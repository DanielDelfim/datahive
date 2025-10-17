# app/utils/produtos/metrics.py
from __future__ import annotations
from typing import Optional, Dict, Any, Union

from app.utils.core.produtos.units import to_float, calc_volume_m3

import math

NumberLike = Union[float, int, str, None]

def _to_float(x: NumberLike) -> Optional[float]:
    """Converte com segurança; trata '', 'nan', None, e NaN numérico como None."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if isinstance(x, float) and math.isnan(x):
            return None
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace(",", ".")
        if s == "" or s.lower() in {"nan", "none", "null"}:
            return None
        try:
            v = float(s)
            return None if math.isnan(v) else v
        except Exception:
            return None
    return None

def normalizar_multiplo(m: NumberLike) -> Optional[int]:
    """
    Normaliza o múltiplo de compra para inteiro >= 1.
    Retorna None quando não houver valor válido.
    """
    v = _to_float(m)
    if v is None:
        return None
    try:
        mv = int(v)  # cast “seco” (2.9 -> 2). Ajuste para round se preferir.
    except Exception:
        return None
    if mv < 1:
        mv = 1
    return mv

def calcular_lotes(qtd: NumberLike, multiplo: NumberLike) -> Dict[str, Any]:
    """
    Dado 'qtd' e 'multiplo', calcula:
      - lotes_down: floor(qtd/m)
      - lotes_up  : ceil(qtd/m)
      - qtd_ajustada_down: lotes_down * m
      - qtd_ajustada_up  : lotes_up   * m
    Retorna None nos campos quando não há dados válidos.
    """
    q = _to_float(qtd)
    m_norm = normalizar_multiplo(multiplo)

    if q is None or m_norm is None:
        return {
            "lotes_down": None,
            "lotes_up": None,
            "qtd_ajustada_down": None,
            "qtd_ajustada_up": None,
            "multiplo_norm": m_norm,
        }

    ratio = q / float(m_norm)
    lotes_down = int(math.floor(ratio))
    lotes_up = int(math.ceil(ratio))
    return {
        "lotes_down": lotes_down,
        "lotes_up": lotes_up,
        "qtd_ajustada_down": lotes_down * m_norm,
        "qtd_ajustada_up": lotes_up * m_norm,
        "multiplo_norm": m_norm,
    }

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
