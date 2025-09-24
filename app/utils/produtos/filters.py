# app/utils/produtos/filters.py
from __future__ import annotations
from typing import Dict, Any, Iterable, Optional


def filtrar_kits(items: Dict[str, Dict[str, Any]], apenas_kits: bool = True) -> Dict[str, Dict[str, Any]]:
    out = {}
    for sku, rec in items.items():
        e_kit = rec.get("e_kit") is True
        if (apenas_kits and e_kit) or (not apenas_kits and not e_kit):
            out[sku] = rec
    return out


def filtrar_ativos(items: Dict[str, Dict[str, Any]], ativo: Optional[bool] = True) -> Dict[str, Dict[str, Any]]:
    if ativo is None:
        return dict(items)
    return {k: v for k, v in items.items() if (v.get("ativo") is ativo)}


def buscar_por_sku(items: Dict[str, Dict[str, Any]], sku: str) -> Optional[Dict[str, Any]]:
    return items.get(sku)


def filtrar_por_marca(items: Dict[str, Dict[str, Any]], marcas: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    mset = {str(m).strip().lower() for m in marcas}
    return {k: v for k, v in items.items() if (str(v.get("marca") or "").strip().lower() in mset)}
