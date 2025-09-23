#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CLI: valida um arquivo de estoque RAW (Excel/CSV) pelo schema e salva o NORMALIZADO
na camada PP: C:/Apps/Datahive/data/estoques/pp

Uso:
  python scripts/estoques_matriz_filial/validar_estoques_raw.py --in "C:/.../arquivo.xlsx" --regiao SP
  python scripts/estoques_matriz_filial/validar_estoques_raw.py --in "C:/.../arquivo.csv" --regiao MG --out "C:/custom/out.json"
"""

from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

from app.config.paths import Regiao  # enum fonte única
from app.utils.estoques_matriz_filial.config import (
    estoque_pp_json_regiao,
    atomic_write_json,
)
from app.utils.estoques_matriz_filial.normalizer import (
    RAW_SCHEMA,
    validate_header,
    normalize_df,
    to_records,
)

def _read_any(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, engine=None)
    elif suffix in (".csv",):
        return pd.read_csv(path, encoding="utf-8", sep=",")
    else:
        raise ValueError(f"Extensão não suportada: {suffix}. Use .xlsx, .xls ou .csv.")

def _parse_regiao(s: str) -> Regiao:
    s = s.strip().lower()
    if s == "sp":
        return Regiao.SP
    if s == "mg":
        return Regiao.MG
    raise ValueError("Valor inválido para --regiao. Use SP ou MG.")

def main():
    parser = argparse.ArgumentParser(description="Valida e normaliza estoque RAW, salvando em data/estoques/pp.")
    parser.add_argument("--in", dest="in_path", required=True,
                        help="Caminho do arquivo RAW (Excel .xlsx/.xls ou .csv)")
    parser.add_argument("--regiao", dest="regiao", required=True, choices=["SP", "MG"],
                        help="Região do arquivo (SP ou MG)")
    parser.add_argument("--out", dest="out_path", default=None,
                        help="(Opcional) Caminho de saída JSON. Default = estoque_pp_json_regiao(REGIAO)")
    args = parser.parse_args()

    in_path = Path(args.in_path)
    regiao = _parse_regiao(args.regiao)

    # Ler + validar cabeçalho de acordo com o schema
    df_raw = _read_any(in_path)
    try:
        validate_header(df_raw)
    except Exception as e:
        raise SystemExit(f"❌ Schema inválido ({in_path.name}). Esperado colunas: {RAW_SCHEMA['required']}. Erro: {e}")

    # Normalizar (funções puras)
    df_norm = normalize_df(df_raw)
    records = to_records(df_norm)

    # Saída
    out_path: Path
    if args.out_path:
        out_path = Path(args.out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_path = estoque_pp_json_regiao(regiao)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    # Gravação atômica com backup
    atomic_write_json(out_path, records, do_backup=True)

    print("✅ Validação e normalização concluídas.")
    print(f"   • Linhas válidas: {len(records)}")
    print(f"   • Saída (PP): {out_path}")

if __name__ == "__main__":
    main()
