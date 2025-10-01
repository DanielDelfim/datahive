from __future__ import annotations
import os

def _get_rate(env_name: str, default: float) -> float:
    raw = os.environ.get(env_name)
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default

# Defaults solicitados
IMPOSTO_RATE_DEFAULT = 0.10  # 10% sobre valor_transacao_total
FRETE_RATE_DEFAULT   = 0.05  # 5%  sobre custo_total

def get_rates() -> dict:
    return {
        "imposto_rate": _get_rate("IMPOSTO_RATE", IMPOSTO_RATE_DEFAULT),
        "frete_rate": _get_rate("FRETE_RATE", FRETE_RATE_DEFAULT),
    }
