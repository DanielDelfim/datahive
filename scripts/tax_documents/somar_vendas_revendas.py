#!/usr/bin/env python
from __future__ import annotations
import argparse
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, Iterable

# paths / config
from app.utils.tax_documents.config import (
    pp_resumo_json_path,
    pp_consolidado_somas_json_path,
)

# services e filtros (reuso)
from app.utils.tax_documents.service import (
    _iter_buckets_mes,
    _load_pp_rows_from_json,
    gerar_resumo_por_natureza_from_pp,
)
from app.utils.tax_documents.filters import (
    filtrar_por_cfop,
    filtrar_por_situacao,
    pos_filtro_por_provedor,
)

# --- CFOPs: tenta os conjuntos “própria” e “revenda”; se não existirem, usa fallback ---
try:
    from app.utils.tax_documents.config import CFOPS_VENDA_PROPRIA, CFOPS_REVENDA
except Exception:  # compat
    CFOPS_VENDA_PROPRIA = {"5101", "6101"}                     # produção do estabelecimento
    CFOPS_REVENDA       = {"5102", "5405", "6102", "6405"}     # mercadoria de terceiros

# ===================== Helpers =====================
def _has_key(rows: list[dict], key: str) -> bool:
    return any(isinstance(r, dict) and key in r for r in rows)

def _has_any_key(rows: list[dict], keys: list[str]) -> bool:
    return any(_has_key(rows, k) for k in keys)

def _to_float(x) -> float:
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0

def _dedup_sum(rows: Iterable[dict], field: str = "Valor Nota") -> float:
    """Soma um campo por NF (ID/Chave) apenas 1x."""
    seen, total = set(), 0.0
    for r in rows:
        nid = r.get("ID Nota") or r.get("Chave de acesso") or ""
        if nid and nid in seen:
            continue
        if nid:
            seen.add(nid)
        total += _to_float(r.get(field, 0))
    return total

def _load_resumo_rows(prov: str, ano: int, mes: int, regiao, debug: bool) -> Optional[list[dict]]:
    """Lê o resumo se existir; caso contrário, None."""
    p = Path(pp_resumo_json_path(prov, ano, mes, regiao))
    if not p.exists():
        if debug:
            print(f"[DEBUG] Resumo inexistente: {p}")
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        rows = doc.get("rows") or []
        if debug:
            lbl = getattr(regiao, "value", regiao) or "-"
            print(f"[DEBUG] Resumo carregado {prov}/{lbl}: {len(rows)} linhas")
        return rows
    except Exception as e:
        if debug:
            print(f"[WARN] Resumo inválido {p}: {e}")
        return None

def _normalize_and_filter_rows(source_rows: list[dict], prov: str, *, only_auth: bool) -> list[dict]:
    rows = list(source_rows)
    if only_auth and _has_any_key(rows, ["Situacao NFe", "Situação NFe"]):
        rows = filtrar_por_situacao(rows, {"autorizada"})
    rows = pos_filtro_por_provedor(rows, prov)  # ex.: Bling → Série=1 (se houver)
    return rows

def _sum_venda_revenda(rows: list[dict]) -> tuple[float, float]:
    """Soma Valor Nota por CFOP (Venda Própria x Revenda), com dedupe por NF."""
    venda_rows   = filtrar_por_cfop(rows, incluir=CFOPS_VENDA_PROPRIA)
    revenda_rows = filtrar_por_cfop(rows, incluir=CFOPS_REVENDA)
    return _dedup_sum(venda_rows), _dedup_sum(revenda_rows)

# ===================== CLI =====================
def parse_args():
    ap = argparse.ArgumentParser(
        description="Somar Valor Nota por CFOP (Venda Própria x Revenda) com dedupe por NF."
    )
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--somente-autorizadas", action="store_true", help="Ignora NF canceladas/denegadas.")
    ap.add_argument("--source", choices=["auto", "resumo", "pp"], default="auto",
                    help="De onde ler os dados: resumo, pp ou auto (prefere resumo e cai para pp).")
    ap.add_argument("--refresh-resumos", action="store_true",
                    help="Antes de somar, regrava os resumos com modo=vendas (garante consistência).")
    ap.add_argument("--debug", action="store_true")
    return ap.parse_args()

