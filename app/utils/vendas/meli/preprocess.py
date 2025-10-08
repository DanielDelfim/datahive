# app/utils/vendas/meli/preprocess.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config.paths import APP_TIMEZONE, vendas_raw_json
from app.utils.core.io import ler_json

__all__ = ["parse_iso_to_tz", "normalize_order", "normalize_from_file"]

def parse_iso_to_tz(s: Optional[str], tz_name: Optional[str] = None) -> Optional[str]:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        # try the straightforward parse first
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            # fallback: strip fractional seconds but preserve timezone offset if present
            if len(s) >= 6 and (s[-6] == "+" or s[-6] == "-"):
                dt = datetime.fromisoformat(s.split(".")[0] + s[-6:])
            else:
                # last resort: try without fractional seconds / timezone
                dt = datetime.fromisoformat(s.split(".")[0])
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    target_tz = ZoneInfo(tz_name or APP_TIMEZONE)
    return dt.astimezone(target_tz).isoformat(timespec="seconds")

def _first(d: Dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return None

def normalize_order(order: Dict[str, Any], tz_name: Optional[str] = None) -> List[Dict[str, Any]]:
    tz = tz_name or APP_TIMEZONE
    date_created = parse_iso_to_tz(order.get("date_created"), tz)
    date_closed  = parse_iso_to_tz(order.get("date_closed"), tz)
    last_updated = parse_iso_to_tz(_first(order, "date_last_updated", "last_updated"), tz)
    payments = order.get("payments") or []
    pay_approved = parse_iso_to_tz(payments[0].get("date_approved"), tz) if payments else None
    date_approved = pay_approved or parse_iso_to_tz(order.get("date_approved"), tz)

    order_id    = order.get("id")
    pack_id     = order.get("pack_id")
    currency_id = order.get("currency_id")
    paid_amount = order.get("paid_amount")
    buyer_id    = (order.get("buyer") or {}).get("id")
    seller_id   = (order.get("seller") or {}).get("id")
    site_id     = _first(order.get("context") or {}, "site") or order.get("site_id")

    rows: List[Dict[str, Any]] = []
    for oi in (order.get("order_items") or []):
        item   = oi.get("item") or {}
        qty    = oi.get("quantity")
        uprice = oi.get("unit_price")
        rows.append({
            "order_id": order_id, "pack_id": pack_id, "site_id": site_id,
            "buyer_id": buyer_id, "seller_id": seller_id,
            "date_created": date_created, "date_approved": date_approved,
            "date_closed": date_closed, "last_updated": last_updated,
            "item_id": item.get("id"), "title": item.get("title"), "seller_sku": item.get("seller_sku"),
            "quantity": qty, "unit_price": uprice, "paid_amount": paid_amount, "currency_id": currency_id,
        })
    if not rows:
        rows.append({
            "order_id": order_id, "pack_id": pack_id, "site_id": site_id,
            "buyer_id": buyer_id, "seller_id": seller_id,
            "date_created": date_created, "date_approved": date_approved,
            "date_closed": date_closed, "last_updated": last_updated,
            "item_id": None, "title": None, "seller_sku": None,
            "quantity": None, "unit_price": None, "paid_amount": paid_amount, "currency_id": currency_id,
        })
    return rows

def normalize_from_file(loja: str, raw_path: Optional[Path] = None,
                        tz_name: Optional[str] = None) -> List[Dict[str, Any]]:
    p = raw_path or vendas_raw_json(loja)
    data = ler_json(p)
    results = data.get("results") or []
    rows: List[Dict[str, Any]] = []
    for order in results:
        rows.extend(normalize_order(order, tz_name=tz_name or APP_TIMEZONE))
    return rows
