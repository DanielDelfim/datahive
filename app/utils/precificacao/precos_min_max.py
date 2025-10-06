from __future__ import annotations
from typing import Any, Dict, Optional
from app.utils.precificacao.metrics import custo_fixo_full  # reaproveita tier FULL

def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _pct_from_item_or(yaml_value, item_value):
    try:
        if item_value is not None:
            return float(item_value)
    except Exception:
        pass
    return float(yaml_value or 0.0)

def _sum_pcts_para_faixas(regras: Dict[str, Any], item: Dict[str, Any]) -> float:
    """
    Soma de percentuais para inverter P nos preços-alvo (min/max).
    Usa SEMPRE a comissão 'bruta' por logística (ignora subsídio e pct efetivo do item),
    e usa imposto/marketing do YAML (ou do item se você quiser manter).
    """
    default = regras.get("default") or {}
    comissao_yaml = regras.get("comissao") or {}

    # imposto/marketing: do YAML (fixo para as metas)
    imposto_pct   = float(default.get("imposto_pct") or 0.0)
    marketing_pct = float(default.get("marketing_pct") or 0.0)

    # comissão BRUTA por logística
    lt = (item.get("logistic_type") or "").strip().lower()
    if lt.startswith("fulfillment"):
        comissao_base = comissao_yaml.get("full") or comissao_yaml.get("fulfillment")
    else:
        comissao_base = comissao_yaml.get("seller")

    if comissao_base is None:
        comissao_base = comissao_yaml.get("classico_pct", default.get("comissao_pct"))

    comissao_pct = float(comissao_base or 0.0)

    return imposto_pct + marketing_pct + comissao_pct


def _frete_sobre_custo(preco_compra: float, regras: Dict[str, Any]) -> float:
    default = regras.get("default") or {}
    frete_pct = float(default.get("frete_pct_sobre_custo") or 0.0)
    return preco_compra * frete_pct

def _resolver_preco_por_mcp_alvo(
    preco_compra: float,
    alvo_mcp: float,
    regras: Dict[str, Any],
    item: Dict[str, Any],
    max_iter: int = 6,
) -> Optional[float]:
    """
    MCP = P - [preco_compra + frete + fixo(P) + (imposto+marketing+COMISSAO_BRUTA)*P]
    alvo_mcp = MCP/P  =>  (k - alvo_mcp)*P = base + fixo(P),   com k = 1 - sum_pcts
    Obs.: subsídio NÃO entra no cálculo de min/max.
    """
    lt = (item.get("logistic_type") or "").strip().lower()
    if not lt.startswith("fulfillment"):
        return None  # faixas só para FULL

    sum_pcts = _sum_pcts_para_faixas(regras, item)   # ← usa 14% (YAML) para FULL
    k = 1.0 - sum_pcts
    if k - alvo_mcp <= 0:
        return None

    frete = _frete_sobre_custo(preco_compra, regras)
    base = preco_compra + frete

    # chute inicial (sem fixo)
    p = base / (k - alvo_mcp)

    for _ in range(max_iter):
        fixo = custo_fixo_full(p, regras)  # tier por preço candidato
        novo_p = (base + fixo) / (k - alvo_mcp)
        if abs(novo_p - p) <= 0.01:
            p = novo_p
            break
        p = novo_p

    return round(p, 2)

def precos_min_max(item: Dict[str, Any], regras: Dict[str, Any]) -> Dict[str, Optional[float]]:
    if not (item.get("logistic_type") or "").strip().lower().startswith("fulfillment"):
        return {"preco_minimo": None, "preco_maximo": None}

    pc = _as_float(item.get("preco_compra"))
    if pc is None:
        return {"preco_minimo": None, "preco_maximo": None}

    default = regras.get("default") or {}
    mcp_min = float(default.get("mcp_min") or 0.0)
    mcp_max = float(default.get("mcp_max") or 0.0)

    pmin = _resolver_preco_por_mcp_alvo(pc, mcp_min, regras, item=item)
    pmax = _resolver_preco_por_mcp_alvo(pc, mcp_max, regras, item=item)

    return {"preco_minimo": pmin, "preco_maximo": pmax}
