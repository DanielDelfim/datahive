#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Consolida relatórios Excel (MP/ML/Full) + Pagamentos e gera artefatos do mês.

Saídas (por mês e região/all):
- fatura_totais.json   ← inclui {periodo, totais.total_cobrancas, categorias}
- reconciliacao.json   ← inclui {periodo, total_pagamentos, ...}
- detalhes_por_fonte.json
- anomalias.json       ← linhas ignoradas por valor anômalo

Uso:
  python scripts/billing/excel/consolidar_relatorios_excel.py --ano 2025 --mes 8 --regiao sp --regiao mg --consolidado --sink file
  # Para período por ML (padrão): --periodo_por ml
  # Para calendário (1º→último):  --periodo_por calendario
"""

from __future__ import annotations

import argparse
import calendar
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Service (utils puros) e paths do domínio
from app.utils.billing.excel.service import consolidar_excel
from app.utils.billing.config import (
    fatura_totais_json,
    reconciliacao_json,
    detalhes_por_fonte_json,
    billing_results_dir,
)

# =========================
# JSON-safe serialization
# =========================
def _to_jsonable(obj):
    """Converte recursivamente Timestamps/NaT/numpy para tipos JSON."""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    try:
        if pd.isna(obj):  # NaT/NaN/None
            return None
    except Exception:
        pass
    if isinstance(obj, (np.integer, )):
        return int(obj)
    if isinstance(obj, (np.floating,  )):
        return float(obj)
    return obj

def _emit_json(obj: Any, target: Path, sink: str = "file") -> None:
    """Emite JSON via result_sink.make_sink('json'|'stdout'), fallback atomic_write_json."""
    obj = _to_jsonable(obj)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from app.utils.core.result_sink.service import make_sink
        if sink in ("file", "both"):
            make_sink("json", output_dir=target.parent, filename=target.name).emit(obj)
        if sink in ("stdout", "both"):
            make_sink("stdout").emit(obj)
    except Exception:
        from app.config.paths import atomic_write_json
        atomic_write_json(target, obj, do_backup=True)
        if sink in ("stdout", "both"):
            print(json.dumps(obj, ensure_ascii=False, indent=2))

# =========================
# Datas: período canônico
# =========================
def _month_bounds(ano: int, mes: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    first = pd.Timestamp(year=ano, month=mes, day=1)
    last = pd.Timestamp(year=ano, month=mes, day=calendar.monthrange(ano, mes)[1],
                        hour=23, minute=59, second=59)
    return first, last

def _bounds_from_df(df: pd.DataFrame | None) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if df is None or df.empty or "__data__" not in df.columns:
        return None, None
    d = pd.to_datetime(df["__data__"], errors="coerce").dropna()
    if d.empty:
        return None, None
    return d.min(), d.max()

def _clip_by_bounds(df: pd.DataFrame | None, d0: pd.Timestamp, d1: pd.Timestamp) -> pd.DataFrame | None:
    if df is None or df.empty or "__data__" not in df.columns:
        return df
    dd = pd.to_datetime(df["__data__"], errors="coerce")
    return df.loc[(dd >= d0) & (dd <= d1)].copy()

# =========================
# Sanitização e ajustes
# =========================
LIM_LINHA_COBR = 10_000.0  # teto razoável por linha de tarifa

def _clip_outliers(df: Optional[pd.DataFrame], fonte: str, anomalias: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    if df is None or df.empty or "__valor__" not in df.columns:
        return df
    mask = df["__valor__"].abs() > LIM_LINHA_COBR
    if mask.any():
        for _, r in df.loc[mask].iterrows():
            anomalias.append({
                "fonte": fonte,
                "id": str(r.get("__id__", "")),
                "categoria": r.get("__categoria__", ""),
                "conceito": r.get("__conceito__", ""),
                "valor": float(r.get("__valor__", 0.0)),
            })
    return df.loc[~mask].copy()

_ADS_KEYS = ("campanhas de publicidade", "publicidade", "publicidad", "product ads", "brand ads")
_ENVIO_KEYS = ("tarifa de envio", "envio", "intermunicipal", "etiqueta")

def _is_ads(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _ADS_KEYS)

def _is_envio(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _ENVIO_KEYS)

def _rebucket_ml_conservative(df_ml: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Garante que Ads só tenha termos de Ads; Envios só termos de envio; gestão da venda → Tarifas de venda."""
    if df_ml is None or df_ml.empty or "__categoria__" not in df_ml.columns:
        return df_ml
    out = df_ml.copy()
    # Publicidade
    mask_pub = out["__categoria__"].eq("Tarifas por campanha de publicidade")
    out.loc[mask_pub & ~out["__conceito__"].apply(_is_ads), "__categoria__"] = "Tarifas de venda"
    # Envios ML
    mask_env = out["__categoria__"].eq("Tarifas de envios no Mercado Livre")
    out.loc[mask_env & ~out["__conceito__"].apply(_is_envio), "__categoria__"] = "Tarifas de venda"
    # Gestão da venda
    mask_gest = out["__conceito__"].str.lower().str.contains(r"custo de gest|gest[aã]o da venda", na=False)
    out.loc[mask_gest, "__categoria__"] = "Tarifas de venda"
    return out

