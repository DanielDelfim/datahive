# app/utils/replacement/metrics.py
from __future__ import annotations
import math
from typing import Optional, Tuple, Dict

# ---- Parâmetros do domínio ----
DEFAULT_WEIGHTS: Tuple[float, float, float] = (0.45, 0.35, 0.20)  # 7/15/30
DEFAULT_LEAD_DAYS: int = 7

# ======================== MÉTODO CORRIGIDO =========================
def taxa_diaria_ponderada(
    sold_7: float, sold_15: float, sold_30: float,
    weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> float:
    """Média diária ponderada: (7/7, 15/15, 30/30) com pesos 0.45/0.35/0.20."""
    w7, w15, w30 = weights
    d7  = (sold_7  or 0.0) / 7.0
    d15 = (sold_15 or 0.0) / 15.0
    d30 = (sold_30 or 0.0) / 30.0
    return max(0.0, w7*d7 + w15*d15 + w30*d30)

def venda_prevista(
    sold_7: float, sold_15: float, sold_30: float,
    dias: int, weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> float:
    """Converte taxa diária ponderada em previsão para N dias."""
    return taxa_diaria_ponderada(sold_7, sold_15, sold_30, weights) * float(dias)

def venda_prevista_30d(s7: float, s15: float, s30: float,
                       weights: Tuple[float, float, float] = DEFAULT_WEIGHTS) -> float:
    return venda_prevista(s7, s15, s30, 30, weights)

def venda_prevista_60d(s7: float, s15: float, s30: float,
                       weights: Tuple[float, float, float] = DEFAULT_WEIGHTS) -> float:
    return venda_prevista(s7, s15, s30, 60, weights)

def estoque_pos_lead(
    estoque_atual: float | None,
    sold_7: float, sold_15: float, sold_30: float,
    lead_days: int = DEFAULT_LEAD_DAYS,
    weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> float | None:
    """Estoque após consumir durante o lead time. None se estoque não informado."""
    if estoque_atual is None:
        return None
    consumo = taxa_diaria_ponderada(sold_7, sold_15, sold_30, weights) * float(lead_days)
    return max(0.0, float(estoque_atual) - consumo)

def _arredonda_multiplo(qtd: float, multiplo_compra: Optional[int]) -> int:
    q = max(0.0, float(qtd or 0.0))
    if multiplo_compra and multiplo_compra > 1:
        return int(math.ceil(q / multiplo_compra) * multiplo_compra)
    return int(round(q))

def reposicao_necessaria(
    sold_7: float, sold_15: float, sold_30: float,
    estoque_atual: float | None, horizonte_dias: int,
    lead_days: int = DEFAULT_LEAD_DAYS, multiplo_compra: Optional[int] = None,
    weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> Dict[str, int | float | None]:
    """
    Compra sugerida = max(0, venda_prevista(H) - estoque_pos_lead).
    Retorna também os intermediários.
    """
    prev = venda_prevista(sold_7, sold_15, sold_30, horizonte_dias, weights)
    pos  = estoque_pos_lead(estoque_atual, sold_7, sold_15, sold_30, lead_days, weights)
    need = max(0.0, prev - (pos or 0.0))
    rep  = _arredonda_multiplo(need, multiplo_compra)

    return {
        "venda_prevista": int(round(prev)),
        "estoque_pos_lead": None if pos is None else int(round(pos)),
        "reposicao_sugerida": rep,     # ✅ novo nome
        "compra_sugerida": rep,        # 🔁 alias p/ compatibilidade
    }

def reposicao_necessaria_30d(s7, s15, s30, estoque_atual, lead_days=DEFAULT_LEAD_DAYS, multiplo_compra=None):
    return reposicao_necessaria(s7, s15, s30, estoque_atual, 30, lead_days, multiplo_compra)

def reposicao_necessaria_60d(s7, s15, s30, estoque_atual, lead_days=DEFAULT_LEAD_DAYS, multiplo_compra=None):
    return reposicao_necessaria(s7, s15, s30, estoque_atual, 60, lead_days, multiplo_compra)

# ======================== BACKWARD COMPAT ==========================
# Usado pelo aggregator atual. Agora passa a usar o método corrigido.
def estimate_30_60(s7: float, s15: float, s30: float,
                   w: Tuple[float, float, float] = DEFAULT_WEIGHTS) -> dict:
    """
    Mantém contrato antigo:
      retorna {"estimado_30", "estimado_60", "taxa_diaria"}.
    Agora: estimado_30/60 = venda_prevista_(30/60) por taxa diária ponderada.
    """
    dr = taxa_diaria_ponderada(s7, s15, s30, w)
    e30 = dr * 30.0
    e60 = dr * 60.0
    return {"estimado_30": e30, "estimado_60": e60, "taxa_diaria": dr}

# Alias para manter import existente no aggregator
def estoque_pos_delay(estoque_atual: float | None, taxa_diaria: float, lead_days: int) -> float | None:
    """Compat: antes recebia taxa_diaria pronta; mantém a assinatura."""
    if estoque_atual is None:
        return None
    return max(0.0, float(estoque_atual) - float(taxa_diaria) * float(lead_days))

__all__ = [
    # novo método/nomes
    "taxa_diaria_ponderada", "venda_prevista", "venda_prevista_30d", "venda_prevista_60d",
    "estoque_pos_lead", "reposicao_necessaria", "reposicao_necessaria_30d", "reposicao_necessaria_60d",
    # compat
    "estimate_30_60", "estoque_pos_delay",
]
