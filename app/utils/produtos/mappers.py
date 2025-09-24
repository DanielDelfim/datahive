# app/utils/produtos/mappers.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import re


def sku_to_gtin(items: Dict[str, Dict[str, Any]]) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    for sku, rec in items.items():
        out[sku] = rec.get("gtin")
    return out


def gtin_to_skus(items: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for sku, rec in items.items():
        gtin = rec.get("gtin")
        if not gtin:
            continue
        out.setdefault(gtin, []).append(sku)
    return out


def sku_to_dun14(items: Dict[str, Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """
    Usa campo 'dum_14' (DUN-14) se existir. Sanitiza para dígitos.
    """
    out: Dict[str, Optional[str]] = {}
    for sku, rec in items.items():
        raw = rec.get("dum_14")
        if raw is None:
            out[sku] = None
            continue
        digits = re.sub(r"\D", "", str(raw))
        out[sku] = digits or None
    return out
