# app/utils/precificar_woo/service.py
from __future__ import annotations
from typing import Dict, Any, List

from .aggregator import carregar_base
from .metrics import calcular_componentes, calcular_faixas_por_mcp

def _mcp_bounds(it: dict, default: dict) -> tuple[float, float]:
    d = default or {}
    mmin = float(it.get("mcp_min_override", d.get("mcp_min", 0.10)))
    mmax = float(it.get("mcp_max_override", d.get("mcp_max", 0.25)))
    return mmin, mmax

def _preco_base(it: dict) -> float:
    # Nesta aba não há “preço atual”; usamos o preço alvo (médio) como base de cálculo dos componentes
    pc = float(it.get("preco_compra") or 0.0)
    return pc  # simples: pode trocar para média da faixa se preferir

def construir_dataset() -> Dict[str, Any]:
    doc = carregar_base()
    regras = (doc.get("regras") or {})
    default = regras.get("default") or {}

    saida = []
    for it in doc.get("itens", []):
        pc = float(it.get("preco_compra") or 0.0)

        # limites (overrides > default)
        mmin = float(it.get("mcp_min_override", default.get("mcp_min", 0.10)))
        mmax = float(it.get("mcp_max_override", default.get("mcp_max", 0.25)))

        faixas = calcular_faixas_por_mcp(pc, mmin, mmax, default, it)   # <-- NOVO: usa custos sobre o preço
        # escolha de preço_base para componentes: o mínimo (conservador) ou a média, como preferir
        preco_base = faixas["preco_minimo"] or faixas["preco_maximo"] or pc

        comps = calcular_componentes(pc, default, preco_base, it)

        mcp_abs_min = (faixas["preco_minimo"] - pc) if faixas["preco_minimo"] else None
        mcp_abs_max = (faixas["preco_maximo"] - pc) if faixas["preco_maximo"] else None

        it2 = {
            **it,
            **faixas,
            **comps,
            "mcp_min": mmin, "mcp_max": mmax,
            "mcp_abs_min": round(mcp_abs_min, 2) if mcp_abs_min is not None else None,
            "mcp_abs_max": round(mcp_abs_max, 2) if mcp_abs_max is not None else None,
        }
        saida.append(it2)

    return {**doc, "itens": saida}

# CONTRATOS PÚBLICOS
def faixas_por_gtin(gtin: str) -> Dict[str, Any]:
    doc = construir_dataset()
    for it in doc.get("itens", []):
        if it.get("gtin") == str(gtin):
            return it
    return {}

def resumo_precificacao() -> List[Dict[str, Any]]:
    doc = construir_dataset()
    return [{
        "gtin": it.get("gtin"),
        "title": it.get("title"),
        "preco_compra": it.get("preco_compra"),
        "preco_minimo": it.get("preco_minimo"),
        "preco_maximo": it.get("preco_maximo"),
        "mcp_min": it.get("mcp_min"),
        "mcp_max": it.get("mcp_max"),
    } for it in doc.get("itens", [])]
