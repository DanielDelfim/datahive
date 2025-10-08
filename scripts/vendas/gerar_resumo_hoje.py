# scripts/vendas/gerar_resumo_hoje.py
from __future__ import annotations
import argparse
import sys

from app.config.paths import vendas_resumo_hoje_json
from app.utils.core.io import atomic_write_json
from app.utils.vendas.meli.service import get_resumo_hoje

USO = "Uso: python -m scripts.vendas.gerar_resumo_hoje [sp|mg]"

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("loja", choices=("sp", "mg"))
    ap.add_argument("--materializar", action="store_true",
                    help="Se presente, grava resumo_today.json; caso contrário, só imprime/loga.")
    args = ap.parse_args(argv[1:])

    payload = get_resumo_hoje(args.loja)

    if args.materializar:
        out = vendas_resumo_hoje_json(args.loja)
        atomic_write_json(out, payload, do_backup=True)
        print(f"[OK] resumo_today materializado: {out}")
    else:
        print(f"[OK] Resumo de hoje em memória (loja={args.loja}); nada gravado.")
        print(payload)  # ou um resumo enxuto

if __name__ == "__main__":
    import sys
    main(sys.argv)
