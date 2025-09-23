#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Atualiza JSONs de estoque (SP e MG) a partir de planilhas Excel.

- Lê:
  • default_excel_sp() -> Estoque__filial_SP.xlsx
  • default_excel_mg() -> Estoque__matriz_MG.xlsx
  (podem ser alterados via CLI ou ENV)

- Grava (via atomic_write_json/backup_path de app/config/paths.py):
  • data/estoques/raw/estoque_sp.json
  • data/estoques/raw/estoque_mg.json
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# Pega tudo do config do módulo (que por sua vez referencia paths.py)
from app.utils.estoques_matriz_filial.config import (
    Regiao,
    default_excel_sp,
    default_excel_mg,
    estoque_json_regiao,
    atomic_write_json,
)

COLMAP = {
    "ID": "id",
    "Código": "codigo",
    "EAN": "ean",
    "Descrição": "descricao",
    "Quantidade": "quantidade",
}
REQUIRED_COLS = list(COLMAP.keys())

def _read_excel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {path}")
    return pd.read_excel(path, engine=None)

def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Colunas obrigatórias ausentes: {missing}. Esperado: {REQUIRED_COLS}"
        )
    df = df.rename(columns=COLMAP)

    for col in ["id", "codigo", "ean", "descricao"]:
        df[col] = df[col].astype(str).str.strip().fillna("")

    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0)
    df.loc[df["quantidade"] < 0, "quantidade"] = 0

    # Remove linhas totalmente vazias
    mask_vazias = (
        (df[["id", "codigo", "ean", "descricao"]].apply(lambda s: s.str.strip() == "", axis=0).all(axis=1))
        & (df["quantidade"] == 0)
    )
    df = df[~mask_vazias].reset_index(drop=True)
    return df

def _to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
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
        recs.append(
            {
                "id": row["id"],
                "codigo": row["codigo"],
                "ean": row["ean"],
                "descricao": row["descricao"],
                "quantidade": cast_qty(row["quantidade"]),
            }
        )
    return recs

def _processar(xlsx_path: Path, regiao: Regiao) -> Path:
    df = _normalize_df(_read_excel(xlsx_path))
    data = _to_records(df)

    target = estoque_json_regiao(regiao)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target, data, do_backup=True)
    return target

def main():
    parser = argparse.ArgumentParser(description="Atualiza JSONs de estoque (SP/MG) a partir de Excel.")
    parser.add_argument("--sp", dest="sp_path", default=str(default_excel_sp()),
                        help="Caminho do Excel da FILIAL SP (default: ENV ESTOQUE_SP_XLSX ou padrão do módulo)")
    parser.add_argument("--mg", dest="mg_path", default=str(default_excel_mg()),
                        help="Caminho do Excel da MATRIZ MG (default: ENV ESTOQUE_MG_XLSX ou padrão do módulo)")
    args = parser.parse_args()

    sp_xlsx = Path(args.sp_path)
    mg_xlsx = Path(args.mg_path)

    out_sp = _processar(sp_xlsx, Regiao.SP)
    out_mg = _processar(mg_xlsx, Regiao.MG)

    print("✅ Estoques atualizados:")
    print(f" - SP: {out_sp}")
    print(f" - MG: {out_mg}")

if __name__ == "__main__":
    main()
