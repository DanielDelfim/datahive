from __future__ import annotations
from typing import Dict

def calcular_imposto(valor_transacao_total: float, rate: float) -> float:
    return round((valor_transacao_total or 0.0) * (rate or 0.0), 2)

def calcular_frete(custo_total: float, rate: float) -> float:
    return round((custo_total or 0.0) * (rate or 0.0), 2)

def build_result(resumo: Dict, rates: Dict) -> Dict:
    vt = float(resumo.get("valor_transacao_total", 0.0) or 0.0)
    ct = float(resumo.get("custo_total", 0.0) or 0.0)
    imposto_rate = float(rates.get("imposto_rate", 0.0) or 0.0)
    frete_rate   = float(rates.get("frete_rate", 0.0) or 0.0)

    return {
        "quantidade_total": int(resumo.get("quantidade_total", 0) or 0),
        "valor_transacao_total": round(vt, 2),
        "custo_total": round(ct, 2),
        "imposto_rate": imposto_rate,
        "frete_rate": frete_rate,
        "imposto_calculado": calcular_imposto(vt, imposto_rate),
        "frete_calculado": calcular_frete(ct, frete_rate),
    }
