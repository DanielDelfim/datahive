from __future__ import annotations
from typing import Iterable, Dict, Any, List, Optional, Callable, Union

def _norm(s: Optional[object]) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    return s.lower() if s else None

def _is_iterable_but_not_str(x: object) -> bool:
    if isinstance(x, (str, bytes)) or x is None:
        return False
    try:
        iter(x)
        return True
    except TypeError:
        return False

def _to_norm_id_set(order_id_or_ids: Union[str, int, Iterable[Union[str, int]]]) -> set[str]:
    """
    Converte 1 id ou uma coleção de ids (str|int|iterável) para um set normalizado (str lower).
    """
    if _is_iterable_but_not_str(order_id_or_ids):
        return {v for v in (_norm(i) for i in order_id_or_ids) if v}
    one = _norm(order_id_or_ids)
    return {one} if one else set()

def by_mlb(rows: Iterable[Dict[str, Any]], mlb: str) -> List[Dict[str, Any]]:
    tgt = _norm(mlb)
    return [r for r in rows if tgt and _norm(r.get("item_id")) == tgt]

def by_sku(rows: Iterable[Dict[str, Any]], sku: str) -> List[Dict[str, Any]]:
    tgt = _norm(sku)
    return [r for r in rows if tgt and _norm(r.get("seller_sku")) == tgt]

def by_gtin(
    rows: Iterable[Dict[str, Any]],
    gtin: str,
    *,
    getter: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
) -> List[Dict[str, Any]]:
    """
    Filtra por GTIN/EAN. Se o row não tiver gtin direto, passe um getter opcional.
    """
    tgt = _norm(gtin)

    def _get(row: Dict[str, Any]) -> Optional[str]:
        if getter:
            return _norm(getter(row))
        return _norm(row.get("gtin") or row.get("ean") or row.get("item", {}).get("ean"))

    return [r for r in rows if tgt and _get(r) == tgt]

def by_order_id(
    rows: Iterable[Dict[str, Any]],
    order_id_or_ids: Union[str, int, Iterable[Union[str, int]]],
) -> List[Dict[str, Any]]:
    """
    Filtra por número da venda (order_id).
    Aceita um único id ou uma coleção (lista/tupla/conjunto) de ids (str|int).
    Comparação é feita por igualdade textual normalizada.
    """
    tgt_ids = _to_norm_id_set(order_id_or_ids)
    if not tgt_ids:
        return []
    out: List[Dict[str, Any]] = []
    for r in rows:
        oid = _norm(r.get("order_id"))
        if oid and oid in tgt_ids:
            out.append(r)
    return out
