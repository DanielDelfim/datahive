from __future__ import annotations
import argparse
from pathlib import Path
import json

from app.utils.precificacao.service import enriquecer_preco_compra, salvar_dataset
from app.utils.precificacao.config import get_precificacao_dataset_path

def parse_args():
    ap = argparse.ArgumentParser(description="Enriquece dataset de precificação com preço de compra (via service de Produtos).")
    ap.add_argument("--regiao", choices=["sp", "mg"], required=True)
    return ap.parse_args()

def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def main():
    args = parse_args()
    in_path = get_precificacao_dataset_path(args.regiao)
    if not in_path.exists():
        raise FileNotFoundError(f"Dataset base não encontrado: {in_path}. Rode primeiro carregar_anuncios.py --regiao {args.regiao}")

    doc = _read_json(in_path)
    doc2 = enriquecer_preco_compra(doc)
    out = salvar_dataset(doc2, args.regiao)

    # estatísticas básicas
    itens = doc2.get("itens", [])
    ok = sum(1 for it in itens if it.get("preco_compra") is not None)
    print(f"[ok] Dataset enriquecido: {out}")
    print(f"[stats] itens={len(itens)} | com_preco_compra={ok}")

if __name__ == "__main__":
    main()
