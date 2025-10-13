# app/utils/produtos/mappers.py
from __future__ import annotations
from typing import Dict, Any, List, Optional, Iterable
import re


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

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def _iter_items(produtos_obj: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """
    Aceita {"items": [...]} ou {"items": {...}} (dict por gtin/sku).
    Retorna um iterável de produtos (dicts).
    """
    items = produtos_obj.get("items")
    if isinstance(items, list):
        return items
    if isinstance(items, dict):
        return items.values()
    return []

def build_indices(produtos_obj: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Constrói índices por_gtin e por_sku a partir do objeto carregado do produtos.json.
    Campos aceitos: gtin/ean, sku.
    """
    por_gtin: Dict[str, Dict[str, Any]] = {}
    por_sku: Dict[str, Dict[str, Any]] = {}

    for p in _iter_items(produtos_obj):
        gtin = _norm(p.get("gtin") or p.get("ean") or p.get("codigo_barras"))
        sku  = _norm(p.get("sku") or p.get("seller_sku") or p.get("codigo"))
        if gtin:
            por_gtin[gtin] = p
        if sku:
            por_sku[sku] = p

    return {"por_gtin": por_gtin, "por_sku": por_sku}

def sku_to_gtin(sku: str, *, indices: Optional[Dict[str, Dict[str, Any]]] = None,
                produtos_obj: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Retorna o GTIN correspondente a um SKU, se existir.
    Preferir passar 'indices' já construído para evitar I/O em chamadas repetidas.
    """
    if indices is None:
        indices = build_indices(produtos_obj or {})
    prod = (indices.get("por_sku") or {}).get(_norm(sku))
    if not prod:
        return None
    return _norm(prod.get("gtin") or prod.get("ean") or prod.get("codigo_barras"))

def gtin_to_sku(gtin: str, *, indices: Optional[Dict[str, Dict[str, Any]]] = None,
                produtos_obj: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Retorna o SKU correspondente a um GTIN, se existir.
    """
    if indices is None:
        indices = build_indices(produtos_obj or {})
    prod = (indices.get("por_gtin") or {}).get(_norm(gtin))
    if not prod:
        return None
    return _norm(prod.get("sku") or prod.get("seller_sku") or prod.get("codigo"))