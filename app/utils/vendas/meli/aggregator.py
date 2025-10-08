# app/utils/vendas/meli/aggregator.py
from __future__ import annotations
from typing import List, Dict, Any, Iterable, Optional
from collections import defaultdict

from app.utils.core.filtros import rows_in_ml_window, ml_window_bounds

__all__ = ["apply_filters", "summarize", "window_sums", "all_windows", "per_mlb"]

def _num(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

def _qty(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

def line_total(row: Dict[str, Any]) -> float:
    return _qty(row.get("quantity")) * _num(row.get("unit_price"))

def apply_filters(rows: Iterable[Dict[str, Any]],
                  mlb: Optional[str] = None,
                  sku: Optional[str] = None,
                  title_contains: Optional[str] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    mlb = (mlb or "").strip().lower() or None
    sku = (sku or "").strip().lower() or None
    tkn = (title_contains or "").strip().lower() or None
    for r in rows:
        if mlb and str(r.get("item_id", "")).lower() != mlb:
            continue
        if sku and str(r.get("seller_sku", "")).lower() != sku:
            continue
        if tkn and tkn not in str(r.get("title", "")).lower():
            continue
        out.append(r)
    return out

def _orders_paid(rows: Iterable[Dict[str, Any]]) -> float:
    seen = {}
    for r in rows:
        oid = r.get("order_id")
        if oid is None: 
            continue
        paid = _num(r.get("paid_amount"))
        seen[oid] = max(paid, seen.get(oid, 0.0))
    return sum(seen.values())

def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    items_count  = len(rows)
    orders_count = len({r.get("order_id") for r in rows if r.get("order_id") is not None})
    qty_total    = sum(_qty(r.get("quantity")) for r in rows)
    items_gross  = sum(line_total(r) for r in rows)
    orders_paid  = _orders_paid(rows)
    return {"items_count": items_count, "orders_count": orders_count,
            "qty_total": qty_total, "items_gross": items_gross, "orders_paid": orders_paid}

def window_sums(rows: List[Dict[str, Any]], days: int,
                date_field: str = "date_approved", *, mode: str = "ml") -> Dict[str, Any]:
    if mode == "ml":
        win_from, win_to = ml_window_bounds(days)
        sub = rows_in_ml_window(rows, days, date_field=date_field)
    else:
        win_from, win_to = ml_window_bounds(days)
        sub = rows_in_ml_window(rows, days, date_field=date_field)
    base = summarize(sub)
    base.update({"days": days, "from": win_from, "to": win_to})
    return base

def all_windows(rows: List[Dict[str, Any]], windows: Iterable[int] = (7, 15, 30),
                date_field: str = "date_approved",
                mlb: Optional[str] = None, sku: Optional[str] = None,
                title_contains: Optional[str] = None, *, mode: str = "ml") -> Dict[str, Any]:
    base = apply_filters(rows, mlb=mlb, sku=sku, title_contains=title_contains)
    out: Dict[str, Any] = {}
    for d in windows:
        out[str(d)] = window_sums(base, d, date_field=date_field, mode=mode)
    return out

def per_mlb(
    rows: List[Dict[str, Any]],
    windows: Iterable[int] = (7, 15, 30),
    date_field: str = "date_approved",
    *,
    mode: str = "ml",
) -> Dict[str, Any]:
    """
    Agrega vendas por MLB (item_id), mantendo um título representativo (primeiro visto).
    """
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    titles: Dict[str, str] = {}
    for r in rows:
        mlb = str(r.get("item_id") or "")
        if not mlb:
            continue
        groups[mlb].append(r)
        if r.get("title") and mlb not in titles:
            titles[mlb] = r["title"]
    out: Dict[str, Any] = {}
    for mlb, lst in groups.items():
        w = {str(d): window_sums(lst, d, date_field=date_field, mode=mode) for d in windows}
        out[mlb] = {"title": titles.get(mlb), "windows": w}
    return out

# app/utils/vendas/meli/aggregator.py

def _norm_str(x):
    return str(x).strip().lower() if x is not None else None

def _row_gtin(row: Dict[str, Any], getter=None) -> Optional[str]:
    if getter:
        v = getter(row)
        if v:
            return _norm_str(v)
    # tentativas padrão no PP/RAW do ML
    return _norm_str(row.get("gtin") or row.get("ean") or (row.get("item") or {}).get("ean"))

def per_gtin(
    rows: List[Dict[str, Any]],
    windows: Iterable[int] = (7, 15, 30),
    date_field: str = "date_approved",
    *,
    mode: str = "ml",
    gtin_getter=None,
) -> Dict[str, Any]:
    """
    Agrega vendas por GTIN (soma todas as MLBs do mesmo GTIN).
    Mantém um título representativo (primeiro visto).
    """
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    titles: Dict[str, str] = {}
    for r in rows:
        g = _row_gtin(r, getter=gtin_getter)
        if not g:
            continue
        groups[g].append(r)
        if r.get("title") and g not in titles:
            titles[g] = r["title"]
    out: Dict[str, Any] = {}
    for gtin, lst in groups.items():
        w = {str(d): window_sums(lst, d, date_field=date_field, mode=mode) for d in windows}
        out[gtin] = {"title": titles.get(gtin), "windows": w, "mlbs_count": len({x.get("item_id") for x in lst if x.get("item_id")})}
    return out

