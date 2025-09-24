# app/utils/produtos/metricas.py
from __future__ import annotations
from typing import Optional, Dict, Any

from app.utils.core.produtos.units import to_float, calc_volume_m3


def volume_caixa_m3(rec: Dict[str, Any]) -> Optional[float]:
    """Calcula volume da caixa em m³ a partir das dimensões da chave 'caixa_cm'."""
    caixa = rec.get("caixa_cm") or {}
    return calc_volume_m3(caixa.get("altura"), caixa.get("largura"), caixa.get("profundidade"))


def peso_total_kit_g(rec: Dict[str, Any]) -> Optional[float]:
    """Para kits, retorna unidades_no_kit * peso_liq_g; caso contrário, peso_liq_g."""
    base = rec.get("pesos_g") or {}
    peso_liq = to_float(base.get("liq"))
    if peso_liq is None:
        return None
    unidades = rec.get("unidades_no_kit") or 1
    try:
        unidades = int(unidades)
    except Exception:
        unidades = 1
    return peso_liq * max(unidades, 1)


def custo_medio_caixa(rec: Dict[str, Any]) -> Optional[float]:
    """
    Exemplo simples: estima custo da caixa por unidade como preco_compra * fator.
    Ajuste conforme sua regra real (frete, impostos, embalagens).
    """
    preco = rec.get("preco_compra")
    try:
        preco = float(preco) if preco is not None else None
    except Exception:
        preco = None
    if preco is None:
        return None
    # placeholder: 2% do custo do item como custo de caixa/insumos
    return round(preco * 0.02, 4)
