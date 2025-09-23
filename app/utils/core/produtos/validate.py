# app/utils/core/validate.py
from typing import Iterable, Mapping

def validate_required(required_fields: Iterable[str], row: Mapping) -> list[str]:
    missing = []
    for f in required_fields:
        v = row.get(f)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            missing.append(f)
    return missing

def coerce_in_set(value, allowed: set[str]) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    return v if v in allowed else None