# ===================== main =====================
def main():
    a = parse_args()
    ano, mes, only_auth = a.ano, a.mes, a.somente_autorizadas

    result: Dict[str, Dict[str, float]] = {
        "meli":   {"venda": 0.0, "revenda": 0.0, "total": 0.0},
        "amazon": {"venda": 0.0, "revenda": 0.0, "total": 0.0},
        "bling":  {"venda": 0.0, "revenda": 0.0, "total": 0.0},
        "geral":  {"venda": 0.0, "revenda": 0.0, "total": 0.0},
    }

    buckets = _iter_buckets_mes(ano, mes)
    if a.debug:
        print(f"[DEBUG] Buckets: {buckets}")

    # (opcional) garante resumos de vendas atualizados
    if a.refresh_resumos and a.source in {"auto", "resumo"}:
        for prov, reg in buckets:
            try:
                gerar_resumo_por_natureza_from_pp(prov, ano, mes, regiao=reg, modo="vendas", dry_run=False, debug=a.debug)
                if a.debug:
                    lbl = getattr(reg, "value", reg) or "-"
                    print(f"[DEBUG] Resumo (modo=vendas) gerado: {prov}/{lbl}")
            except Exception as e:
                if a.debug:
                    print(f"[WARN] Falha ao gerar resumo {prov}/{getattr(reg,'value',reg) or '-'}: {e}")

    for prov, reg in buckets:
        rows: Optional[list[dict]] = None

    # 1) Fonte preferida: RESUMO (se 'auto' ou 'resumo')
    used_resumo = False
    if a.source in {"auto", "resumo"}:
        rows = _load_resumo_rows(prov, ano, mes, reg, a.debug)
        # Se resumo não tiver CFOP (ex.: só Natureza/Valores), caímos para PP
        if rows is not None and not _has_any_key(rows, ["Item CFOP", "CFOP"]):
            if a.debug:
                lbl = getattr(reg, "value", reg) or "-"
                print(f"[DEBUG] Resumo sem CFOP ({prov}/{lbl}) → fallback para PP JSON")
            rows = None
        else:
            used_resumo = rows is not None

    # 2) Fallback: PP JSON
    if rows is None:
        rows = _load_pp_rows_from_json(prov, ano, mes, reg, debug=a.debug)

    # filtros padrão + somatório por CFOP
    rows = _normalize_and_filter_rows(rows, prov, only_auth=only_auth)
    if a.debug:
        # conta quantas têm CFOP detectável
        from app.utils.tax_documents.filters import _extract_cfop_from_row  # usa o helper acima
        total = len(rows)
        com_cfop = sum(1 for r in rows if _extract_cfop_from_row(r))
        print(f"[DEBUG] {prov}/{getattr(reg,'value',reg) or '-'}: rows={total} com_cfop={com_cfop}")

    # soma por CFOP (conjuntos em config)
    v, r = _sum_venda_revenda(rows)

    result[prov]["venda"]   += v
    result[prov]["revenda"] += r
    result[prov]["total"]   += (v + r)

    if a.debug:
        lbl = getattr(reg, "value", reg) or "-"
        src = "resumo" if used_resumo else "pp"
        print(f"[DEBUG] {prov}/{lbl}: venda={v:.2f} revenda={r:.2f} (source={src})")

    # Totais gerais
    result["geral"]["venda"]   = result["meli"]["venda"]   + result["amazon"]["venda"]   + result["bling"]["venda"]
    result["geral"]["revenda"] = result["meli"]["revenda"] + result["amazon"]["revenda"] + result["bling"]["revenda"]
    result["geral"]["total"]   = result["geral"]["venda"] + result["geral"]["revenda"]

    payload: Dict[str, Any] = {
        "_meta": {
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "competencia": f"{ano:04d}-{mes:02d}",
            "somente_autorizadas": bool(only_auth),
            "source": a.source,
            "cfop_sets": {
                "venda_propria": sorted(CFOPS_VENDA_PROPRIA),
                "revenda":       sorted(CFOPS_REVENDA),
            },
        },
        "totais": result,
    }

    out = pp_consolidado_somas_json_path(ano, mes)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"status": "ok", "output": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
