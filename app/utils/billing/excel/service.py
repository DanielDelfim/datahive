# app/utils/billing/excel/service.py
from __future__ import annotations

from typing import Dict, Any, Iterable, Optional
import calendar
import pandas as pd

from app.utils.billing.config import excel_dir
from app.utils.billing.excel.ingest import (
    carregar_faturamento_mp,
    carregar_faturamento_ml,
    carregar_tarifas_full,
    carregar_pagamento_faturas,
)
from app.utils.billing.excel.conceitos import categorias_fatura_ml

# ----------------------
# Helpers (internos)
# ----------------------
def _month_bounds(ano: int, mes: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    first = pd.Timestamp(year=ano, month=mes, day=1)
    last  = pd.Timestamp(year=ano, month=mes, day=calendar.monthrange(ano, mes)[1], hour=23, minute=59, second=59)
    return first, last

def _bounds_from_df(df: Optional[pd.DataFrame]) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    if df is None or df.empty or "__data__" not in df.columns:
        return None, None
    d = pd.to_datetime(df["__data__"], errors="coerce").dropna()
    if d.empty:
        return None, None
    return d.min(), d.max()

def _clip_by_bounds(df: Optional[pd.DataFrame], d0: pd.Timestamp, d1: pd.Timestamp) -> Optional[pd.DataFrame]:
    if df is None or df.empty or "__data__" not in df.columns:
        return df
    dd = pd.to_datetime(df["__data__"], errors="coerce")
    return df.loc[(dd >= d0) & (dd <= d1)].copy()

def _clip_outliers(df: Optional[pd.DataFrame], lim_por_linha: float, fonte: str, anomalias: list[dict]) -> Optional[pd.DataFrame]:
    if df is None or df.empty or "__valor__" not in df.columns:
        return df
    mask = df["__valor__"].abs() > float(lim_por_linha)
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
    """Ads só com termos de Ads; Envios só com termos de envio; gestão da venda → Tarifas de venda."""
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

def _sum_by_category(dfs: list[Optional[pd.DataFrame]]) -> dict[str, float]:
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
            tot[c] = tot.get(c, 0.0) + float(v or 0.0)
    return {k: round(v, 2) for k, v in tot.items()}

# ----------------------
# API pública
# ----------------------
def consolidar_excel(*, market: str, ano: int, mes: int, regioes: Iterable[str]) -> Dict[str, Any]:
    """(mantida) Consolidação ampla com detalhes por fonte."""
    cats = list(categorias_fatura_ml())
    total_cobrancas = {c: 0.0 for c in cats}
    total_pagamentos = 0.0
    detalhes_por_fonte = {"MP": None, "ML": None, "FULL": None, "PAY": None}
    frames_mp: list[pd.DataFrame] = []
    frames_ml: list[pd.DataFrame] = []
    frames_full: list[pd.DataFrame] = []
    frames_pay: list[pd.DataFrame] = []

    for reg in regioes:
        d = excel_dir(market, ano, mes, reg)
        mp = carregar_faturamento_mp(d)
        ml = carregar_faturamento_ml(d)
        fu = carregar_tarifas_full(d)
        pay = carregar_pagamento_faturas(d)

        if not mp.empty:
            g = mp.groupby("__categoria__", dropna=False)["__valor__"].sum()
            for c, v in g.items():
                if c in total_cobrancas:
                    total_cobrancas[c] += float(v or 0.0)
            frames_mp.append(mp)
        if not ml.empty:
            g = ml.groupby("__categoria__", dropna=False)["__valor__"].sum()
            for c, v in g.items():
                if c in total_cobrancas:
                    total_cobrancas[c] += float(v or 0.0)
            frames_ml.append(ml)
        if not fu.empty:
            g = fu.groupby("__categoria__", dropna=False)["__valor__"].sum()
            for c, v in g.items():
                if c in total_cobrancas:
                    total_cobrancas[c] += float(v or 0.0)
            frames_full.append(fu)
        if not pay.empty:
            total_pagamentos += float(pay["__valor_mes__"].fillna(0).sum())
            frames_pay.append(pay)

    if frames_mp:
        detalhes_por_fonte["MP"] = pd.concat(frames_mp, ignore_index=True).to_dict(orient="records")
    if frames_ml:
        detalhes_por_fonte["ML"] = pd.concat(frames_ml, ignore_index=True).to_dict(orient="records")
    if frames_full:
        detalhes_por_fonte["FULL"] = pd.concat(frames_full, ignore_index=True).to_dict(orient="records")
    if frames_pay:
        detalhes_por_fonte["PAY"] = pd.concat(frames_pay, ignore_index=True).to_dict(orient="records")

    return {
        "fatura_por_categoria": {k: round(float(v), 2) for k, v in total_cobrancas.items()},
        "resumo": {
            "total_cobrancas": round(sum(total_cobrancas.values()), 2),
            "total_pagamentos": round(total_pagamentos, 2),
        },
        "detalhes_por_fonte": detalhes_por_fonte,
        "categorias": cats,
        "parametros": {"market": market, "ano": ano, "mes": mes, "regioes": list(regioes)},
    }

def consolidar_fatura_totais(
    *,
    market: str,
    ano: int,
    mes: int,
    regioes: Iterable[str],
    periodo_por: str = "ml",
    lim_por_linha: float = 10_000.0,
) -> Dict[str, Any]:
    """
    Retorna somente o fatura_totais (periodo, totais, categorias) deduplicado por __tarifa_id__ entre MP/ML/FULL/PAY_DET.
    """
    # --------- carregar por região ---------
    frames_mp: list[pd.DataFrame] = []
    frames_ml: list[pd.DataFrame] = []
    frames_full: list[pd.DataFrame] = []
    frames_pay: list[pd.DataFrame] = []  # detalhe do mês com __valor__/__categoria__

    regioes_processadas: list[str] = []
    for reg in regioes:
        d = excel_dir(market, ano, mes, reg)
        mp = carregar_faturamento_mp(d)
        ml = carregar_faturamento_ml(d)
        fu = carregar_tarifas_full(d)
        pay = carregar_pagamento_faturas(d)

        has_data = False
        if not mp.empty:
            frames_mp.append(mp)
            has_data = True
        if not ml.empty:
            frames_ml.append(ml)
            has_data = True
        if not fu.empty:
            frames_full.append(fu)
            has_data = True

        # usamos apenas as linhas do PAY que são "cobranças" (têm __valor__ + __categoria__)
        if not pay.empty and "__valor__" in pay.columns and "__categoria__" in pay.columns:
            frames_pay.append(pay[["__id__","__data__","__valor__","__categoria__","__tarifa_id__"]].copy())
            has_data = True

        if has_data:
            regioes_processadas.append(reg)

    df_mp   = pd.concat(frames_mp,   ignore_index=True) if frames_mp   else None
    df_ml   = pd.concat(frames_ml,   ignore_index=True) if frames_ml   else None
    df_full = pd.concat(frames_full, ignore_index=True) if frames_full else None
    df_pay_det = pd.concat(frames_pay, ignore_index=True) if frames_pay else None

    # --------- período canônico ---------
    if periodo_por == "calendario":
        d0, d1 = _month_bounds(ano, mes)
        crit = "calendario"
    elif periodo_por == "ml":
        d0, d1 = _bounds_from_df(df_ml);  crit = "ml"
    elif periodo_por == "mp":
        d0, d1 = _bounds_from_df(df_mp);  crit = "mp"
    elif periodo_por == "full":
        d0, d1 = _bounds_from_df(df_full); crit = "full"
    else:  # charges (união)
        b = [_bounds_from_df(x) for x in (df_mp, df_ml, df_full, df_pay_det)]
        mins = [x for x,_ in b if x is not None]
        maxs = [y for _,y in b if y is not None]
        d0 = min(mins) if mins else None
        d1 = max(maxs) if maxs else None
        crit = "charges"
    if d0 is None or d1 is None:
        d0, d1 = _month_bounds(ano, mes); crit = "calendario(fallback)"

    # --------- filtro por período + sanity + rebucket ---------
    anomalias: list[dict] = []
    def _prep(df, fonte):
        df = _clip_by_bounds(df, d0, d1)
        df = _clip_outliers(df, lim_por_linha, fonte, anomalias)
        return df

    df_mp   = _prep(df_mp,   "MP")
    df_ml   = _prep(df_ml,   "ML")
    df_full = _prep(df_full, "FULL")
    df_pay_det = _prep(df_pay_det, "PAY_DET")

    df_ml = _rebucket_ml_conservative(df_ml)

    # --------- dedup global por __tarifa_id__ ---------
    dfs = [df for df in (df_mp, df_ml, df_full, df_pay_det) if df is not None and not df.empty]
    if dfs:
        cobr = pd.concat(dfs, ignore_index=True, sort=False)
        cobr = cobr.dropna(subset=["__valor__"])
        if "__tarifa_id__" in cobr.columns:
            # mantém a última ocorrência (ex.: duplicidades entre arquivos/abas)
            cobr = cobr.drop_duplicates(subset=["__tarifa_id__"], keep="last")
    else:
        cobr = pd.DataFrame(columns=["__categoria__","__valor__"])

    # --------- somatório por categoria ---------
    categorias = {}
    if not cobr.empty:
        categorias = cobr.groupby("__categoria__")["__valor__"].sum().map(lambda v: round(float(v or 0.0), 2)).to_dict()

    total_cobrancas = round(sum(categorias.values()), 2)

    return {
        "periodo": {"data_min": d0.isoformat(), "data_max": d1.isoformat(), "criterio_datas": crit},
        "totais": {"total_cobrancas": total_cobrancas},
        "categorias": categorias,
        "regioes_processadas": regioes_processadas,
        "diagnostico": {
            "linhas_mp":   int(0 if df_mp   is None or df_mp.empty   else len(df_mp)),
            "linhas_ml":   int(0 if df_ml   is None or df_ml.empty   else len(df_ml)),
            "linhas_full": int(0 if df_full is None or df_full.empty else len(df_full)),
            "linhas_pay_det": int(0 if df_pay_det is None or df_pay_det.empty else len(df_pay_det)),
            "anomalias": anomalias,
        },
        "parametros": {"market": market, "ano": ano, "mes": mes, "regioes": list(regioes), "periodo_por": periodo_por},
    }
