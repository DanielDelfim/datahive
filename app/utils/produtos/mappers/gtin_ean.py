#C:\Apps\Datahive\app\utils\produtos\mappers\gtin_ean.py
from __future__ import annotations
from typing import Dict, Any, Optional, Iterable

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def _iter_items(produtos_obj: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """
    Aceita {"items": [...]} ou {"items": {...}} e devolve um iterável de produtos.
    """
    items = produtos_obj.get("items")
    if isinstance(items, list):
        return items
    if isinstance(items, dict):
        return items.values()
    return []

def build_indices(produtos_obj: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Índices canônicos do domínio Produtos.
    - por_gtin: gtin/ean/codigo_barras -> produto
    - por_sku : sku/seller_sku/codigo  -> produto
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
    if indices is None:
        indices = build_indices(produtos_obj or {})
    prod = (indices.get("por_sku") or {}).get(_norm(sku))
    if not prod:
        return None
    return _norm(prod.get("gtin") or prod.get("ean") or prod.get("codigo_barras"))

def gtin_to_sku(gtin: str, *, indices: Optional[Dict[str, Dict[str, Any]]] = None,
                produtos_obj: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if indices is None:
        indices = build_indices(produtos_obj or {})
    prod = (indices.get("por_gtin") or {}).get(_norm(gtin))
    if not prod:
        return None
    return _norm(prod.get("sku") or prod.get("seller_sku") or prod.get("codigo"))
