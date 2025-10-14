# app/utils/anuncios/metrics_estoque.py
from __future__ import annotations
from typing import Mapping

# pesos das janelas (7/15/30) → 40% / 35% / 25%
DEFAULT_WEIGHTS: dict[int, float] = {7: 0.40, 15: 0.35, 30: 0.25}


def _num(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def weighted_daily_sales(
    windows: Mapping[str | int, Mapping],
    weights: Mapping[int, float] = DEFAULT_WEIGHTS,
) -> float:
    """
    Calcula o consumo médio diário ponderado a partir de janelas 7/15/30.
    Espera um shape do tipo:
      windows = {
        "7":  {"qty_total": N7, ...},
        "15": {"qty_total": N15, ...},
        "30": {"qty_total": N30, ...}
      }
    Retorna itens/dia (float). Ignora janelas ausentes.
    """
    if not isinstance(windows, Mapping):
        return 0.0

    acc = 0.0
    for d, w in weights.items():
        rec = windows.get(str(d)) or windows.get(d) or {}
        qtd = _num(rec.get("qty_total") if isinstance(rec, Mapping) else 0)
        if d > 0:
            acc += (qtd / float(d)) * float(w)
    return max(acc, 0.0)


def days_to_deplete(stock: float, daily_sales: float) -> float:
    """
    Dias estimados para zerar o estoque ao ritmo ponderado.
    Se daily_sales <= 0, retorna float('inf').
    """
    stock = _num(stock)
    daily_sales = float(daily_sales)
    if daily_sales <= 0.0:
        return float("inf")
    return stock / daily_sales


def format_coverage_days(dias: float) -> str:
    """
    Converte dias em string amigável (com ~semanas/meses quando fizer sentido).
    """
    if dias == float("inf"):
        return "∞ (sem consumo recente)"
    if dias < 1:
        horas = max(int(round(dias * 24)), 0)
        return f"~{horas} h"
    semanas = dias / 7.0
    if dias < 30:
        return f"~{int(round(dias))} dias (~{semanas:.1f} sem)"
    meses = dias / 30.0
    return f"~{int(round(dias))} dias (~{meses:.1f} m)"


def calcular_cobertura_estoque(
    estoque_total: float,
    windows: Mapping[str | int, Mapping],
    weights: Mapping[int, float] = DEFAULT_WEIGHTS,
) -> dict:
    """
    Calcula cobertura de estoque usando pesos 40/35/25 nas janelas 7/15/30.
    Retorna:
      {
        "consumo_dia_pond": float,   # itens/dia
        "dias_cobertura": float,     # dias (∞ se sem consumo)
        "dias_cobertura_str": str    # formato amigável
      }
    """
    consumo = weighted_daily_sales(windows, weights=weights)
    dias = days_to_deplete(estoque_total, consumo)
    return {
        "consumo_dia_pond": consumo,
        "dias_cobertura": dias,
        "dias_cobertura_str": format_coverage_days(dias),
    }
