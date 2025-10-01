# C:\Apps\Datahive\scripts\custos\variaveis\produtos\dedup_e_resumir_base.py
from __future__ import annotations
import argparse
from pathlib import Path

from app.config.paths import Regiao, Camada
from app.utils.core.io import atomic_write_json
from app.utils.costs.variable.produtos.config import (
    transacoes_base_json,
    resumo_base_json,
)
from app.utils.costs.variable.produtos.service import (
    read_transacoes_base,
    deduplicate_by_numero_venda_base,
    summarize_transacoes,
)

def parse_args():
    p = argparse.ArgumentParser(
        description="Dedup por numero_venda e resumo na base; sobrescreve results_transacoes_por_produto.json."
    )
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--regiao", type=str, required=True)  # ex.: mg
    p.add_argument("--camada", type=str, default="pp")   # raw|pp
    p.add_argument("--debug", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Não escreve nada; apenas reporta antes/depois.")
    return p.parse_args()

def main():
    args = parse_args()
    regiao = Regiao[args.regiao.upper()]
    camada = Camada[args.camada.upper()]

    # 1) Ler base
    base_path = Path(transacoes_base_json(args.ano, args.mes, regiao, camada))
    base = read_transacoes_base(args.ano, args.mes, regiao, camada, debug=args.debug)
    if args.debug:
        print(f"[DBG] base: {base_path} (lidas {len(base)} linhas)")

    # 2) Deduplicar por numero_venda (mantém 1ª ocorrência; None não deduplica)
    base_dedup = deduplicate_by_numero_venda_base(base)
    if args.debug:
        repetidas = len(base) - len(base_dedup)
        print(f"[DBG] após dedup: {len(base_dedup)} linhas (removidas {repetidas})")

    # 3) Resumo (3 totais) a partir do conjunto deduplicado
    resumo = summarize_transacoes(base_dedup)

    if args.dry_run:
        print("[DRY-RUN] Nenhum arquivo foi escrito.")
        print(f"[DRY-RUN] Totais após dedup → {resumo}")
        return

    # 4) SOBRESCREVER o arquivo base com a versão deduplicada (atomic + backup)
    atomic_write_json(base_path, base_dedup, do_backup=True)
    if args.debug:
        print(f"[ECHO] sobrescrito base dedup → {base_path}")

    # 5) Gravar resumo saneado
    dst_resumo = Path(resumo_base_json(args.ano, args.mes, regiao, camada))
    atomic_write_json(dst_resumo, resumo, do_backup=True)
    if args.debug:
        print(f"[ECHO] resumo → {dst_resumo}")

if __name__ == "__main__":
    main()
