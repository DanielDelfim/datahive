from __future__ import annotations

from typing import Any, Dict, Optional
from copy import deepcopy

from .metrics import (
    calcular_componentes,
    fixo_por_preco,
    frete_pct_sobre_custo,
    mcp_bounds,
    preco_para_mcp_alvo_bandas,
    _nz,  # uso interno
)


def merge_params(regras_base: Dict[str, Any], knobs: Optional[Dict[str, Any]], *, full: bool) -> Dict[str, Any]:
    """
    Mescla 'knobs' (overrides em memória) sobre as regras_base.
    knobs aceitos (todos opcionais):
      - imposto_pct, marketing_pct, take_rate_pct  (frações)
      - frete_pct_sobre_custo                      (fração)
      - tarifa_fixa_brl                            (R$ fixo; trava fixo e ignora faixas)
      - mcp_min, mcp_max                           (frações; metas para preços sugeridos)
      - preco_venda_override                       (travamento de preço final p/ simulação)
    """
    base = deepcopy(regras_base)
    perfil = "full" if full else "nao_full"
    knobs = knobs or {}

    def maybe_set(sec: str, key: str):
        if key in knobs and knobs[key] is not None:
            base.setdefault(sec, {})[key] = knobs[key]

    # percentuais e frete % sobre custo
    for sec, key in (("default", "imposto_pct"),
                     ("default", "marketing_pct")):
        maybe_set(sec, key)

    if "take_rate_pct" in knobs and knobs["take_rate_pct"] is not None:
        base.setdefault("comissao", {})["classico_pct"] = knobs["take_rate_pct"]

    maybe_set("default", "frete_pct_sobre_custo")
    maybe_set(perfil, "frete_pct_sobre_custo")  # permite override por perfil

    # metas
    for key in ("mcp_min", "mcp_max"):
        maybe_set("default", key)
        maybe_set(perfil, key)

    # fixa um valor absoluto de tarifa por venda (ignora faixas)
    if "tarifa_fixa_brl" in knobs and knobs["tarifa_fixa_brl"] is not None:
        base.setdefault(perfil, {})["__tarifa_fixa_brl_forcada__"] = knobs["tarifa_fixa_brl"]

    # preço travado (não altera regras; usado no simular_item)
    if "preco_venda_override" in knobs and knobs["preco_venda_override"] is not None:
        base.setdefault("__sim__", {})["preco_venda_override"] = knobs["preco_venda_override"]

    return base


def simular_item(item: Dict[str, Any], regras_base: Dict[str, Any], knobs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Enriquecimento do item com métricas usando 'knobs' em memória (sem alterar YAML).
    - Aplica overrides com merge_params();
    - Se houver tarifa_fixa_brl forçada, ignora faixas;
    - Calcula preços sugeridos min/max a partir das metas (se presentes).
    Retorna um NOVO dict (não altera o original).
    """
    # shallow copy do item (não mutar o original)
    out = dict(item)
    preco = _nz(out.get("preco_venda"))
    custo = _nz(out.get("preco_custo"))
    full = bool(out.get("full"))

    regras = merge_params(regras_base, knobs, full=full)

    # preco travado pelo knob (ex.: campanha do ML)
    preco_override = regras.get("__sim__", {}).get("preco_venda_override")
    if preco_override is not None:
        try:
            preco = float(preco_override)
            out["preco_venda"] = preco
        except (TypeError, ValueError):
            pass

    # percentuais
    imposto_pct   = _nz(regras["default"].get("imposto_pct"))
    marketing_pct = _nz(regras["default"].get("marketing_pct"))
    comissao_pct  = _nz(regras["comissao"].get("classico_pct"))

    # componentes percentuais (frete_pct=0; frete absoluto abaixo)
    comp = calcular_componentes(
        preco_venda=preco,
        custo=custo,
        imposto_pct=imposto_pct,
        marketing_pct=marketing_pct,
        take_rate_pct=comissao_pct,
        frete_pct=0.0,
    )

    # frete % sobre custo (perfil/default)
    frete_pct = frete_pct_sobre_custo(regras, full)
    frete_abs = custo * frete_pct

    # fixo por faixa OU fixo travado
    perfil = "full" if full else "nao_full"
    fixo_forcado = regras.get(perfil, {}).get("__tarifa_fixa_brl_forcada__")
    if fixo_forcado is not None:
        try:
            fixo_brl = float(fixo_forcado)
        except (TypeError, ValueError):
            fixo_brl = 0.0
    else:
        fixo_brl = fixo_por_preco(regras.get(perfil, {}), preco)

    # MC final & MCP
    mc_valor_final = comp["mc_valor"] - frete_abs - fixo_brl
    mcp_pct_final = (mc_valor_final / preco) if preco else 0.0

    # preços sugeridos por metas (se existirem)
    m_min, m_max = mcp_bounds(regras, full)
    preco_min = preco_para_mcp_alvo_bandas(regras, full, custo, m_min) if m_min is not None else None
    preco_max = preco_para_mcp_alvo_bandas(regras, full, custo, m_max) if m_max is not None else None

    # monta saída
    out.update({
        "imposto_valor": comp["imposto_valor"],
        "marketing_valor": comp["marketing_valor"],
        "tarifa_canal_valor": comp["tarifa_canal_valor"],
        "frete_valor": frete_abs,
        "tarifa_fixa_brl": fixo_brl,
        "mc_valor": mc_valor_final,
        "mcp_pct": mcp_pct_final,
        "preco_sugerido_min": preco_min if m_min is not None else None,
        "mcp_min_inviavel": ((preco_min is None) if m_min is not None else None),
        "preco_sugerido_max": preco_max if m_max is not None else None,
        "mcp_max_inviavel": ((preco_max is None) if m_max is not None else None),
    })
    return out
