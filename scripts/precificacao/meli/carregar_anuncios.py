from __future__ import annotations
import argparse
from app.utils.precificacao.service import construir_dataset_base, salvar_dataset

def parse_args():
    ap = argparse.ArgumentParser(description="Carrega anúncios PP (via service) e monta dataset base de precificação.")
    ap.add_argument("--regiao", choices=["sp", "mg"], required=True)
    return ap.parse_args()

def main():
    args = parse_args()
    doc = construir_dataset_base(args.regiao)  # via service de Anúncios
    out = salvar_dataset(doc, args.regiao)
    print(f"[ok] Dataset base gerado: {out}")
    print(f"[stats] itens={len(doc.get('itens', []))}")

if __name__ == "__main__":
    main()
