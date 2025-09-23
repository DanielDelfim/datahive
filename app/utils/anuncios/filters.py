# app/utils/anuncios/filters.py
from __future__ import annotations
from typing import Iterable, Callable, Dict, Any, List, Optional
import re

Record = Dict[str, Any]
Predicate = Callable[[Record], bool]

# ------------------------- helpers internos -------------------------

def _norm_str(x: Any) -> str:
    """Normaliza strings para comparação: str, strip, casefold. Retorna '' se None."""
    if x is None:
        return ""
    return str(x).strip().casefold()

def _get_mlb(rec: Record) -> str:
    """Suporta PP ('mlb') e RAW ('id' dentro de item/registro)."""
    # PP plano
    v = rec.get("mlb")
    if v:
        return str(v)
    # Caso rec seja um RAW-item (objeto do /items/<id>)
    v = rec.get("id")
    if v:
        return str(v)
    # Caso rec seja o envelope RAW unitário { "item": {...} }
    item = rec.get("item") or {}
    v = item.get("id")
    return str(v) if v else ""

def _get_title(rec: Record) -> str:
    t = rec.get("title")
    if t is None and isinstance(rec.get("item"), dict):
        t = rec["item"].get("title")
    return t if isinstance(t, str) else ""

def _get_sku(rec: Record) -> str:
    """
    PP: 'sku'.
    RAW: tentar seller_custom_field / seller_sku; fallback em attributes SELLER_SKU.
    """
    v = rec.get("sku")
    if isinstance(v, str) and v.strip():
        return v

    # RAW em nível de item
    item = rec.get("item") if isinstance(rec.get("item"), dict) else rec
    if isinstance(item, dict):
        for k in ("seller_custom_field", "seller_sku", "catalog_product_id", "sku"):
            vv = item.get(k)
            if isinstance(vv, str) and vv.strip():
                return vv
        attrs = item.get("attributes") or []
        if isinstance(attrs, list):
            for a in attrs:
                if not isinstance(a, dict):
                    continue
                aid = str(a.get("id") or "").upper()
                aname = str(a.get("name") or "").upper()
                if aid in {"SELLER_SKU", "SKU"} or "SKU" in aname:
                    val = a.get("value_name") or a.get("value_id")
                    if isinstance(val, str) and val.strip():
                        return val
    return ""

