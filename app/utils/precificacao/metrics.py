
from __future__ import annotations

from typing import Any, Dict, List, Optional

import math
import yaml

from app.utils.precificacao.config import get_regras_meli_yaml_path


# =========================
# Utilidades numéricas
# =========================

def _to_num(v) -> Optional[float]:
    try:
        if v is None or isinstance(v, bool):
            return None
        x = float(v)
        if not math.isfinite(x):
            return None
        return x
    except Exception:
        return None


def _pct(v) -> float:
    try:
        if v is None:
            return 0.0
        x = float(v)
        return x if math.isfinite(x) else 0.0
    except Exception:
        return 0.0


# =========================
# Regras (local, sem importar service.py)
# =========================

def carregar_regras_ml() -> dict:
    yaml_path = get_regras_meli_yaml_path()
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# =========================
# FULL helpers
# =========================

def _is_full_item(it: Dict[str, Any]) -> bool:
    lt = str(it.get("logistic_type") or "").lower()
    return (
        bool(it.get("is_full")) or bool(it.get("full")) or bool(it.get("isFull"))
        or lt.startswith("fulfillment")
    )


def custo_fixo_full(preco: float | None, regras: dict) -> float:
    """
    Retorna o custo fixo FULL (R$) de acordo com as faixas do YAML:
      full.custo_fixo_por_unidade_brl: [{max_preco, valor}, ..., {otherwise: true, valor}]
    """
    tiers = (regras or {}).get("full", {}).get("custo_fixo_por_unidade_brl", []) or []
    try:
        p = float(preco)
    except (TypeError, ValueError):
        return 0.0

    # Faixas com limite superior (<= max_preco)
    for t in tiers:
        if "max_preco" in t and t["max_preco"] is not None:
            try:
                if p <= float(t["max_preco"]) + 1e-9:
                    return float(t.get("valor", 0.0))
            except (TypeError, ValueError):
                continue

    # Fallback "otherwise"
    for t in tiers:
        if t.get("otherwise"):
            try:
                return float(t.get("valor", 0.0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0

def _num(x, default=None):
    """Converte para float, mantendo None quando faltar informação crítica."""
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

# =========================
# Preço efetivo
# =========================

def subsidio_ml_valor(price, rebate_price_discounted, considerar_rebate=True) -> Optional[float]:
    """
    Subsídio do ML em VALOR (R$): max(price - rebate, 0) quando considerar_rebate=True.
    """
    if not considerar_rebate:
        return None
    p = _num(price)
    r = _num(rebate_price_discounted)
    if p is None or r is None:
        return None
    if p <= 0 or r >= p:
        return None
    return max(0.0, p - r)


def _alocar_subsidio_sobre_taxas(
    subs_valor: float,
    base_comissao_brl: float,
    base_marketing_brl: float,
    base_imposto_brl: float,
    ordem_campos: list[str],
) -> tuple[float, float, float, dict]:
    """
    Aloca o subsídio (R$) abatendo a soma das taxas na ordem indicada.
    Não deixa nenhum custo ficar negativo. Retorna (comissao_aj, marketing_aj, imposto_aj, aloc_map).
    ordem_campos: p.ex. ["comissao"] ou ["comissao","marketing","imposto"].
    """
    rem = max(0.0, float(subs_valor))
    c, m, i = float(base_comissao_brl or 0), float(base_marketing_brl or 0), float(base_imposto_brl or 0)
    alloc = {"comissao": 0.0, "marketing": 0.0, "imposto": 0.0}

    for campo in ordem_campos:
        if rem <= 0:
            break
        if campo == "comissao":
            ded = min(rem, c); c -= ded; rem -= ded; alloc["comissao"] += ded
        elif campo == "marketing":
            ded = min(rem, m); m -= ded; rem -= ded; alloc["marketing"] += ded
        elif campo == "imposto":
            ded = min(rem, i); i -= ded; rem -= ded; alloc["imposto"] += ded

    return c, m, i, alloc


def preco_efetivo(preco_cheio, rebate_price_discounted, considerar_rebate=True) -> Optional[float]:
    """Escolhe o preço válido: rebate (se houver e considerar), senão cheio; não deixa <=0."""
    p = None
    if considerar_rebate and rebate_price_discounted not in (None, ""):
        p = _num(rebate_price_discounted)
    if p is None:
        p = _num(preco_cheio)
    if p is None or p <= 0:
        return None
    return p

def subsidio_ml_taxa(price, rebate_price_discounted, considerar_rebate=True) -> Optional[float]:
    """
    Retorna a taxa de subsídio do ML (0..1) quando o rebate for menor que o preço cheio.
    Ex.: price=100, rebate=92  ->  0.08  (8%)
    """
    try:
        if not considerar_rebate:
            return None
        p = _num(price)
        r = _num(rebate_price_discounted)
        if p is None or p <= 0 or r is None:
            return None
        if r < p:
            return max(0.0, 1.0 - (r / p))
        return None
    except Exception:
        return None

def clamp_percent(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    # evita taxas absurdas por erro de origem
    return max(0.0, min(1.0, x))

def custo_total(preco_compra,
                frete=0, comissao_pct=0, imposto_pct=0, marketing_pct=0,
                custo_fixo_full=0) -> Optional[float]:
    """Soma custos. Percentuais devem vir em [0,1]. Se preço_compra faltar, devolve None."""
    pc = _num(preco_compra)
    if pc is None or pc < 0:
        return None
    fr = _num(frete, 0.0)
    cf = _num(custo_fixo_full, 0.0)

    c = clamp_percent(_num(comissao_pct, 0.0))
    i = clamp_percent(_num(imposto_pct, 0.0))
    m = clamp_percent(_num(marketing_pct, 0.0))

    # Percentuais incidem sobre preço de venda (trataremos fora com o preço efetivo)
    return pc + fr + cf, c, i, m

def mcp(preco_venda_efetivo: Optional[float],
        preco_compra: Optional[float],
        frete=0, comissao_pct=0, imposto_pct=0, marketing_pct=0,
        custo_fixo_full=0) -> dict:
    """
    Retorna dict com mcp_abs, mcp_pct (ou ambos None) + 'null_reasons' se algo impedir o cálculo.
    """
    reasons = []
    pv = _num(preco_venda_efetivo)
    if pv is None or pv <= 0:
        reasons.append("preco_venda_invalido")
        return {"mcp_abs": None, "mcp_pct": None, "null_reasons": reasons}

    ct_tuple = custo_total(preco_compra, frete, comissao_pct, imposto_pct, marketing_pct, custo_fixo_full)
    if ct_tuple is None:
        reasons.append("preco_compra_invalido")
        return {"mcp_abs": None, "mcp_pct": None, "null_reasons": reasons}

    ct_base, c, i, m = ct_tuple
    # percentuais incidem sobre o preço de venda efetivo
    custos_percentuais = (c or 0) * pv + (i or 0) * pv + (m or 0) * pv
    ct = ct_base + custos_percentuais

    m_abs = pv - ct
    # proteção: se pv ~ 0, já teria retornado acima
    m_pct = m_abs / pv

    return {"mcp_abs": m_abs, "mcp_pct": m_pct, "null_reasons": reasons}

# =========================
# Núcleo de métricas por item
# =========================

# --- no topo do arquivo já devem existir seus imports e helpers ---

# app/utils/precificacao/metrics.py  (substituir a função inteira)

def calcular_metricas_item(item: dict, *args, **kwargs) -> dict:
    """
    Calcula MCP por item e anota custos absolutos, incluindo subsídio do ML em R$.
    Compat:
      - calcular_metricas_item(item)
      - calcular_metricas_item(item, True/False)                      # considerar_rebate
      - calcular_metricas_item(item, considerar_rebate=True/False)
      - calcular_metricas_item(item, use_rebate_as_price=True/False)  # alias legado
      - calcular_metricas_item(item, regras=<dict>)                   # regras YAML (opcional)
    """
    # --- 1) Flags/kwargs de compatibilidade ---
    considerar_rebate = kwargs.pop("considerar_rebate", None)
    alias = kwargs.pop("use_rebate_as_price", None)
    if considerar_rebate is None:
        if len(args) >= 1:
            considerar_rebate = bool(args[0])
        elif alias is not None:
            considerar_rebate = bool(alias)
        else:
            considerar_rebate = True

    # --- 2) Regras (YAML) ---
    regras = kwargs.get("regras") or carregar_regras_ml()
    default = (regras or {}).get("default", {}) or {}
    cfg_comissao = (regras or {}).get("comissao", {}) or {}
    # onde abater o subsídio: lista de campos, default só "comissao"
    aplicar_em = default.get("aplicar_subsidio_em") or ["comissao"]
    if isinstance(aplicar_em, str):
        aplicar_em = [aplicar_em]

    # --- 3) Preço efetivo + subsídios ---
    price  = item.get("price")
    rebate = item.get("rebate_price_discounted")
    pe = preco_efetivo(price, rebate, considerar_rebate=considerar_rebate)
    if pe is not None:
        item["preco_efetivo"] = pe

    subs_valor = subsidio_ml_valor(price, rebate, considerar_rebate=considerar_rebate)
    subs_tx    = None
    if subs_valor is not None and _num(price):
        try:
            subs_tx = max(0.0, subs_valor / float(price))
        except Exception:
            subs_tx = None

    # --- 4) Percentuais (0..1), com overrides do item quando presentes ---
    def _pct_or_default(key, fallback):
        v = _to_num(item.get(key))
        return clamp_percent(v if v is not None else fallback)

    # comissão depende da logística
    if _is_full_item(item):
        comissao_base = cfg_comissao.get("full") or cfg_comissao.get("fulfillment") \
                        or cfg_comissao.get("classico_pct") or default.get("comissao_pct")
    else:
        comissao_base = cfg_comissao.get("seller") or cfg_comissao.get("classico_pct") \
                        or default.get("comissao_pct")

    comissao_pct  = _pct_or_default("comissao_pct", _pct(comissao_base))
    imposto_pct   = _pct_or_default("imposto_pct",  _pct(default.get("imposto_pct")))
    marketing_pct = _pct_or_default("marketing_pct",_pct(default.get("marketing_pct")))

    # --- 5) Frete sobre custo ---
    preco_compra = item.get("preco_compra")
    frete_val = _to_num(item.get("frete_full"))
    if frete_val is None:
        frete_val = _to_num(item.get("frete_sobre_custo"))
    if frete_val is None:
        fr_pct = _pct(default.get("frete_pct_sobre_custo"))
        fr_base = _to_num(preco_compra) or 0.0
        frete_val = fr_base * fr_pct

    # --- 6) Custos variáveis (R$) sobre o preço efetivo (antes do subsídio) ---
    if pe is not None:
        imposto_val_base   = (imposto_pct   * pe)
        marketing_val_base = (marketing_pct * pe)
        comissao_val_base  = (comissao_pct  * pe)
    else:
        imposto_val_base = marketing_val_base = comissao_val_base = None

    # --- 7) Aplicação do subsídio EM VALOR sobre as taxas (sem negativar) ---
    if pe is not None and subs_valor and subs_valor > 0:
        c_adj, m_adj, i_adj, alloc = _alocar_subsidio_sobre_taxas(
            subs_valor,
            comissao_val_base or 0.0,
            marketing_val_base or 0.0,
            imposto_val_base or 0.0,
            ordem_campos=aplicar_em,   # ex.: ["comissao"] ou ["comissao","marketing","imposto"]
        )
    else:
        c_adj, m_adj, i_adj = comissao_val_base or 0.0, marketing_val_base or 0.0, imposto_val_base or 0.0
        alloc = {"comissao": 0.0, "marketing": 0.0, "imposto": 0.0}

    # Deriva percentuais efetivos APÓS subsídio (para alimentar o MCP)
    if pe and pe > 0:
        comissao_pct_eff  = c_adj / pe
        marketing_pct_eff = m_adj / pe
        imposto_pct_eff   = i_adj / pe
    else:
        comissao_pct_eff = marketing_pct_eff = imposto_pct_eff = 0.0

    # --- 8) MCP (usando percentuais AJUSTADOS) ---
    res = mcp(
        preco_venda_efetivo=pe,
        preco_compra=preco_compra,
        frete=frete_val,
        comissao_pct=comissao_pct_eff,
        imposto_pct=imposto_pct_eff,
        marketing_pct=marketing_pct_eff,
        custo_fixo_full=float(custo_fixo_full(pe, regras)) if _is_full_item(item) else 0.0,
    )

    # --- 9) Saída padronizada ---
    out = {
        "preco_efetivo": pe,
        "mcp_abs": res.get("mcp_abs"),
        "mcp_pct": res.get("mcp_pct"),
        "mcp": res.get("mcp_pct"),

        # custos absolutos (após subsídio)
        "imposto": i_adj if pe is not None else None,
        "marketing": m_adj if pe is not None else None,
        "comissao": c_adj if pe is not None else None,

        # percentuais efetivos (após subsídio)
        "imposto_pct": imposto_pct_eff,
        "marketing_pct": marketing_pct_eff,
        "comissao_pct": comissao_pct_eff,

        # controles
        "custo_fixo_full": float(custo_fixo_full(pe, regras)) if _is_full_item(item) else None,
        "frete_sobre_custo": frete_val,

        # subsídio em valor e taxa (para exibir no dashboard)
        "subsidio_ml_valor": subs_valor,
        "subsidio_ml_taxa":  subs_tx,

        # rastros úteis
        "comissao_bruta":  comissao_val_base,
        "marketing_bruta": marketing_val_base,
        "imposto_bruta":   imposto_val_base,
        "subsidio_alocado": alloc,   # quanto foi abatido de cada taxa
        "aplicar_subsidio_em": aplicar_em,
    }
    if res.get("null_reasons"):
        out["mcp_null_reasons"] = res["null_reasons"]
    return out




# =========================
# Agregação do documento
# =========================

def agregar_metricas_documento(itens: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(itens)
    mcp_vals = [_to_num(x.get("mcp")) for x in itens]
    mcp_vals = [x for x in mcp_vals if x is not None]
    mcp_media = sum(mcp_vals) / len(mcp_vals) if mcp_vals else None
    return {"row_count": n, "mcp_media": mcp_media}


# =========================
# Compat: aplicar_metricas_no_documento (legado)
# =========================

def aplicar_metricas_no_documento(documento: Dict[str, Any], *, regras: dict | None = None, only_full: bool = False, use_rebate_as_price: bool = True) -> Dict[str, Any]:
    if regras is None:
        regras = carregar_regras_ml()

    itens_in = documento.get("itens") or []
    itens_out: List[Dict[str, Any]] = []

    for it in itens_in:
        if only_full and not _is_full_item(it):
            itens_out.append(dict(it))
            continue
        calc = calcular_metricas_item(it, regras=regras, use_rebate_as_price=use_rebate_as_price)
        merged = dict(it)
        merged.update(calc)
        itens_out.append(merged)

    doc2 = dict(documento)
    doc2["itens"] = itens_out
    doc2["metrics"] = agregar_metricas_documento(itens_out)
    return doc2

