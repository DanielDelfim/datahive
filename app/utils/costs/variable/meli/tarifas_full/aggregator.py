from __future__ import annotations
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# Colunas por aba
NUMERIC_ABA1 = ["valor_tarifa","unidades_armazenadas","tarifa_por_unidade"]
DATE_ABA1 = ["data_tarifa"]

NUMERIC_ABA2 = ["valor_custo","tarifa_por_m3","unidades_retiradas","volume_unitario_cm3"]
DATE_ABA2 = ["data_custo"]

NUMERIC_ABA3 = ["valor_custo","tarifa_por_m3","volume_total_m3","unidades_coletadas","volume_unitario_cm3"]
DATE_ABA3 = ["data_custo"]

NUMERIC_ABA4 = ["valor_custo","custo_por_unidade","unidades_armazenadas","tempo_meses","unidades_disponiveis","unidades_nao_disponiveis"]
DATE_ABA4 = ["data_custo"]

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

def _to_date_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, dayfirst=True, errors="coerce").dt.date

def _apply_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].apply(_to_float)

def _apply_dates(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = _to_date_series(df[c])

def _competencia_from(df: pd.DataFrame, date_col: str, fallback: Optional[str]) -> str:
    comp = fallback
    if not comp and date_col in df.columns and pd.notna(df[date_col]).any():
        dtser = pd.to_datetime(df[date_col], errors="coerce")
        if dtser.notna().any():
            comp = f"{int(dtser.dt.year.mode().iloc[0]):04d}-{int(dtser.dt.month.mode().iloc[0]):02d}"
    if not comp:
        comp = datetime.today().strftime("%Y-%m")
    return comp

def enrich_and_clean_aba1(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    _apply_numeric(df, NUMERIC_ABA1)
    _apply_dates(df, DATE_ABA1)
    comp = _competencia_from(df, "data_tarifa", competencia)
    df["competencia"] = comp
    return df

def enrich_and_clean_aba2(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    _apply_numeric(df, NUMERIC_ABA2)
    _apply_dates(df, DATE_ABA2)
    comp = _competencia_from(df, "data_custo", competencia)
    df["competencia"] = comp
    return df

def enrich_and_clean_aba3(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    _apply_numeric(df, NUMERIC_ABA3)
    _apply_dates(df, DATE_ABA3)
    comp = _competencia_from(df, "data_custo", competencia)
    df["competencia"] = comp
    return df

def enrich_and_clean_aba4(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    _apply_numeric(df, NUMERIC_ABA4)
    _apply_dates(df, DATE_ABA4)
    comp = _competencia_from(df, "data_custo", competencia)
    df["competencia"] = comp
    return df

# JSON-safe
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
        if isinstance(v, float) and (v != v):
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
