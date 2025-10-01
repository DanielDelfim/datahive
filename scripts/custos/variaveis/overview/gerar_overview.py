# C:\Apps\Datahive\scripts\custos\variaveis\overview\gerar_overview.py
from __future__ import annotations
import argparse
from pathlib import Path
from app.config.paths import Regiao, Camada
from app.utils.core.io import atomic_write_json
from app.utils.costs.variable.overview.config import overview_json
from app.utils.costs.variable.overview.service import build_overview

def parse_args():
    p = argparse.ArgumentParser(description="Gera consolidated overview (frete_imposto + fatura_resumo_pp).")
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--regiao", type=str, required=True, help="sp|mg")
    p.add_argument("--camada", type=str, default="pp", help="raw|pp (default=pp)")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()

def main():
    args = parse_args()
    regiao = Regiao[args.regiao.upper()]
    camada = Camada[args.camada.upper()]

    payload = build_overview(args.ano, args.mes, regiao, camada, debug=args.debug)
    dst = Path(overview_json(args.ano, args.mes, regiao, camada))
    if args.debug:
        print(f"[ECHO] overview → {dst}")

    atomic_write_json(dst, payload, do_backup=True)

if __name__ == "__main__":
    main()
