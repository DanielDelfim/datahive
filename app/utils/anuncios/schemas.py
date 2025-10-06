from __future__ import annotations
from typing import TypedDict, Optional, List, Dict, Any

class PPAnuncio(TypedDict, total=False):
    mlb: str
    sku: Optional[str]
    gtin: Optional[str]
    title: Optional[str]
    estoque: Optional[float]
    price: Optional[float]
    original_price: Optional[float]
    rebate_price: float | int | None
    rebate_currency: str | None
    status: Optional[str]
    logistic_type: Optional[str]

class PPEnvelope(TypedDict, total=False):
    _generated_at: str
    _source: str
    regiao: str
    marketplace: str
    total: int
    data: List[PPAnuncio]

def has_minimal_fields(rec: Dict[str, Any]) -> bool:
    return "mlb" in rec and "title" in rec

def validate_envelope(env: Dict[str, Any]) -> bool:
    if not isinstance(env, dict):
        return False
    data = env.get("data")
    if not isinstance(data, list):
        return False
    return all(isinstance(x, dict) and has_minimal_fields(x) for x in data)
