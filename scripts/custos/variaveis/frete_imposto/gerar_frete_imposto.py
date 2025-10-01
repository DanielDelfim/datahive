from __future__ import annotations
import argparse
from pathlib import Path
from app.config.paths import Regiao, Camada
from app.utils.core.io import atomic_write_json
from app.utils.costs.variable.frete_imposto.config import frete_imposto_json
from app.utils.costs.variable.frete_imposto.service import calcular_frete_imposto

def parse_args():
    p = argparse.ArgumentParser(description="Calcula frete e imposto a partir do resumo_transacoes.json")
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--regiao", type=str, required=True)
    p.add_argument("--camada", type=str, default="pp")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()

def main():
    args = parse_args()
    regiao = Regiao[args.regiao.upper()]
    camada = Camada[args.camada.upper()]

    payload = calcular_frete_imposto(args.ano, args.mes, regiao, camada, debug=args.debug)
    dst = Path(frete_imposto_json(args.ano, args.mes, regiao, camada))
    if args.debug:
        print(f"[ECHO] destino → {dst}")
    atomic_write_json(dst, payload, do_backup=True)

if __name__ == "__main__":
    main()
