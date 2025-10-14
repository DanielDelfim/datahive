#C:\Apps\Datahive\app\utils\precificacao\simulator.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, Optional, Tuple

from app.utils.precificacao.metrics import (
    custo_fixo_full,         # tier por preço
    carregar_regras_ml,      # lê YAML
    _to_num,                 # helpers do módulo de métricas
)

# -----------------------
# helpers locais
# -----------------------
def _clamp01(x: Optional[float]) -> float:
    if x is None:
        return 0.0
    try:
        x = float(x)
    except Exception:
        return 0.0
    return 0.0 if x < 0 else (1.0 if x > 1 else x)

def _num_or_none(x):
    try:
        return float(x)
    except Exception:
        return None

def _pick_override(item: Dict[str, Any], base: str) -> Optional[float]:
    # ex.: base="comissao_pct" -> lê "comissao_pct_override"
    return _num_or_none(item.get(f"{base}_override"))

def _is_full(item: Dict[str, Any]) -> bool:
    lt = (item.get("logistic_type") or "").strip().lower()
    return lt.startswith("fulfillment") or bool(item.get("is_full"))

# -----------------------
# percentuais por logística (com override)
# -----------------------
def _pcts_yaml_por_logistica(regras: Dict[str, Any], item: Dict[str, Any]) -> Tuple[float, float, float]:
    """
    retorna (comissao_pct, imposto_pct, marketing_pct) já BRUTOS,
    usando override do item se existir; senão, YAML por logística.
    """
    default = (regras or {}).get("default", {}) or {}
    cfg_comissao = (regras or {}).get("comissao", {}) or {}

    # comissão base por logística
    if _is_full(item):
        com_base = cfg_comissao.get("full") or cfg_comissao.get("fulfillment") \
                   or cfg_comissao.get("classico_pct") or default.get("comissao_pct")
    else:
        com_base = cfg_comissao.get("seller") or cfg_comissao.get("classico_pct") \
                   or default.get("comissao_pct")

    # overrides (se vierem já no item via service.aplicar_overrides_no_documento)
    ov_com = _pick_override(item, "comissao_pct")
    ov_imp = _pick_override(item, "imposto_pct")
    ov_mkt = _pick_override(item, "marketing_pct")

    com = _clamp01(ov_com if ov_com is not None else _to_num(item.get("comissao_pct")) or float(com_base or 0.0))
    imp = _clamp01(ov_imp if ov_imp is not None else _to_num(item.get("imposto_pct"))  or float(default.get("imposto_pct")   or 0.0))
    mkt = _clamp01(ov_mkt if ov_mkt is not None else _to_num(item.get("marketing_pct")) or float(default.get("marketing_pct") or 0.0))
    return com, imp, mkt

# -----------------------
# frete (com override)
# -----------------------
def _frete_sobre_custo(item: Dict[str, Any], regras: Dict[str, Any]) -> float:
    """
    frete: prioriza *_override; depois campos do item; por fim default.frete_pct_sobre_custo * preco_compra.
    """
    v = _pick_override(item, "frete_full")
    if v is None:
        v = _pick_override(item, "frete_sobre_custo")
    if v is None:
        v = _to_num(item.get("frete_full"))
    if v is None:
        v = _to_num(item.get("frete_sobre_custo"))
    if v is None:
        pc = _to_num(item.get("preco_compra")) or 0.0
        fr = float((regras or {}).get("default", {}).get("frete_pct_sobre_custo") or 0.0)
        v = pc * fr
    return float(v or 0.0)

# -----------------------
# subsídio
# -----------------------
def _alocar_subsidio_valor(subs: float, c_brl: float, m_brl: float, i_brl: float,
                           ordem: list[str]) -> Tuple[float, float, float, Dict[str, float]]:
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

# -----------------------
# função pública
# -----------------------
def simular_mcp_item(
    item: Dict[str, Any],
    *,
    preco_venda: float,
    subsidio_valor: float = 0.0,
    regras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Simula MCP com base no item + preço escolhido + subsídio em R$.

    HONRA OVERRIDES NO ITEM:
      - custo_fixo_full_override (R$)
      - comissao_pct_override, imposto_pct_override, marketing_pct_override
      - frete_full_override / frete_sobre_custo_override

    Retorna: dict com mcp_abs, mcp_pct e decomposição.
    """
    regras = regras or carregar_regras_ml()
    preco = float(preco_venda)
    if preco <= 0:
        return {"mcp_abs": None, "mcp_pct": None, "error": "preco_venda_invalido"}

    pc = _to_num(item.get("preco_compra"))
    if pc is None:
        return {"mcp_abs": None, "mcp_pct": None, "error": "preco_compra_ausente"}

    # percentuais (brutos) respeitando overrides
    com_pct, imp_pct, mkt_pct = _pcts_yaml_por_logistica(regras, item)

    # custos variáveis brutos, antes de subsídio
    com_b = com_pct * preco
    imp_b = imp_pct * preco
    mkt_b = mkt_pct * preco

    # alocação do subsídio
    aplicar_em = (regras or {}).get("default", {}).get("aplicar_subsidio_em") or ["comissao"]
    if isinstance(aplicar_em, str):
        aplicar_em = [aplicar_em]
    com_r, mkt_r, imp_r, alloc = _alocar_subsidio_valor(subsidio_valor, com_b, mkt_b, imp_b, aplicar_em)

    # frete (com override)
    frete = _frete_sobre_custo(item, regras)

    # custo fixo FULL (com override)
    ov_fix = _pick_override(item, "custo_fixo_full")  # R$/unidade
    if _is_full(item):
        fixo = float(ov_fix) if (ov_fix is not None) else float(custo_fixo_full(preco, regras))
    else:
        fixo = 0.0

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
