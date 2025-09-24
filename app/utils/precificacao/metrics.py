# app/utils/precificacao/metrics.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
import math


# ---------------------------
# Utilitários numéricos
# ---------------------------

def _nz(x) -> float:
    """Converte para float com fallback 0.0."""
    try:
        return float(x) if x is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def parse_frac(v: Any) -> Optional[float]:
    """
    Converte fração tolerando vírgula (ex.: '0,05' -> 0.05).
    Retorna None quando não conseguir interpretar.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------
# Núcleo: componentes percentuais (PURO)
# ---------------------------

def calcular_componentes(
    preco_venda: float,
    custo: float,
    imposto_pct: float,
    marketing_pct: float,
    take_rate_pct: float,
    frete_pct: float = 0.0,
) -> Dict[str, float]:
    """
    Decompõe custos percentuais e calcula MC e MCP%.
    Percentuais em FRAÇÃO (0.10 = 10%). 'frete_pct' aqui é sobre o preço
    (no projeto base mantemos 0 e tratamos frete absoluto à parte).
    """
    preco = _nz(preco_venda)
    c_custo = _nz(custo)

    if preco <= 0.0:
        return {
            "preco": preco,
            "custo": c_custo,
            "imposto_valor": 0.0,
            "marketing_valor": 0.0,
            "tarifa_canal_valor": 0.0,
            "frete_valor_pct": 0.0,
            "mc_valor": -c_custo,
            "mcp_pct": 0.0,
        }

    imposto_valor = preco * _nz(imposto_pct)
    marketing_valor = preco * _nz(marketing_pct)
    tarifa_canal_valor = preco * _nz(take_rate_pct)
    frete_valor_pct = preco * _nz(frete_pct)

    mc_valor = preco - (c_custo + imposto_valor + marketing_valor + tarifa_canal_valor + frete_valor_pct)
    mcp_pct = mc_valor / preco if preco else 0.0

    return {
        "preco": preco,
        "custo": c_custo,
        "imposto_valor": imposto_valor,
        "marketing_valor": marketing_valor,
        "tarifa_canal_valor": tarifa_canal_valor,
        "frete_valor_pct": frete_valor_pct,
        "mc_valor": mc_valor,
        "mcp_pct": mcp_pct,
    }


# ---------------------------
# Helpers de regra (PUROS)
# ---------------------------

def fixo_por_preco(regras_perfil: Dict[str, Any], preco: float) -> float:
    """
    Seleciona custo fixo (R$) por faixa de preço.
    regras_perfil['custo_fixo_por_unidade_brl'] = [
        {max_preco: ..., valor: ...}, ..., {otherwise: true, valor: ...}
    ]
    """
    faixas = (regras_perfil or {}).get("custo_fixo_por_unidade_brl") or []
    fixo = 0.0
    aplicado = False
    for item in faixas:
        if item.get("otherwise"):
            if not aplicado:
                try:
                    fixo = float(item.get("valor", 0.0))
                except (TypeError, ValueError):
                    fixo = 0.0
            break
        try:
            max_preco = float(item.get("max_preco", 0.0))
        except (TypeError, ValueError):
            continue
        if preco <= max_preco:
            try:
                fixo = float(item.get("valor", 0.0))
            except (TypeError, ValueError):
                fixo = 0.0
            aplicado = True
            break
    return fixo


def frete_pct_sobre_custo(regras: Dict[str, Any], full: bool) -> float:
    """
    Percentual de frete sobre o custo (fração). Procura no perfil (full/nao_full) e em default.
    Chave esperada: 'frete_pct_sobre_custo'. Fallback 0.08 (8%).
    """
    perfil = "full" if full else "nao_full"
    for sec in (perfil, "default"):
        v = parse_frac(regras.get(sec, {}).get("frete_pct_sobre_custo"))
        if v is not None and 0.0 <= v <= 1.0:
            return v
    return 0.08


def mcp_bounds(regras: Dict[str, Any], full: bool) -> Tuple[Optional[float], Optional[float]]:
    """
    Obtém (mcp_min, mcp_max) do perfil (full/nao_full) com fallback em default.
    Valores em FRAÇÃO; aceita vírgula no YAML.
    """
    perfil = "full" if full else "nao_full"
    mcp_min = None
    mcp_max = None
    for sec in (perfil, "default"):
        if mcp_min is None:
            v = parse_frac(regras.get(sec, {}).get("mcp_min", None))
            if v is not None:
                mcp_min = v
        if mcp_max is None:
            v = parse_frac(regras.get(sec, {}).get("mcp_max", None))
            if v is not None:
                mcp_max = v
    return mcp_min, mcp_max


def preco_para_mcp_alvo(
    preco_custo: float,
    a: float,
    fixo_brl: float,
    frete_abs: float,
    alvo: float,
) -> Optional[float]:
    """
    Resolve Preço para atingir MCP alvo 'alvo':
      a = 1 - (imposto_pct + marketing_pct + comissao_pct)
      b = custo + frete_abs + fixo_brl
      MCP = a - (b / Preco)  =>  Preco = b / (a - alvo), se (a - alvo) > 0
    """
    b = float(preco_custo) + float(frete_abs) + float(fixo_brl)
    denom = a - float(alvo)
    if denom <= 0:
        return None
    p = b / denom
    return round(p, 2) if p > 0 else None


def _faixas_fixos(regras_perfil: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normaliza faixas: ordena por max_preco e deixa fallback 'otherwise' por último."""
    faixas = (regras_perfil or {}).get("custo_fixo_por_unidade_brl") or []
    ordenadas = [f for f in faixas if "max_preco" in f]
    ordenadas.sort(key=lambda f: float(f.get("max_preco", math.inf)))
    fallback = [f for f in faixas if f.get("otherwise")]
    return ordenadas + fallback