def _only_digits(s: Optional[str]) -> str:
    """Mantém apenas dígitos para normalizar GTIN/EAN."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"\D+", "", s)

def _get_gtin(rec: Record) -> str:
    """
    PP: tenta 'gtin' já pronto.
    RAW: procura em attributes (id == 'GTIN' ou name contém 'GTIN' ou 'Código universal de produto').
    Retorna apenas dígitos.
    """
    # PP direto
    v = rec.get("gtin")
    if isinstance(v, str) and v.strip():
        return _only_digits(v)

    # RAW em nível de item (ou envelope { "item": {...} })
    item = rec.get("item") if isinstance(rec.get("item"), dict) else rec
    if isinstance(item, Dict):
        attrs = item.get("attributes") or []
        if isinstance(attrs, list):
            for a in attrs:
                if not isinstance(a, dict):
                    continue
                aid = str(a.get("id") or "").upper()
                aname = str(a.get("name") or "").strip().upper()
                if aid == "GTIN" or "GTIN" in aname or "CÓDIGO UNIVERSAL DE PRODUTO" in aname:
                    val = a.get("value_name")
                    if not val:
                        vals = a.get("values") or []
                        if isinstance(vals, list) and vals:
                            val = vals[0].get("name")
                    return _only_digits(val) if isinstance(val, str) else ""
    return ""


def _get_status(rec: Record) -> str:
    st = rec.get("status")
    if st is None and isinstance(rec.get("item"), dict):
        st = rec["item"].get("status")
    return st if isinstance(st, str) else ""

def _get_logistic_type(rec: Record) -> str:
    lt = rec.get("logistic_type")
    if lt is None and isinstance(rec.get("item"), dict):
        ship = rec["item"].get("shipping") or {}
        lt = ship.get("logistic_type")
    return lt if isinstance(lt, str) else ""

# --------------------------- predicados puros ---------------------------

def by_mlb(*mlbs: str) -> Predicate:
    """Mantém registros cujo MLB esteja em mlbs (case-insensitive)."""
    wanted = { _norm_str(m) for m in mlbs if m }
    def _pred(rec: Record) -> bool:
        if not wanted:
            return True
        return _norm_str(_get_mlb(rec)) in wanted
    return _pred

def by_title_contains(query: Optional[str]) -> Predicate:
    """Mantém registros cujo título contém 'query' (case-insensitive)."""
    q = _norm_str(query)
    def _pred(rec: Record) -> bool:
        if not q:
            return True
        return q in _norm_str(_get_title(rec))
    return _pred

def by_sku_contains(query: Optional[str]) -> Predicate:
    """Mantém registros cujo SKU contém 'query' (case-insensitive)."""
    q = _norm_str(query)
    def _pred(rec: Record) -> bool:
        if not q:
            return True
        return q in _norm_str(_get_sku(rec))
    return _pred

def by_gtin_contains(query: Optional[str]) -> Predicate:
    """Mantém registros cujo GTIN (apenas dígitos) contém 'query' (apenas dígitos)."""
    q = _only_digits(query) if query else ""
    def _pred(rec: Record) -> bool:
        if not q:
            return True
        return q in _get_gtin(rec)
    return _pred

def by_gtins(*gtins: str) -> Predicate:
    """Mantém registros cujo GTIN esteja no conjunto (comparação por dígitos)."""
    wanted = { _only_digits(g) for g in gtins if g }
    wanted.discard("")
    def _pred(rec: Record) -> bool:
        if not wanted:
            return True
        return _get_gtin(rec) in wanted
    return _pred

def by_fulfillment_only(flag: bool = True) -> Predicate:
    """
    Se flag=True, mantém apenas logistic_type == 'fulfillment'.
    Se flag=False, não filtra por fulfillment.
    """
    def _pred(rec: Record) -> bool:
        if not flag:
            return True
        return _norm_str(_get_logistic_type(rec)) == "fulfillment"
    return _pred

def by_active_only(flag: bool = True) -> Predicate:
    """
    Se flag=True, mantém apenas status == 'active'.
    Se flag=False, não filtra por status.
    """
    def _pred(rec: Record) -> bool:
        if not flag:
            return True
        return _norm_str(_get_status(rec)) == "active"
    return _pred

# --------------------------- composição/execução ---------------------------

def all_filters(preds: Iterable[Predicate]) -> Predicate:
    """Combina predicados com AND."""
    preds = list(preds)
    def _pred(rec: Record) -> bool:
        for p in preds:
            if not p(rec):
                return False
        return True
    return _pred

def apply_filters(
    data: Iterable[Record],
    mlbs: Optional[Iterable[str]] = None,
    title_q: Optional[str] = None,
    sku_q: Optional[str] = None,
    gtin_q: Optional[str] = None,
    gtins: Optional[Iterable[str]] = None,
    fulfillment_only: bool = False,
    active_only: bool = False,
) -> List[Record]:
    """
    Aplica um conjunto de filtros a uma lista de registros (PP ou RAW-item).
    Retorna nova lista filtrada (não muta 'data').
    """
    mlbs = list(mlbs or [])

    gtins = list(gtins or [])
    pred = all_filters([
        by_mlb(*mlbs),
        by_title_contains(title_q),
        by_sku_contains(sku_q),
        by_gtin_contains(gtin_q),
        by_gtins(*gtins),
        by_fulfillment_only(fulfillment_only),
        by_active_only(active_only),
    ])
    return [rec for rec in data if pred(rec)]
