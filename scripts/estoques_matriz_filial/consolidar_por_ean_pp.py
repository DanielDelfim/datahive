#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Consolida PP por EAN (soma quantidades) e grava o resultado.

Uso:
  # Consolida SP e MG in-place (backup automático):
  python scripts/estoques_matriz_filial/consolidar_por_ean_pp.py

  # Apenas SP:
  python scripts/estoques_matriz_filial/consolidar_por_ean_pp.py --regiao SP

  # Salvar em pasta separada:
  python scripts/estoques_matriz_filial/consolidar_por_ean_pp.py --out "C:/Apps/Datahive/data/estoques/pp_consolidado"

  # Forçar escrever em arquivo específico:
  python scripts/estoques_matriz_filial/consolidar_por_ean_pp.py --regiao MG --out "C:/temp/estoque_mg_consolidado.json"
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

from app.config.paths import Regiao
from app.utils.estoques_matriz_filial.config import (
    estoque_pp_json_regiao,
    atomic_write_json,
)
from app.utils.estoques_matriz_filial.aggregator import consolidar_por_ean

def _load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, data, do_backup=True)

def _consolidar_um(regiao: Regiao, out_arg: str | None) -> None:
    src = estoque_pp_json_regiao(regiao)
    data = _load_json(src)
    if not data:
        print(f"⚠️  {regiao.value.upper()}: arquivo vazio ou inexistente → {src}")
        return

    before = len(data)
    qty_before = sum(float(r.get("quantidade", 0) or 0) for r in data)

    data2 = consolidar_por_ean(data)
    after = len(data2)
    qty_after = sum(float(r.get("quantidade", 0) or 0) for r in data2)

    # Monta destino
    if out_arg:
        out = Path(out_arg)
        if out.exists() and out.is_dir():
            out = out / f"estoque_{regiao.value}_consolidado.json"
    else:
        out = src  # inplace

    # (Opcional) meta simples
    if isinstance(data2, list) and data2:
        # somente se o primeiro for dict simples — não impomos em todos
        if isinstance(data2[0], dict):
            # escreve um arquivo planar (lista), meta não é por registro;
            # então só logamos no console e seguimos.
            pass

    _save_json(out, data2)

    print(f"✅ {regiao.value.upper()} consolidado por EAN.")
    print(f"   • Registros: {before} → {after}")
    print(f"   • Quantidade total: {qty_before} → {qty_after}")
    print(f"   • Saída: {out}")

def main():
    parser = argparse.ArgumentParser(description="Consolida PP por EAN (soma quantidades).")
    parser.add_argument("--regiao", choices=["SP", "MG", "ALL"], default="ALL",
                        help="Quais arquivos consolidar (default: ALL).")
    parser.add_argument("--out", dest="out_path", default=None,
                        help="Arquivo ou pasta de saída. Se omitido, sobrescreve o PP (in-place).")
    args = parser.parse_args()

    if args.regiao in ("SP", "ALL"):
        _consolidar_um(Regiao.SP, args.out_path)
    if args.regiao in ("MG", "ALL"):
        _consolidar_um(Regiao.MG, args.out_path)

if __name__ == "__main__":
    main()
