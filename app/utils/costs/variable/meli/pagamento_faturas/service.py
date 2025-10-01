from __future__ import annotations
from typing import List, Dict, Any, Optional
import pandas as pd
from .mapper import map_columns_aba1, map_columns_aba2
from .aggregator import (
    enrich_and_clean_aba1, enrich_and_clean_aba2, to_json_records
)

def read_pagamentos_estornos(
    xlsx_path: str | bytes,
    competencia: Optional[str] = None,
    header_row: int = 9,                 # linha 10
    sheet_name: str = "Pagamentos e estornos",
) -> List[Dict[str, Any]]:
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=header_row, dtype=object, engine="openpyxl")
    df = map_columns_aba1(df)
    df = enrich_and_clean_aba1(df, competencia=competencia)
    return to_json_records(df)

def read_detalhe_pagamentos_mes(
    xlsx_path: str | bytes,
    competencia: Optional[str] = None,
    header_row: int = 9,                 # linha 10
    sheet_name: str = "Detalhe do Pagamentos deste mês",
) -> List[Dict[str, Any]]:
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=header_row, dtype=object, engine="openpyxl")
    df = map_columns_aba2(df)
    df = enrich_and_clean_aba2(df, competencia=competencia)
    return to_json_records(df)
