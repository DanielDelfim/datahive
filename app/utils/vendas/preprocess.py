# app/utils/vendas/preprocess.py
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config.paths import APP_TIMEZONE, vendas_raw_json
from app.utils.core.io import ler_json

__all__ = [
    "parse_iso_to_tz",
    "normalize_order",
    "normalize_from_file",
]

def parse_iso_to_tz(s: Optional[str], tz_name: Optional[str] = None) -> Optional[str]:
    """
    Converte string ISO-8601 (p.ex. '2025-09-18T15:37:33.000-04:00' ou '...+00:00' ou '...Z')
    para ISO no timezone do projeto (default: APP_TIMEZONE), preservando offset correto.
    Retorna string ISO (e.g. 'YYYY-MM-DDTHH:MM:SS±HH:MM') ou None se s vazio.
    """
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")  # compat parser
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # tenta variações simples (sem milissegundos)
        try:
            dt = datetime.fromisoformat(s.split(".")[0] + s[-6:])
        except Exception:
            return None
    if dt.tzinfo is None:
        # assume UTC se vier “naive”
        dt = dt.replace(tzinfo=timezone.utc)
    target_tz = ZoneInfo(tz_name or APP_TIMEZONE)
    return dt.astimezone(target_tz).isoformat(timespec="seconds")

def _first(d: Dict[str, Any], *keys: str) -> Optional[str]:
    """Retorna o primeiro valor não-vazio dentre d[k] para k em keys, ou None."""
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return None

def normalize_order(order: Dict[str, Any], tz_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Normaliza um 'order' do ML (estrutura de /orders/search) em 1..N linhas (uma por item).
    Campos principais:
      - datas normalizadas: date_created, date_approved, date_closed, last_updated
      - item: id (MLB...), title, seller_sku
      - valores: quantity, unit_price, paid_amount (topo), currency_id
      - ids contextuais: order_id, pack_id, buyer_id, seller_id, site_id
    """
    tz = tz_name or APP_TIMEZONE

    # Datas no topo e em payments
    date_created = parse_iso_to_tz(order.get("date_created"), tz)
    date_closed  = parse_iso_to_tz(order.get("date_closed"), tz)
    last_updated = parse_iso_to_tz(_first(order, "date_last_updated", "last_updated"), tz)

    payments = order.get("payments") or []
    pay_approved = None
    if payments:
        # pega o primeiro "date_approved" aprovado (ou o primeiro disponível)
        pay_approved = parse_iso_to_tz(payments[0].get("date_approved"), tz)

    date_approved = pay_approved or parse_iso_to_tz(order.get("date_approved"), tz)

    # Valores e metadados do topo
    order_id    = order.get("id")
    pack_id     = order.get("pack_id")
    currency_id = order.get("currency_id")
    paid_amount = order.get("paid_amount")  # total pago (topo)
    buyer_id    = (order.get("buyer") or {}).get("id")
    seller_id   = (order.get("seller") or {}).get("id")
    site_id     = _first(order.get("context") or {}, "site") or order.get("site_id")

    rows: List[Dict[str, Any]] = []
    for oi in (order.get("order_items") or []):
        item   = oi.get("item") or {}
        qty    = oi.get("quantity")
        uprice = oi.get("unit_price")

        rows.append({
            # ids
            "order_id": order_id,
            "pack_id": pack_id,
            "site_id": site_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,

            # datas (todas no fuso do projeto)
            "date_created": date_created,
            "date_approved": date_approved,
            "date_closed": date_closed,
            "last_updated": last_updated,

            # item
            "item_id": item.get("id"),
            "title": item.get("title"),
            "seller_sku": item.get("seller_sku"),

            # valores
            "quantity": qty,
            "unit_price": uprice,
            "paid_amount": paid_amount,
            "currency_id": currency_id,
        })

    # fallback: sem items -> ainda retorna 1 linha mínima com cabeçalho do pedido
    if not rows:
        rows.append({
            "order_id": order_id, "pack_id": pack_id, "site_id": site_id,
            "buyer_id": buyer_id, "seller_id": seller_id,
            "date_created": date_created, "date_approved": date_approved,
            "date_closed": date_closed, "last_updated": last_updated,
            "item_id": None, "title": None, "seller_sku": None,
            "quantity": None, "unit_price": None, "paid_amount": paid_amount,
            "currency_id": currency_id,
        })
    return rows

def normalize_from_file(loja: str, raw_path: Optional[Path] = None,
                        tz_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lê o RAW (.../vendas/<loja>/raw/vendas.json por padrão) e retorna linhas normalizadas.
    """
    p = raw_path or vendas_raw_json(loja)
    data = ler_json(p)

    results = data.get("results") or []
    rows: List[Dict[str, Any]] = []
    for order in results:
        rows.extend(normalize_order(order, tz_name=tz_name or APP_TIMEZONE))
    return rows
