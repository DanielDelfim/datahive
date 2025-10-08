from __future__ import annotations

def weighted_estimate_30(s7: float, s15: float, s30: float, w=(0.45, 0.35, 0.20)) -> float:
    """Estimativa de consumo para 30 dias usando pesos 7/15/30."""
    return max(0.0, w[0]*s7 + w[1]*s15 + w[2]*s30)

def daily_rate_from_30(est_30: float) -> float:
    """Taxa diária média inferida a partir da estimativa de 30 dias."""
    return est_30 / 30.0 if est_30 > 0 else 0.0

def estimate_30_60(s7: float, s15: float, s30: float, w=(0.45, 0.35, 0.20)) -> dict:
    """Retorna estimativas de 30 e 60 dias + taxa diária."""
    e30 = weighted_estimate_30(s7, s15, s30, w)
    dr = daily_rate_from_30(e30)
    e60 = dr * 60.0
    return {"estimado_30": e30, "estimado_60": e60, "taxa_diaria": dr}

def estoque_pos_delay(estoque_atual: float | None, taxa_diaria: float, lead_days: int) -> float | None:
    """
    Estoque previsto após consumir pelo lead time. Se negativo, clamp em 0.
    Retorna None se estoque_atual não for informado.
    """
    if estoque_atual is None:
        return None
    restante = estoque_atual - (taxa_diaria * lead_days)
    return max(0.0, restante)
