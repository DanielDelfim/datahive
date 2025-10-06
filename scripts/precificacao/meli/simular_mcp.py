# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
import json
from app.config.paths import Regiao
from app.utils.precificacao.service import simular_mcp

def main():
    ap = argparse.ArgumentParser(description="Simular MCP informando preço e subsídio (R$).")
    ap.add_argument("--regiao", choices=["sp","mg"], required=True)
    ap.add_argument("--mlb", required=True, help="MLB do anúncio")
    ap.add_argument("--preco", type=float, required=True, help="Preço de venda a simular (R$)")
    ap.add_argument("--subsidio", type=float, default=0.0, help="Subsídio ML (R$) a abater nas taxas")
    args = ap.parse_args()

    reg = Regiao.SP if args.regiao == "sp" else Regiao.MG
    out = simular_mcp(args.mlb, reg, args.preco, args.subsidio)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
