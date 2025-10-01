# C:\Apps\Datahive\scripts\custos\variaveis\produtos\resumir_transacoes.py
from __future__ import annotations

import argparse
from pathlib import Path

from app.config.paths import Regiao, Camada  # Enums transversais
from app.utils.core.io import atomic_write_json  # atomic + backup
from app.utils.costs.variable.produtos.config import (
    resumo_transacoes_json,
    agregado_mlb_gtin_json,
)
from app.utils.costs.variable.produtos.service import (
    read_transacoes_enriquecidas,
    summarize_transacoes,
    aggregate_by_mlb_gtin,
    deduplicate_by_numero_venda,
)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resumo e agregado por (mlb, gtin) a partir do enriquecido.")
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--regiao", type=str, required=True, help="Ex.: sp, mg")
    p.add_argument("--camada", type=str, default="pp", help="raw|pp (default=pp)")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--no-dedup", action="store_true", help="Não deduplicar por numero_venda (debug/comparação)")
    return p.parse_args()

def main():
    args = parse_args()
    regiao = Regiao[args.regiao.upper()]
    camada = Camada[args.camada.upper()]

    records = read_transacoes_enriquecidas(args.ano, args.mes, regiao, camada, debug=args.debug)
    if args.debug:
        print(f"[DBG] lidos {len(records)} registros (enriquecido, bruto)")

    if not args.no_dedup:
        records = deduplicate_by_numero_venda(records)
        if args.debug:
            print(f"[DBG] após dedup por numero_venda: {len(records)} registros")

    resumo = summarize_transacoes(records)
    agregado = aggregate_by_mlb_gtin(records)

    # destinos
    dst_resumo = Path(resumo_transacoes_json(args.ano, args.mes, regiao, camada))
    dst_agregado = Path(agregado_mlb_gtin_json(args.ano, args.mes, regiao, camada))

    if args.debug:
        print(f"[ECHO] resumo → {dst_resumo}")
        print(f"[ECHO] agregado → {dst_agregado}")

    atomic_write_json(dst_resumo, resumo, do_backup=True)
    atomic_write_json(dst_agregado, agregado, do_backup=True)

if __name__ == "__main__":
    main()