def _df_from_records(records: Optional[List[Dict[str, Any]]]) -> Optional[pd.DataFrame]:
    if not records:
        return None
    df = pd.DataFrame(records)
    if "__data__" in df.columns:
        df["__data__"] = pd.to_datetime(df["__data__"], errors="coerce")
    if "__valor__" in df.columns:
        df["__valor__"] = pd.to_numeric(df["__valor__"], errors="coerce")
    if "__valor_mes__" in df.columns:
        df["__valor_mes__"] = pd.to_numeric(df["__valor_mes__"], errors="coerce")
    return df

def _sum_by_category(dfs: List[Optional[pd.DataFrame]]) -> Dict[str, float]:
    cats = [
        "Tarifas de venda",
        "Aplicamos descontos sobre essas tarifas",
        "Tarifas de envios no Mercado Livre",
        "Tarifas por campanha de publicidade",
        "Taxas de parcelamento",
        "Tarifas de envios Full",
        "Tarifas dos serviços do Mercado Pago",
        "Tarifas da Minha página",
        "Cancelamentos de tarifas",
    ]
    tot = {c: 0.0 for c in cats}
    for df in dfs:
        if df is None or df.empty:
            continue
        g = df.groupby("__categoria__")["__valor__"].sum()
        for c, v in g.items():
            if c in tot:
                tot[c] += float(v or 0.0)
            else:
                tot["Tarifas de venda"] += float(v or 0.0)
    return {k: round(v, 2) for k, v in tot.items()}

