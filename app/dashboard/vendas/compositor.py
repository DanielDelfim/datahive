# app/dashboard/vendas/compositor.py
from __future__ import annotations
from typing import Literal, List, Dict, Any
import pandas as pd
from app.utils.vendas.meli.service import (
    get_por_mlb, get_por_mlb_br,
    get_por_gtin, get_por_gtin_br,
)

Loja = Literal["sp", "mg"]

_EXPECTED_COLS = ["id", "titulo", "sold_7", "sold_15", "sold_30", "mlbs_count"]

def _qty_from_windows(payload: Dict[str, Any], win: str) -> float:
    try:
        return float((payload.get("windows", {}).get(win) or {}).get("qty_total") or 0.0)
    except Exception:
        return 0.0

def _df_from_agg_dict(agg_dict: Dict[str, Any], id_key_name: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    if isinstance(agg_dict, dict):
        for k, payload in agg_dict.items():
            payload = payload or {}
            row = {
                "id": k,
                "titulo": payload.get("title"),
                "sold_7":  _qty_from_windows(payload, "7"),
                "sold_15": _qty_from_windows(payload, "15"),
                "sold_30": _qty_from_windows(payload, "30"),
                "mlbs_count": payload.get("mlbs_count"),
            }
            rows.append(row)

    df = pd.DataFrame(rows)

    # garante todas as colunas esperadas mesmo se vazio
    for col in _EXPECTED_COLS:
        if col not in df.columns:
            df[col] = 0 if col.startswith("sold_") or col.endswith("_count") else None

    # renomeia id e ordena
    df.rename(columns={"id": id_key_name}, inplace=True)
    df = df[[id_key_name, "titulo", "sold_7", "sold_15", "sold_30", "mlbs_count"]]

    if not df.empty:
        df = df.sort_values(
            ["sold_7", "sold_15", "sold_30", id_key_name],
            ascending=[False, False, False, True],
            kind="mergesort",
        ).reset_index(drop=True)

    return df

def tabela_por_mlb(loja: Loja) -> pd.DataFrame:
    return _df_from_agg_dict(get_por_mlb(loja, windows=(7, 15, 30)), "mlb")

def tabela_por_mlb_br() -> pd.DataFrame:
    return _df_from_agg_dict(get_por_mlb_br(windows=(7, 15, 30)), "mlb")

def tabela_por_gtin(loja: Loja) -> pd.DataFrame:
    return _df_from_agg_dict(get_por_gtin(loja, windows=(7, 15, 30)), "gtin")

def tabela_por_gtin_br() -> pd.DataFrame:
    return _df_from_agg_dict(get_por_gtin_br(windows=(7, 15, 30)), "gtin")
