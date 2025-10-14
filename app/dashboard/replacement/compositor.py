from __future__ import annotations
from typing import List, Dict, Any
from app.utils.replacement.service import (
    estimativa_consumo_por_mlb,
    estimativa_consumo_por_gtin_br,
)

def _as_rows(d: dict[str, dict]) -> List[Dict[str, Any]]:
    rows = list(d.values())
    rows.sort(key=lambda r: (-float(r.get("estimado_30") or 0), r.get("title") or "", r.get("mlb") or r.get("gtin") or ""))
    return rows

def resumo_sp_mlb() -> List[Dict[str, Any]]:
    return _as_rows(estimativa_consumo_por_mlb("sp"))

def resumo_mg_mlb() -> List[Dict[str, Any]]:
    return _as_rows(estimativa_consumo_por_mlb("mg"))

def resumo_br_gtin() -> List[Dict[str, Any]]:
    return _as_rows(estimativa_consumo_por_gtin_br())
