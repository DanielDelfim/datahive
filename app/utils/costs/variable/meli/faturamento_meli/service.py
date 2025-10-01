from __future__ import annotations
from typing import List, Dict, Any, Optional
import pandas as pd
from .mapper import map_columns
from .aggregator import enrich_and_clean, to_json_records

def read_faturamento_meli_excel(xlsx_path: str | bytes, competencia: Optional[str] = None) -> List[Dict[str, Any]]:
    df = pd.read_excel(xlsx_path, sheet_name="REPORT", header=7, dtype=object, engine="openpyxl")
    df = map_columns(df)
    df = enrich_and_clean(df, competencia=competencia)
    return to_json_records(df)
