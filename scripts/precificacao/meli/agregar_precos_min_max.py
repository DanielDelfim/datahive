# -*- coding: utf-8 -*-
"""
Agrega preços mínimo e máximo (faixas alvo de MCP) no dataset de precificação.

Uso (PowerShell):
  python .\scripts\precificacao\meli\agregar_precos_min_max.py --regiao mg
  python .\scripts\precificacao\meli\agregar_precos_min_max.py --regiao sp
  python .\scripts\precificacao\meli\agregar_precos_min_max.py --regiao all --debug
"""
from __future__ import annotations

import argparse
import json
from typing import Dict, Any, List

from app.config.paths import Regiao
from app.utils.precificacao.config import get_precificacao_dataset_path
from app.utils.precificacao.service import salvar_dataset, carregar_regras_ml
from app.utils.precificacao.precos_min_max import precos_min_max
from app.utils.precificacao.filters import is_item_full

# Validators (avisos por item)
try:
    from app.utils.precificacao.validators import validar_item_mcp, validar_item_ranges
except Exception:
    # fallbacks no-op, caso o módulo não exista ainda
    def validar_item_mcp(item: dict) -> list[str]:
        return []
    def validar_item_ranges(item: dict) -> list[str]:
        return []


def _load_doc(regiao_enum: Regiao) -> tuple[dict, str]:
    path = get_precificacao_dataset_path(regiao_enum)
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc.get("itens"), list):
        doc["itens"] = []
    return doc, str(path)


def _merge_ranges_e_warnings(item: dict, regras: dict) -> dict:
    """Calcula faixa de preço e anota warnings de validação no item."""
    res = precos_min_max(item, regras) or {}
    it2 = dict(item)
    # Persistimos com ambos os nomes (compatibilidade com páginas/serviços)
    it2["preco_minimo"] = res.get("preco_minimo")
    it2["preco_maximo"] = res.get("preco_maximo")
    it2["preco_min"] = res.get("preco_minimo")
    it2["preco_max"] = res.get("preco_maximo")

    # Validações (avisos)
    warns: list[str] = []
    warns += validar_item_mcp(it2)
    warns += validar_item_ranges(it2)
    if warns:
        it2["warnings"] = sorted(set(warns))
    else:
        it2.pop("warnings", None)
    return it2


def _processar_regiao(regiao: str, *, debug: bool = False) -> None:
    regiao_l = regiao.lower()
    regiao_enum = Regiao.SP if regiao_l == "sp" else Regiao.MG

    doc, path = _load_doc(regiao_enum)
    regras = carregar_regras_ml()

    itens_in = doc.get("itens") or []
    itens_out: List[Dict[str, Any]] = []
    full_com_faixa = 0

    for it in itens_in:
        it2 = _merge_ranges_e_warnings(it, regras)
        if is_item_full(it2) and (it2.get("preco_minimo") is not None or it2.get("preco_maximo") is not None):
            full_com_faixa += 1
        itens_out.append(it2)

    doc_out = dict(doc)
    doc_out["itens"] = itens_out

    # Persistimos pelo service (garante _meta/hash/rotação)
    salvar_dataset(doc_out, regiao_enum, keep=7, debug=debug)

    print(f"[ok] {path}")
    print(f"[stats] total_itens={len(itens_out)} | full_com_faixa={full_com_faixa}")


def main():
    ap = argparse.ArgumentParser(description="Agrega preços mínimo/máximo ao dataset de precificação.")
    ap.add_argument("--regiao", choices=["sp", "mg", "all"], required=True, help="Região alvo (ou all).")
    ap.add_argument("--debug", action="store_true", help="Imprime logs adicionais e relaxa DQ row_count=0.")
    args = ap.parse_args()

    if args.regiao == "all":
        for r in ("sp", "mg"):
            _processar_regiao(r, debug=args.debug)
    else:
        _processar_regiao(args.regiao, debug=args.debug)


if __name__ == "__main__":
    main()
