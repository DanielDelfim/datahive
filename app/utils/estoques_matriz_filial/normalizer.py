# app/utils/estoques_matriz_filial/normalizer.py
from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd
import re

# Schema “raw” esperado (cabeçalhos vindos do Excel/CSV)
RAW_SCHEMA = {
    "required": ["ID", "Código", "EAN", "Descrição", "Quantidade"],
    "types": {
        "ID": "any",         # manteremos como string na normalização
        "Código": "any",
        "EAN": "any",
        "Descrição": "any",
        "Quantidade": "numeric",  # precisa ser numérico convertível
    },
}

_COLMAP = {
    "ID": "id",
    "Código": "codigo",
    "EAN": "ean",
    "Descrição": "descricao",
    "Quantidade": "quantidade",
}

def required_raw_columns() -> List[str]:
    return list(RAW_SCHEMA["required"])

def validate_header(df: pd.DataFrame) -> None:
    missing = [c for c in required_raw_columns() if c not in df.columns]
    if missing:
        raise ValueError(
            f"Colunas obrigatórias ausentes: {missing}. "
            f"Esperado: {required_raw_columns()}. Recebido: {list(df.columns)}"
        )


def to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    def cast_qty(x):
        try:
            i = int(x)
            if float(i) == float(x):
                return i
            return float(x)
        except Exception:
            return float(x) if pd.notna(x) else 0.0

    recs: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        recs.append({
            "id": row["id"],
            "codigo": row["codigo"],
            "ean": row["ean"],
            "descricao": row["descricao"],
            "quantidade": cast_qty(row["quantidade"]),
        })
    return recs

_EAN_SPLIT = re.compile(r"^-?(.+)$")  # placeholder; veremos só o split por '-' mesmo

def clean_ean(value: str) -> str:
    """
    Retorna o EAN 'puro' contendo somente dígitos da PARTE ANTES do primeiro hífen.
    Exemplos:
      "7908812400175-50" -> "7908812400175"
      "  7891234567890 "  -> "7891234567890"
      "ABC-123"          -> "123"
      "" / None          -> ""
    """
    if value is None:
        return ""
    s = str(value).strip()
    # pega apenas a parte antes do primeiro hífen
    if "-" in s:
        s = s.split("-", 1)[0]
    # mantém somente dígitos
    digits = re.sub(r"\D+", "", s)
    return digits

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # (trechos existentes até renomear colunas)
    validate_header(df)
    df = df.rename(columns=_COLMAP)

    for col in ["id", "codigo", "ean", "descricao"]:
        df[col] = df[col].astype(str).str.strip().fillna("")

    # >>> NOVO: limpar EAN <<<
    df["ean"] = df["ean"].map(clean_ean)

    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0)
    df.loc[df["quantidade"] < 0, "quantidade"] = 0

    mask_vazias = (
        (df[["id", "codigo", "ean", "descricao"]]
         .apply(lambda s: s.str.strip() == "", axis=0).all(axis=1))
        & (df["quantidade"] == 0)
    )
    df = df[~mask_vazias].reset_index(drop=True)
    return df

__all__ = [
    "RAW_SCHEMA",
    "required_raw_columns",
    "validate_header",
    "normalize_df",
    "to_records",
    "clean_ean",   # <<< exporta para uso no script de limpeza
]
