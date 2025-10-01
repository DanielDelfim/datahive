from __future__ import annotations
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

NUMERIC_COLS = [
    "valor_tarifa",
    "valor_acrescimo",
    "valor_total_acrescido",
    "valor_operacao",
]

BOOL_COLS = ["tarifa_estornada"]
DATE_COLS = ["data_movimento"]

def _to_bool(x):
    if pd.isna(x):
        return None
    s = str(x).strip().lower()
    if s in {"true","t","1","sim","yes"}:
        return True
    if s in {"false","f","0","não","nao","no"}:
        return False
    return None

def _to_float(x):
    if pd.isna(x):
        return None
    if isinstance(x, str):
        s = x.strip().replace(".", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None
    if isinstance(x, Decimal):
        try:
            return float(x)
        except Exception:
            return None
    try:
        return float(x)
    except Exception:
        return None

def _to_date(x):
    if pd.isna(x):
        return None
    return pd.to_datetime(x, dayfirst=True, errors="coerce")

def enrich_and_clean(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = df[c].apply(_to_float)
    for c in BOOL_COLS:
        if c in df.columns:
            df[c] = df[c].apply(_to_bool)
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = df[c].apply(_to_date).dt.date

    comp = competencia
    if not comp and "data_movimento" in df.columns and df["data_movimento"].notna().any():
        dtser = pd.to_datetime(df["data_movimento"], errors="coerce")
        if dtser.notna().any():
            comp = f"{int(dtser.dt.year.mode().iloc[0]):04d}-{int(dtser.dt.month.mode().iloc[0]):02d}"
    if not comp:
        comp = datetime.today().strftime("%Y-%m")

    df["competencia"] = comp
    return df
# JSON-safe (datas, numpy, Decimal etc.)

def _serialize_json_safe(v):
    try:
        import numpy as np
        import pandas as pd
    except Exception:
        np = None
        pd = None

    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)): 
        if v != v:  # NaN
            return None
        return v
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()

    if pd is not None and isinstance(v, getattr(pd, "Timestamp", ())):
        try:
            return v.to_pydatetime().isoformat()
        except Exception:
            return v.isoformat()

    if np is not None and isinstance(v, getattr(np, "datetime64", ())):
        if pd is not None:
            ts = pd.to_datetime(v, errors="coerce")
            return None if pd.isna(ts) else ts.to_pydatetime().isoformat()
        return str(v)

    if pd is not None and getattr(pd, "isna", None) is not None:
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass

    if isinstance(v, Decimal):
        try:
            return float(v)
        except Exception:
            return str(v)

    if np is not None and isinstance(v, getattr(np, "generic", ())):
        try:
            return _serialize_json_safe(v.item())
        except Exception:
            return str(v)

    if isinstance(v, dict):
        return {str(k): _serialize_json_safe(val) for k, val in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_serialize_json_safe(val) for val in v]

    return str(v)

def to_json_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    recs = df.where(pd.notnull(df), None).to_dict(orient="records")
    for r in recs:
        for k, v in list(r.items()):
            r[k] = _serialize_json_safe(v)
    return recs
