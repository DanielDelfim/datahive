from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Dict, Any
from app.config.paths import ensure_dirs, vendas_pp_json, pp_dir
from app.utils.vendas.preprocess import normalize_from_file
from app.utils.core.io import atomic_write_json

USO = "Uso: python -m scripts.vendas.gerar_pp [sp|mg|all]"

def _run_for(loja: str) -> Path:
    rows: List[Dict[str, Any]] = normalize_from_file(loja)
    out = vendas_pp_json(loja)
    pp_dir(loja).mkdir(parents=True, exist_ok=True)
    atomic_write_json(out, rows, do_backup=True)
    print(f"✓ PP gerado ({loja.upper()}): {out} | linhas={len(rows)}")
    return out

def main(argv: list[str]) -> None:
    ensure_dirs()
    loja = (argv[1] if len(argv) > 1 else "").strip().lower()
    if loja not in ("sp", "mg", "all"):
        raise SystemExit(USO)
    if loja == "all":
        _run_for("sp")
        _run_for("mg")
    else:
        _run_for(loja)

if __name__ == "__main__":
    main(sys.argv)
