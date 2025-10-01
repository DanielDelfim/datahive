from __future__ import annotations
from typing import Optional
import pandas as pd
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

NUMERIC_ABA1 = [
    "valor_total","valor_aplicado_mes","valor_aplicado_outro_mes",
    "saldo_positivo_outras_faturas","saldo_positivo_devolvido"
]
DATE_ABA1 = ["data_pagamento_ou_estorno","data_cancelamento"]

NUMERIC_ABA2 = ["parte_pagamento_aplicada_tarifas"]
DATE_ABA2 = ["data_pagamento","data_tarifa"]

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

# --- dentro de app/utils/costs/variable/meli/pagamento_faturas/aggregator.py ---

def _to_date_series(s: pd.Series) -> pd.Series:
    # Converte a coluna inteira garantindo datetime64[ns] e só depois extrai .date
    return pd.to_datetime(s, dayfirst=True, errors="coerce").dt.date

def enrich_and_clean_aba1(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    for c in NUMERIC_ABA1:
        if c in df.columns:
            df[c] = df[c].apply(_to_float)
    for c in DATE_ABA1:
        if c in df.columns:
            df[c] = _to_date_series(df[c])  # <-- vetoriza

    comp = competencia
    if not comp and "data_pagamento_ou_estorno" in df.columns and pd.notna(df["data_pagamento_ou_estorno"]).any():
        dtser = pd.to_datetime(df["data_pagamento_ou_estorno"], errors="coerce")
        if dtser.notna().any():
            comp = f"{int(dtser.dt.year.mode().iloc[0]):04d}-{int(dtser.dt.month.mode().iloc[0]):02d}"
    if not comp:
        comp = datetime.today().strftime("%Y-%m")
    df["competencia"] = comp
    return df

def enrich_and_clean_aba2(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    for c in NUMERIC_ABA2:
        if c in df.columns:
            df[c] = df[c].apply(_to_float)
    for c in DATE_ABA2:
        if c in df.columns:
            df[c] = _to_date_series(df[c])  # <-- vetoriza

    comp = competencia
    if not comp and "data_pagamento" in df.columns and pd.notna(df["data_pagamento"]).any():
        dtser = pd.to_datetime(df["data_pagamento"], errors="coerce")
        if dtser.notna().any():
            comp = f"{int(dtser.dt.year.mode().iloc[0]):04d}-{int(dtser.dt.month.mode().iloc[0]):02d}"
    if not comp:
        comp = datetime.today().strftime("%Y-%m")
    df["competencia"] = comp
    return df

# Serialização JSON-safe (datas, numpy, Decimal etc.)

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
        if isinstance(v, float) and (v != v):  # NaN
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

def to_json_records(df: pd.DataFrame) -> list[dict]:
    recs = df.where(pd.notnull(df), None).to_dict(orient="records")
    for r in recs:
        for k, v in list(r.items()):
            r[k] = _serialize_json_safe(v)
    return recs
