# app/utils/reposicao/metrics.py
from __future__ import annotations
from typing import Dict, Optional

Number = float | int


# -----------------------------
# Taxas diárias e projeções
# -----------------------------

def daily_rate(qty: Number | None, days: int) -> float:
    """Converte quantidade vendida em taxa diária (q/dias). Trata None e dias <=0."""
    if qty is None or days <= 0:
        return 0.0
    try:
        return float(qty) / float(days)
    except Exception:
        return 0.0


def daily_rates_from_windows(sold_by_window: Dict[int, Number | None]) -> Dict[str, float]:
    """
    Recebe vendas totais por janela {7: qtd, 15: qtd, 30: qtd} e retorna taxas diárias.
    """
    out: Dict[str, float] = {}
    for w in (7, 15, 30):
        qty = sold_by_window.get(w)
        out[f"media_diaria_{w}"] = daily_rate(qty, w)
    return out


def pick_preferred_daily_rate(rates: Dict[str, float]) -> float:
    """
    Escolhe a taxa diária “preferida” priorizando janelas mais curtas quando não = 0.
    Ordem: 7 -> 15 -> 30. Se todas 0, retorna 0.
    """
    for key in ("media_diaria_7", "media_diaria_15", "media_diaria_30"):
        v = float(rates.get(key, 0.0))
        if v > 0:
            return v
    return 0.0


def blended_daily_rate(
    rates: Dict[str, float],
    weights: Optional[Dict[int, float]] = None,
) -> float:
    """
    Taxa diária “blend” ponderada.
    Default (conforme solicitado): 7d=0.5, 15d=0.3, 30d=0.2.
    """
    w = weights or {7: 0.5, 15: 0.3, 30: 0.2}
    s = 0.0
    for win, ww in w.items():
        s += float(rates.get(f"media_diaria_{win}", 0.0)) * float(ww)
    return s


def projections_from_daily(daily: float) -> Dict[str, float]:
    """Projeta vendas para 30 e 60 dias a partir da taxa diária."""
    d = max(0.0, float(daily))
    return {
        "expectativa_30d": round(d * 30.0, 4),
        "expectativa_60d": round(d * 60.0, 4),
    }


def projection_for_days(daily: float, days: int) -> float:
    """Projeção para N dias com base na taxa diária (não negativa)."""
    if days <= 0:
        return 0.0
    return round(max(0.0, float(daily)) * float(days), 4)


def coverage_days(stock: Number | None, daily: float) -> float | None:
    """Dias de cobertura = estoque / taxa_diaria. Se taxa = 0, retorna None."""
    if stock is None:
        return None
    try:
        stock_f = float(stock)
        if daily <= 0:
            return None
        return round(stock_f / daily, 4)
    except Exception:
        return None


# -----------------------------
# Consumo e reposição
# -----------------------------

def consumo_previsto(daily: float, days: int) -> float:
    """
    Consumo projetado = taxa_diaria * days.
    """
    if daily <= 0 or days <= 0:
        return 0.0
    return round(float(daily) * float(days), 4)


def reposicao_necessaria(
    estoque_atual: float | int | None,
    daily: float,
    horizonte_dias: int = 7,
    arredondar_para_multiplo: float | int | None = None,
) -> float:
    """
    Reposição necessária para cobrir o consumo previsto no horizonte (default 7 dias).

      consumo_horizonte = daily * horizonte_dias
      reposicao = max(0, consumo_horizonte - estoque_atual)

    Se 'arredondar_para_multiplo' for informado (ex.: 6 unidades por caixa),
    a reposição é arredondada PARA CIMA ao múltiplo informado.
    """
    estoque_f = float(estoque_atual or 0.0)
    cons = consumo_previsto(daily, horizonte_dias)
    rep = max(0.0, cons - estoque_f)

    if arredondar_para_multiplo and arredondar_para_multiplo > 0:
        import math
        m = float(arredondar_para_multiplo)
        rep = math.ceil(rep / m) * m

    return round(rep, 4)


def estoque_projetado(
    estoque_atual: float | int | None,
    daily: float,
    horizonte_dias: int = 7,
) -> float:
    """
    Estoque projetado = estoque_atual - consumo_previsto(horizonte_dias),
    com regra: se resultado < 1, retorna 0 (não trabalhamos com projeção negativa).
    """
    est = float(estoque_atual or 0.0)
    cons = consumo_previsto(daily, horizonte_dias)
    proj = est - cons
    return 0.0 if proj < 1.0 else round(proj, 4)


def pacote_metricas_reposicao(
    estoque_atual: float | int | None,
    daily_preferida: float,
    horizonte_reposicao_dias: int = 7,
    arredondar_para_multiplo: float | int | None = None,
) -> dict:
    """
    Pacote padrão de métricas para o horizonte de reposição (tipicamente 7d):
      - consumo_previsto_7d
      - reposicao_necessaria_7d
      - estoque_projetado_7d (com piso; <1 => 0)
      - expectativa_30d, expectativa_60d (base taxa diária informada)
    """
    cons_7d = consumo_previsto(daily_preferida, horizonte_reposicao_dias)
    rep_7d = reposicao_necessaria(
        estoque_atual=estoque_atual,
        daily=daily_preferida,
        horizonte_dias=horizonte_reposicao_dias,
        arredondar_para_multiplo=arredondar_para_multiplo,
    )
    proj = projections_from_daily(daily_preferida)
    estoque_proj_7d = estoque_projetado(
        estoque_atual=estoque_atual,
        daily=daily_preferida,
        horizonte_dias=horizonte_reposicao_dias,
    )
    return {
        "consumo_previsto_7d": cons_7d,
        "reposicao_necessaria_7d": rep_7d,
        "estoque_projetado_7d": estoque_proj_7d,  # nunca negativo (piso aplicado)
        **proj,  # expectativa_30d, expectativa_60d
    }


# -----------------------------
# Ponderação fixa 50/30/20 e reposição 30/60d
# -----------------------------

def daily_rate_ponderada_50_30_20(rates: Dict[str, float]) -> float:
    """
    Atalho explícito para a ponderação solicitada: 7d=50%, 15d=30%, 30d=20%.
    """
    return blended_daily_rate(rates, weights={7: 0.5, 15: 0.3, 30: 0.2})


def reposicoes_para_cobertura_30_60(
    estoque_atual: float | int | None,
    rates: Dict[str, float],
    arredondar_para_multiplo: float | int | None = None,
) -> Dict[str, float]:
    """
    Calcula as reposições necessárias para garantir cobertura de 30 e 60 dias,
    usando a taxa diária PONDERADA (50/30/20) das janelas 7/15/30d.
    """
    daily_blend = daily_rate_ponderada_50_30_20(rates)
    rep_30 = reposicao_necessaria(estoque_atual, daily_blend, 30, arredondar_para_multiplo)
    rep_60 = reposicao_necessaria(estoque_atual, daily_blend, 60, arredondar_para_multiplo)
    return {
        "media_diaria_ponderada": round(daily_blend, 6),
        "consumo_previsto_30d_ponderado": projection_for_days(daily_blend, 30),
        "consumo_previsto_60d_ponderado": projection_for_days(daily_blend, 60),
        "reposicao_necessaria_30d": rep_30,
        "reposicao_necessaria_60d": rep_60,
    }
