# app/utils/precificar_woo/metrics.py
from __future__ import annotations
from typing import Dict, Any, Tuple

def calcular_taxa_gateway(preco_venda: float, pct: float) -> Tuple[float, float]:
    valor = float(preco_venda or 0.0) * float(pct or 0.0)
    return valor, float(pct or 0.0)

def _frete_valor(preco_compra: float, default: dict | None, it: dict | None = None) -> float:
    it = it or {}
    d  = default or {}
    ...
    pct = float(it.get("frete_pct_sobre_custo_override") or d.get("frete_pct_sobre_custo", 0.0))
    return float(preco_compra or 0.0) * pct

def calcular_preco_por_mcp(preco_compra: float, mcp_alvo: float,
                           default: dict | None, it: dict | None = None) -> float | None:
    d  = default or {}
    it = it or {}
    imp = float(it.get("imposto_pct_override")   or d.get("imposto_pct", 0.0))
    mkt = float(it.get("marketing_pct_override") or d.get("marketing_pct", 0.0))
    mp  = float(it.get("mercado_pago_pct_override") or d.get("mercado_pago_pct", 0.0))
    frete = _frete_valor(preco_compra, d, it)
    denom = 1.0 - (imp + mkt + mp + float(mcp_alvo or 0.0))
    if denom <= 0:
        return None
    return round((float(preco_compra or 0.0) + frete) / denom, 2)

def calcular_faixas_por_mcp(preco_compra: float, mcp_min: float, mcp_max: float,
                            default: dict | None, it: dict | None = None) -> dict:
    pmin = calcular_preco_por_mcp(preco_compra, mcp_min, default, it)
    pmax = calcular_preco_por_mcp(preco_compra, mcp_max, default, it)
    return {"preco_minimo": pmin, "preco_maximo": pmax}

def calcular_componentes(preco_compra: float, regra_default: dict | None,
                         preco_base: float, it: dict | None = None) -> Dict[str, Any]:
    it = it or {}
    d  = regra_default or {}

    imposto_pct   = float(it.get("imposto_pct_override")   or d.get("imposto_pct", 0.0))
    marketing_pct = float(it.get("marketing_pct_override") or d.get("marketing_pct", 0.0))
    mp_pct        = float(it.get("mercado_pago_pct_override") or d.get("mercado_pago_pct", 0.0))

    frete = _frete_valor(preco_compra, d, it)  # <- sempre numérico

    imposto   = float(preco_base or 0.0) * imposto_pct
    marketing = float(preco_base or 0.0) * marketing_pct
    taxa_val  = float(preco_base or 0.0) * mp_pct

    return {
    "imposto": round(imposto,2), "imposto_pct": imposto_pct,
    "marketing": round(marketing,2), "marketing_pct": marketing_pct,
    "frete_sobre_custo": round(frete,2),
    "taxa_gateway": round(taxa_val,2), "taxa_gateway_pct": mp_pct,
    }
