# C:\Apps\Datahive\app\utils\precificacao\precos_min_max.py
from __future__ import annotations
from typing import Any, Dict, Optional

from app.utils.precificacao.metrics import custo_fixo_full  # tier FULL (quando não há override)

# -----------------------------
# Helpers
# -----------------------------
def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _num_or_none(x: Any) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None

def _pick_override(item: Dict[str, Any], key_base: str) -> Optional[float]:
    """Ex.: key_base='comissao_pct' -> lê 'comissao_pct_override' do item."""
    return _num_or_none(item.get(f"{key_base}_override"))

def _is_full(item: Dict[str, Any]) -> bool:
    lt = (item.get("logistic_type") or "").strip().lower()
    return lt.startswith("fulfillment") or bool(item.get("is_full"))

# -----------------------------
# Percentuais brutos (para metas)
# -----------------------------
def _sum_pcts_para_faixas(regras: Dict[str, Any], item: Dict[str, Any]) -> float:
    """
    Soma de percentuais para inverter P (metas min/max).
    **Ignora subsídio** e usa percentuais *brutos*.
    Agora respeita overrides no item; na falta, cai no YAML.
    """
    default = regras.get("default") or {}
    comissao_yaml = regras.get("comissao") or {}

    # Imposto / marketing: override > item > YAML default
    imp_ovr = _pick_override(item, "imposto_pct")
    mkt_ovr = _pick_override(item, "marketing_pct")

    imposto_pct   = imp_ovr if imp_ovr is not None else _num_or_none(item.get("imposto_pct"))
    if imposto_pct is None:
        imposto_pct = float(default.get("imposto_pct") or 0.0)

    marketing_pct = mkt_ovr if mkt_ovr is not None else _num_or_none(item.get("marketing_pct"))
    if marketing_pct is None:
        marketing_pct = float(default.get("marketing_pct") or 0.0)

    # Comissão: override > YAML por logística
    com_ovr = _pick_override(item, "comissao_pct")
    if com_ovr is not None:
        comissao_pct = float(com_ovr)
    else:
        if _is_full(item):
            com_base = comissao_yaml.get("full") or comissao_yaml.get("fulfillment")
        else:
            com_base = comissao_yaml.get("seller")
        if com_base is None:
            com_base = comissao_yaml.get("classico_pct", default.get("comissao_pct"))
        comissao_pct = float(com_base or 0.0)

    return float(imposto_pct) + float(marketing_pct) + float(comissao_pct)

# -----------------------------
# Frete para metas (com override)
# -----------------------------
def _frete_sobre_custo(item: Dict[str, Any], regras: Dict[str, Any]) -> float:
    """
    Prioriza overrides; depois campos do item; por fim default (pct sobre custo).
    """
    v = _pick_override(item, "frete_full")
    if v is None:
        v = _pick_override(item, "frete_sobre_custo")
    if v is None:
        v = _num_or_none(item.get("frete_full"))
    if v is None:
        v = _num_or_none(item.get("frete_sobre_custo"))
    if v is None:
        pc = _num_or_none(item.get("preco_compra")) or 0.0
        default = regras.get("default") or {}
        frete_pct = float(default.get("frete_pct_sobre_custo") or 0.0)
        v = pc * frete_pct
    return float(v or 0.0)

# -----------------------------
# Resolver preço dado um MCP-alvo
# -----------------------------
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

    Observações:
    - Só aplicável a FULL.
    - **Não** inclui subsídio nas metas.
    - Se houver `custo_fixo_full_override`, ele é usado como fixo constante.
    """
    if not _is_full(item):
        return None

    sum_pcts = _sum_pcts_para_faixas(regras, item)   # já considera overrides
    k = 1.0 - sum_pcts
    if k - alvo_mcp <= 0:
        return None

    frete = _frete_sobre_custo(item, regras)
    base = preco_compra + frete

    # Se houver fixo override, a equação vira linear (não depende de P)
    fixo_ovr = _pick_override(item, "custo_fixo_full")
    if fixo_ovr is not None:
        p = (base + float(fixo_ovr)) / (k - alvo_mcp)
        return round(p, 2)

    # Chute inicial sem fixo
    p = base / (k - alvo_mcp)

    # Itera aplicando o tier do FULL
    for _ in range(max_iter):
        fixo = custo_fixo_full(p, regras)  # sem override → tier por preço candidato
        novo_p = (base + fixo) / (k - alvo_mcp)
        if abs(novo_p - p) <= 0.01:
            p = novo_p
            break
        p = novo_p

    return round(p, 2)

# -----------------------------
# Público
# -----------------------------
def _clamp01(x):
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    return max(0.0, min(1.0, v))

def precos_min_max(item: Dict[str, Any], regras: Dict[str, Any]) -> Dict[str, Optional[float]]:
    if not _is_full(item):
        return {"preco_minimo": None, "preco_maximo": None}

    pc = _as_float(item.get("preco_compra"))
    if pc is None:
        return {"preco_minimo": None, "preco_maximo": None}

    default = regras.get("default") or {}
    # 1) lê do YAML (defaults)
    mcp_min = float(default.get("mcp_min") or 0.0)
    mcp_max = float(default.get("mcp_max") or 0.0)
    # 2) overrides por item (injetados pelo service)
    ov_min = _pick_override(item, "mcp_min")
    ov_max = _pick_override(item, "mcp_max")
    if ov_min is not None:
        mcp_min = _clamp01(ov_min)
    if ov_max is not None:
        mcp_max = _clamp01(ov_max)
    # sanity: min <= max
    if mcp_min is None or mcp_max is None or mcp_min > mcp_max:
        return {"preco_minimo": None, "preco_maximo": None}

    pmin = _resolver_preco_por_mcp_alvo(pc, mcp_min, regras, item=item)
    pmax = _resolver_preco_por_mcp_alvo(pc, mcp_max, regras, item=item)

    return {"preco_minimo": pmin, "preco_maximo": pmax}

