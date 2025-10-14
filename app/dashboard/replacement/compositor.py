# app/dashboard/replacement/compositor.py
from __future__ import annotations
from typing import List, Dict, Any, Iterable, Optional, Tuple

# === Services (fachadas públicas) ===
from app.utils.replacement.service import (
    estimativa_consumo_por_mlb,          # -> dict[mlb] -> row base SP/MG
    estimativa_consumo_por_gtin_br,      # -> dict[gtin] -> row base BR
    map_mlb_to_gtin,                     # -> dict[mlb] -> gtin por região
)
from app.utils.anuncios.service import listar_anuncios_pp  # canônico GTIN/EAN por MLB
from app.utils.vendas.meli import service as vendas_srv    # agregados por MLB/GTIN

# ---------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------
def _ensure_str(v: Any) -> str:
    return "" if v is None else str(v)

def _lower(s: str) -> str:
    return s.lower().strip()

def _as_rows(d: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = list(d.values())
    rows.sort(
        key=lambda r: (
            -float(r.get("estimado_30") or 0),
            r.get("title") or "",
            r.get("mlb") or r.get("gtin") or "",
        )
    )
    return rows

# ---------------------------------------------------------
# Enriquecimento via services
# ---------------------------------------------------------
def _mapa_gtin_por_regiao(regiao: str) -> Dict[str, str]:
    """
    Fonte canônica de GTIN por MLB. Primeiro tenta o service dedicado,
    depois valida contra o PP de anúncios.
    """
    m = map_mlb_to_gtin(regiao) or {}
    if m:
        return m

    # fallback leve: raspa do PP (mantendo arquitetura: ainda é via service de anúncios)
    out: Dict[str, str] = {}
    for a in listar_anuncios_pp(regiao=regiao) or []:
        mlb = _ensure_str(a.get("mlb") or a.get("id")).strip().upper()
        gt  = _ensure_str(a.get("gtin") or a.get("ean") or a.get("barcode")).strip()
        if mlb and gt:
            out[mlb] = gt
    return out

def _sales_map_por_mlb(regiao: str) -> Dict[str, Dict[str, Any]]:
    """
    Aceita diferentes formatos que o service possa retornar.
    """
    try:
        data = vendas_srv.get_por_mlb(regiao, windows=(7, 15, 30))
    except Exception:
        try:
            data = vendas_srv.get_por_mlb(regiao)
        except Exception:
            data = {}

    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        data = data["result"]

    return data if isinstance(data, dict) else {}

def _as_sales(rec: Dict[str, Any]) -> Dict[str, int]:
    def pick(d, *names):
        for n in names:
            if n in d and d[n] is not None:
                return d[n]
        return 0

    v7  = pick(rec, "vendas_7d", "vendido_7d", "w7", "qtd_7")
    v15 = pick(rec, "vendas_15d", "vendido_15d", "w15", "qtd_15")
    v30 = pick(rec, "vendas_30d", "vendido_30d", "w30", "qtd_30")

    win = rec.get("windows") if isinstance(rec.get("windows"), dict) else None
    if win:
        v7  = v7  or pick(win, 7, "7", "w7")
        v15 = v15 or pick(win, 15, "15", "w15")
        v30 = v30 or pick(win, 30, "30", "w30")

    def to_int(x):
        try:
            return int(float(str(x).replace(",", ".")))
        except Exception:
            return 0

    return {"vendas_7d": to_int(v7), "vendas_15d": to_int(v15), "vendas_30d": to_int(v30)}

def _enriquecer_sp_mg(rows: List[Dict[str, Any]], regiao: str) -> List[Dict[str, Any]]:
    mlb_to_gtin = _mapa_gtin_por_regiao(regiao)
    sales_map   = _sales_map_por_mlb(regiao)

    out = []
    for r in rows:
        mlb = _ensure_str(r.get("mlb") or r.get("sku")).strip().upper()
        base = dict(r)
        base["regiao"] = regiao
        base["gtin"] = base.get("gtin") or mlb_to_gtin.get(mlb)
        base["estoque"] = base.get("estoque") or base.get("estoque_atual")

        # replacement com fallback em estimado_*
        base["replacement_30"] = base.get("replacement_30") or base.get("reposicao_30") or base.get("necessidade_30") or base.get("estimado_30")
        base["replacement_60"] = base.get("replacement_60") or base.get("reposicao_60") or base.get("necessidade_60") or base.get("estimado_60")

        # vendas por MLB
        rec = sales_map.get(mlb) or sales_map.get(mlb.lower()) or sales_map.get(mlb.upper()) or {}
        base.update(_as_sales(rec))

        out.append(base)
    return out

# ---------------------------------------------------------
# Facades que a page deve usar
# ---------------------------------------------------------
def anuncios_por_mlb(regiao: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Abastece a aba 1:
      - regiao in {'sp','mg','ambos'}
      - retorna (rows_enriquecidas, 'mlb')
    """
    reg = _lower(_ensure_str(regiao))
    if reg not in {"sp", "mg", "ambos"}:
        reg = "sp"

    rows_sp = _as_rows(estimativa_consumo_por_mlb("sp"))
    rows_mg = _as_rows(estimativa_consumo_por_mlb("mg"))

    if reg == "sp":
        return _enriquecer_sp_mg(rows_sp, "sp"), "mlb"
    if reg == "mg":
        return _enriquecer_sp_mg(rows_mg, "mg"), "mlb"

    # ambos
    out = _enriquecer_sp_mg(rows_sp, "sp") + _enriquecer_sp_mg(rows_mg, "mg")
    return out, "mlb"

def resumo_br_gtin_enriquecido() -> Tuple[List[Dict[str, Any]], str]:
    """
    Abastece a aba 2 (BR por GTIN). Mantém a agregação por GTIN
    e conserva estimado_30/60 para referência.
    """
    rows = _as_rows(estimativa_consumo_por_gtin_br())
    return rows, "gtin"

# ---------------------------------------------------------
# Filtro textual e colunas sugeridas (para a page)
# ---------------------------------------------------------
def filtrar_rows_por_texto(
    rows: Iterable[Dict[str, Any]],
    query: Optional[str],
    campos: Iterable[str] = ("gtin", "ean", "barcode", "title", "mlb", "sku"),
) -> List[Dict[str, Any]]:
    q = _lower(_ensure_str(query))
    if not q:
        return list(rows)
    rows_list = list(rows)
    campos_busca = [c for c in campos if any(c in r for r in rows_list)]
    out: List[Dict[str, Any]] = []
    for r in rows_list:
        for c in campos_busca:
            if q in _lower(_ensure_str(r.get(c, ""))):
                out.append(r)
                break
    return out

_ID_MLB = ["mlb", "sku", "gtin", "ean", "barcode", "title", "regiao"]
_ID_GTIN = ["gtin", "ean", "barcode", "mlb", "sku", "title"]

_SALES = ["vendas_7d", "vendas_15d", "vendas_30d"]
_STOCK = ["estoque", "estoque_atual", "estoque_pos_delay_7"]
_REPL  = ["replacement_30", "replacement_60", "estimado_30", "estimado_60"]
_BUY   = ["multiplo_compra", "preco_compra"]

_COLS_POR_CHAVE: Dict[str, List[str]] = {
    "mlb": _ID_MLB + _SALES + _STOCK + _REPL + _BUY,
    "gtin": _ID_GTIN + _SALES + _STOCK + _REPL + _BUY,
}

def colunas_tabela_sugeridas(key_by: str) -> List[str]:
    return _COLS_POR_CHAVE.get(key_by, [])
