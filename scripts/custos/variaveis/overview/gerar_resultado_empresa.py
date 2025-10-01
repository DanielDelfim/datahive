# C:\Apps\Datahive\scripts\custos\variaveis\overview\gerar_resultado_empresa.py
from __future__ import annotations
import argparse
from pathlib import Path
from app.config.paths import Regiao, Camada
from app.utils.core.io import atomic_write_json
from app.utils.costs.variable.overview.config import overview_json
from app.utils.costs.variable.overview.service import build_resultado_empresa

def parse_args():
    p = argparse.ArgumentParser(description="Gera resultado_empresa.json (payload executivo consolidado).")
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

    payload = build_resultado_empresa(args.ano, args.mes, regiao, camada, debug=args.debug)
    dst = Path(overview_json(args.ano, args.mes, regiao, camada)).with_name("resultado_empresa.json")
    if args.debug:
        print(f"[ECHO] resultado_empresa → {dst}")

    atomic_write_json(dst, payload, do_backup=True)

if __name__ == "__main__":
    main()
