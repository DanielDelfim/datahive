#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Limpa EAN (remove hífen e sufixos, mantendo apenas dígitos) nos arquivos PP:
 - C:/Apps/Datahive/data/estoques/pp/estoque_sp.json
 - C:/Apps/Datahive/data/estoques/pp/estoque_mg.json

Uso:
  python scripts/estoques_matriz_filial/limpar_ean_pp.py            # ALL
  python scripts/estoques_matriz_filial/limpar_ean_pp.py --regiao SP
  python scripts/estoques_matriz_filial/limpar_ean_pp.py --regiao ALL --dry-run
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from app.config.paths import Regiao
from app.utils.estoques_matriz_filial.config import (
    estoque_pp_json_regiao,
    atomic_write_json,
)
from app.utils.estoques_matriz_filial.normalizer import clean_ean

def _load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, data, do_backup=True)

def _clean_records(records: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Retorna (total, alterados) após padronizar o campo 'ean' em cada registro.
    """
    total = len(records)
    changed = 0
    for rec in records:
        old = str(rec.get("ean", "")).strip()
        new = clean_ean(old)
        if new != old:
            rec["ean"] = new
            changed += 1
    return total, changed

def _run_for_regiao(regiao: Regiao, dry_run: bool) -> None:
    target = estoque_pp_json_regiao(regiao)
    records = _load_json(target)

    if not records:
        print(f"⚠️  {regiao.value.upper()}: arquivo vazio ou inexistente → {target}")
        return

    total, changed = _clean_records(records)
    print(f"{regiao.value.upper()}: {changed}/{total} registros com EAN ajustado.")

    if not dry_run:
        _save_json(target, records)
        print(f"✅ Gravado: {target}")
    else:
        print("🔎 Dry-run: nenhuma gravação realizada.")

def main():
    parser = argparse.ArgumentParser(description="Limpa EAN nos arquivos PP de estoque.")
    parser.add_argument("--regiao", choices=["SP", "MG", "ALL"], default="ALL",
                        help="Qual arquivo PP ajustar (default: ALL).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas reporta alterações, sem gravar.")
    args = parser.parse_args()

    if args.regiao in ("SP", "ALL"):
        _run_for_regiao(Regiao.SP, args.dry_run)
    if args.regiao in ("MG", "ALL"):
        _run_for_regiao(Regiao.MG, args.dry_run)

if __name__ == "__main__":
    main()
