# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, Optional, Tuple

from app.utils.precificacao.metrics import (
    custo_fixo_full,         # tier por preço
    carregar_regras_ml,      # lê YAML
    _to_num,  # helpers já existentes no módulo
)

def _is_full(item: Dict[str, Any]) -> bool:
    lt = (item.get("logistic_type") or "").strip().lower()
    return lt.startswith("fulfillment") or bool(item.get("is_full"))

def _pcts_yaml_por_logistica(regras: Dict[str, Any], item: Dict[str, Any]) -> Tuple[float,float,float]:
    """retorna (comissao_pct, imposto_pct, marketing_pct) conforme YAML + logística (bruto)."""
    default = (regras or {}).get("default", {}) or {}
    cfgc = (regras or {}).get("comissao", {}) or {}
    if _is_full(item):
        c = cfgc.get("full") or cfgc.get("fulfillment")
    else:
        c = cfgc.get("seller")
    if c is None:
        c = cfgc.get("classico_pct", default.get("comissao_pct"))
    comissao = float(c or 0.0)
    imposto  = float(default.get("imposto_pct")   or 0.0)
    market   = float(default.get("marketing_pct") or 0.0)
    return comissao, imposto, market

def _frete_sobre_custo(item: Dict[str, Any], regras: Dict[str, Any]) -> float:
    """frete: usa campo do item; senão deriva de default.frete_pct_sobre_custo * preco_compra"""
    v = _to_num(item.get("frete_full"))
    if v is None:
        v = _to_num(item.get("frete_sobre_custo"))
    if v is None:
        pc = _to_num(item.get("preco_compra")) or 0.0
        fr = float((regras or {}).get("default", {}).get("frete_pct_sobre_custo") or 0.0)
        v = pc * fr
    return float(v or 0.0)

def _alocar_subsidio_valor(subs: float, c_brl: float, m_brl: float, i_brl: float,
                           ordem: list[str]) -> Tuple[float,float,float,Dict[str,float]]:
    """aloca subsídio (R$) nas taxas na ordem desejada (sem negativar)."""
    rem = max(0.0, float(subs or 0.0))
    c, m, i = float(c_brl or 0.0), float(m_brl or 0.0), float(i_brl or 0.0)
    alloc = {"comissao": 0.0, "marketing": 0.0, "imposto": 0.0}
    for campo in ordem:
        if rem <= 0:
            break
        if campo == "comissao":
            ded = min(rem, c)
            c -= ded
            rem -= ded
            alloc["comissao"] += ded
        elif campo == "marketing":
            ded = min(rem, m)
            m -= ded
            rem -= ded
            alloc["marketing"] += ded
        elif campo == "imposto":
            ded = min(rem, i)
            i -= ded
            rem -= ded
            alloc["imposto"] += ded
    return c, m, i, alloc

def simular_mcp_item(
    item: Dict[str, Any],
    *,
    preco_venda: float,
    subsidio_valor: float = 0.0,
    regras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Simula MCP com base no item + preço escolhido + subsídio em R$.
    - Percentuais (comissão/imposto/marketing) vêm do YAML por logística (bruto).
    - Custo fixo FULL é por faixa (tier) do preço simulado.
    - Frete vem do item ou default (pct * preco_compra).
    Retorna: dict com mcp_abs, mcp_pct e decomposição.
    """
    regras = regras or carregar_regras_ml()
    preco = float(preco_venda)
    if preco <= 0:
        return {"mcp_abs": None, "mcp_pct": None, "error": "preco_venda_invalido"}

    pc = _to_num(item.get("preco_compra"))
    if pc is None:
        return {"mcp_abs": None, "mcp_pct": None, "error": "preco_compra_ausente"}

    com_pct, imp_pct, mkt_pct = _pcts_yaml_por_logistica(regras, item)
    # custos variáveis brutos (antes do subsídio)
    com_b = com_pct * preco
    imp_b = imp_pct * preco
    mkt_b = mkt_pct * preco

    # aplica subsídio (em valor) nas taxas conforme default.aplicar_subsidio_em (ou só comissao)
    aplicar_em = (regras or {}).get("default", {}).get("aplicar_subsidio_em") or ["comissao"]
    if isinstance(aplicar_em, str):
        aplicar_em = [aplicar_em]
    com_r, mkt_r, imp_r, alloc = _alocar_subsidio_valor(subsidio_valor, com_b, mkt_b, imp_b, aplicar_em)

    frete = _frete_sobre_custo(item, regras)
    fixo  = custo_fixo_full(preco, regras) if _is_full(item) else 0.0

    custos_totais = pc + frete + fixo + com_r + mkt_r + imp_r
    mcp_abs = preco - custos_totais
    mcp_pct = (mcp_abs / preco) if preco > 0 else None

    return {
        "preco_venda": preco,
        "preco_compra": pc,
        "frete": frete,
        "custo_fixo_full": fixo,
        "comissao_pct_bruta": com_pct,
        "imposto_pct": imp_pct,
        "marketing_pct": mkt_pct,
        "comissao_brl": com_r,
        "imposto_brl": imp_r,
        "marketing_brl": mkt_r,
        "subsidio_valor": float(subsidio_valor or 0.0),
        "subsidio_alocado": alloc,
        "mcp_abs": mcp_abs,
        "mcp_pct": mcp_pct,
    }