def preco_para_mcp_alvo_bandas(
    regras: Dict[str, Any],
    full: bool,
    preco_custo: float,
    alvo: float,
) -> Optional[float]:
    """
    Resolve preço para MCP alvo explorando as FAIXAS (fixo depende do próprio preço).
      - frete_abs = custo * frete_pct_sobre_custo
      - a = 1 - (imposto + marketing + comissao)
      - para cada faixa: p = (custo + frete_abs + fixo) / (a - alvo)
        aceita se (p <= max_preco) ou se for 'otherwise'
    """
    alvo_f = parse_frac(alvo)
    if alvo_f is None:
        return None

    imposto = parse_frac(regras.get("default", {}).get("imposto_pct"))
    marketing = parse_frac(regras.get("default", {}).get("marketing_pct"))
    comissao = parse_frac(regras.get("comissao", {}).get("classico_pct"))
    if None in (imposto, marketing, comissao):
        return None

    a = 1.0 - (imposto + marketing + comissao)
    if a - alvo_f <= 0:
        return None

    frete_pct = frete_pct_sobre_custo(regras, full)
    frete_abs = float(preco_custo) * float(frete_pct)
    perfil = "full" if full else "nao_full"
    faixas = _faixas_fixos(regras.get(perfil, {}))

    for fx in faixas:
        fixo = parse_frac(fx.get("valor"))
        if fixo is None:
            continue
        p = (float(preco_custo) + frete_abs + fixo) / (a - alvo_f)
        if p <= 0:
            continue
        p = round(p, 2)
        if "max_preco" in fx:
            try:
                max_preco = float(fx["max_preco"])
            except (TypeError, ValueError):
                max_preco = math.inf
            if p <= max_preco + 1e-9:
                return p
        else:
            # fallback 'otherwise'
            return p
    return None


# ---------------------------
# Utilitário “tudo em um” (PURO)
# ---------------------------

def enriquecer_item_com_metricas(item: Dict[str, Any], regras: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lê 'preco_venda', 'preco_custo' e 'full' do item; aplica:
      - percentuais (imposto, marketing, comissão)
      - fixo por faixa (YAML)
      - frete % sobre custo (YAML)
      - preços sugeridos para metas do YAML (mcp_min/mcp_max) usando faixas
    Atualiza e retorna o próprio dict.
    """
    preco = _nz(item.get("preco_venda"))
    custo = _nz(item.get("preco_custo"))
    full = bool(item.get("full"))

    imposto_pct   = _nz(regras["default"]["imposto_pct"])
    marketing_pct = _nz(regras["default"]["marketing_pct"])
    comissao_pct  = _nz(regras["comissao"]["classico_pct"])

    comp = calcular_componentes(
        preco_venda=preco,
        custo=custo,
        imposto_pct=imposto_pct,
        marketing_pct=marketing_pct,
        take_rate_pct=comissao_pct,
        frete_pct=0.0,  # frete absoluto tratado abaixo
    )

    fixo_brl = fixo_por_preco(regras["full"] if full else regras["nao_full"], preco)
    frete_pct = frete_pct_sobre_custo(regras, full)
    frete_abs = custo * frete_pct

    # --------- NOVO: subsídio de tarifa (rebate) ----------
    # regra: subsidio_brl = max(price - rebate_price, 0)
    bruto_price   = _nz(item.get("price"))
    bruto_rebate  = _nz(item.get("rebate_price"))
    subsidio_brl  = max(bruto_price - bruto_rebate, 0.0) if bruto_rebate > 0.0 else 0.0

    # comissão ajustada: max(preco * comissao_pct - subsidio_brl, 0)
    tarifa_canal_ajustada = max(preco * comissao_pct - subsidio_brl, 0.0)

    # Recalcular MC final usando a comissão AJUSTADA
    mc_valor_final = preco - (
        custo + comp["imposto_valor"] + comp["marketing_valor"] + tarifa_canal_ajustada + frete_abs + fixo_brl
    )
    mcp_pct_final = (mc_valor_final / preco) if preco else 0.0

    1.0 - (imposto_pct + marketing_pct + comissao_pct)
    mcp_min, mcp_max = mcp_bounds(regras, full)

    # Resolver preços sugeridos por FAIXAS (fixo depende do próprio preço)
    preco_min = preco_para_mcp_alvo_bandas(regras, full, custo, mcp_min) if mcp_min is not None else None
    preco_max = preco_para_mcp_alvo_bandas(regras, full, custo, mcp_max) if mcp_max is not None else None

    # Atualiza métricas
    item.update({
        "imposto_valor": comp["imposto_valor"],
        "marketing_valor": comp["marketing_valor"],
        # comissão após abatimento do subsídio:
        "tarifa_canal_valor": tarifa_canal_ajustada,
        "frete_valor": frete_abs,
        "tarifa_fixa_brl": fixo_brl,
        "mc_valor": mc_valor_final,
        "mcp_pct": mcp_pct_final,
    })
    # Sempre expor campos de sugestão; flags como None quando não há alvo no YAML
    item["preco_sugerido_min"] = preco_min if mcp_min is not None else None
    item["mcp_min_inviavel"] = ((preco_min is None) if mcp_min is not None else None)
    item["preco_sugerido_max"] = preco_max if mcp_max is not None else None
    item["mcp_max_inviavel"] = ((preco_max is None) if mcp_max is not None else None)

    return item




__all__ = [
    "calcular_componentes",
    "fixo_por_preco",
    "frete_pct_sobre_custo",
    "mcp_bounds",
    "preco_para_mcp_alvo",
    "preco_para_mcp_alvo_bandas",
    "enriquecer_item_com_metricas",
]