# =========================
# Main
# =========================
def main():
    ap = argparse.ArgumentParser(description="Consolida Excel (MP/ML/Full) + Pagamentos, com período no resumo.")
    ap.add_argument("--market", default="meli")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", action="append", required=True, help="Use múltiplas: --regiao sp --regiao mg")
    ap.add_argument("--consolidado", action="store_true", help="Emite no diretório all/ em vez de por região")
    ap.add_argument(
        "--periodo_por",
        choices=("ml", "mp", "full", "charges", "calendario"),
        default="ml",
        help="Origem do período: ml (padrão), mp, full, charges (MP+ML+Full) ou calendario (1º→último do mês)."
    )
    ap.add_argument("--sink", choices=("file", "stdout", "both"), default="file")
    args = ap.parse_args()

    # 1) Usa service para ler/normalizar (utils puros)
    res = consolidar_excel(market=args.market, ano=args.ano, mes=args.mes, regioes=args.regiao)
    det = res.get("detalhes_por_fonte", {}) or {}

    # 2) Converte para DF
    df_mp   = _df_from_records(det.get("MP"))
    df_ml   = _df_from_records(det.get("ML"))
    df_full = _df_from_records(det.get("FULL"))
    df_pay  = _df_from_records(det.get("PAY"))

    # 3) Definir período canônico (padrão: ML / Data da tarifa)
    if args.periodo_por == "calendario":
        d0, d1 = _month_bounds(args.ano, args.mes)
        criterio_datas = "calendario"
    elif args.periodo_por == "ml":
        d0, d1 = _bounds_from_df(df_ml)
        criterio_datas = "ml"
    elif args.periodo_por == "mp":
        d0, d1 = _bounds_from_df(df_mp)
        criterio_datas = "mp"
    elif args.periodo_por == "full":
        d0, d1 = _bounds_from_df(df_full)
        criterio_datas = "full"
    else:  # charges = união MP+ML+Full
        b = [_bounds_from_df(x) for x in (df_mp, df_ml, df_full)]
        mins = [x for x, _ in b if x is not None]
        maxs = [y for _, y in b if y is not None]
        d0 = min(mins) if mins else None
        d1 = max(maxs) if maxs else None
        criterio_datas = "charges"

    # Fallback: se não achou datas, usa calendário do mês
    if d0 is None or d1 is None:
        d0, d1 = _month_bounds(args.ano, args.mes)
        criterio_datas = "calendario(fallback)"

    # 4) Aplicar período às COBRANÇAS (e aos pagamentos, para reconciliação coerente)
    df_mp   = _clip_by_bounds(df_mp,   d0, d1)
    df_ml   = _clip_by_bounds(df_ml,   d0, d1)
    df_full = _clip_by_bounds(df_full, d0, d1)
    df_pay  = _clip_by_bounds(df_pay,  d0, d1)

    # 5) Sanidade por linha e rechecagem de buckets (ML)
    anomalias: List[Dict[str, Any]] = []
    df_mp   = _clip_outliers(df_mp,   "MP",   anomalias)
    df_ml   = _clip_outliers(df_ml,   "ML",   anomalias)
    df_full = _clip_outliers(df_full, "FULL", anomalias)
    df_ml   = _rebucket_ml_conservative(df_ml)

    # 6) Totais por categoria e pagamentos
    fatura_por_categoria = _sum_by_category([df_mp, df_ml, df_full])
    total_pagamentos = float(df_pay["__valor_mes__"].fillna(0.0).sum()) \
        if (df_pay is not None and "__valor_mes__" in df_pay.columns) else 0.0
    total_cobrancas = float(sum(fatura_por_categoria.values()))

    # 7) Período (bloco utilizado em ambos artefatos)
    periodo = {
        "data_min": d0.isoformat(),
        "data_max": d1.isoformat(),
        "criterio_datas": criterio_datas,
    }

    # 8) Estruturas finais
    fatura_enriched = {
        "periodo": periodo,
        "totais": {"total_cobrancas": round(total_cobrancas, 2)},
        "categorias": fatura_por_categoria,
    }

    reconc = {
        "total_cobrancas": fatura_enriched["totais"]["total_cobrancas"],
        "total_pagamentos": round(total_pagamentos, 2),
        "diferenca": round(total_pagamentos - fatura_enriched["totais"]["total_cobrancas"], 2),
        "periodo": periodo,
        "pagamentos_itens": int(df_pay["__valor_mes__"].count()) if (df_pay is not None and "__valor_mes__" in df_pay.columns) else 0,
        "parametros": {"market": args.market, "ano": args.ano, "mes": args.mes, "regioes": args.regiao},
    }

    def _df_to_records(df: Optional[pd.DataFrame]) -> Optional[List[Dict[str, Any]]]:
        return _to_jsonable(df.to_dict(orient="records")) if df is not None and not df.empty else None

    detalhes_por_fonte = {
        "MP":   _df_to_records(df_mp),
        "ML":   _df_to_records(df_ml),
        "FULL": _df_to_records(df_full),
        "PAY":  _df_to_records(df_pay),
    }

    # 9) Alvos e emissão
    alvo_reg = "all" if args.consolidado else args.regiao[0]
    out_tot  = fatura_totais_json(args.market, args.ano, args.mes, alvo_reg)
    out_rec  = reconciliacao_json(args.market, args.ano, args.mes, alvo_reg)
    out_det  = detalhes_por_fonte_json(args.market, args.ano, args.mes, alvo_reg)
    out_anom = billing_results_dir(args.market, args.ano, args.mes, alvo_reg) / "anomalias.json"

    _emit_json(fatura_enriched,    out_tot, args.sink)
    _emit_json(reconc,             out_rec, args.sink)
    _emit_json(detalhes_por_fonte, out_det, args.sink)
    _emit_json(anomalias,          out_anom, args.sink)

if __name__ == "__main__":
    main()
