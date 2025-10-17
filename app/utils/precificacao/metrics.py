from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
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


def clamp_percent(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return max(0.0, min(1.0, x))


def _num(x, default=None):
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# =========================
# Leitura de regras (YAML)
# =========================

def carregar_regras_ml() -> dict:
    """
    Carrega o arquivo de regras do ML (tiers de FULL, comissões, defaults, etc.)
    Mantém este módulo puro (sem depender de service.py).
    """
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
    Retorna o custo fixo FULL (R$) de acordo com faixas do YAML:
      full.custo_fixo_por_unidade_brl: [{max_preco, valor}, ..., {otherwise: true, valor}]
    """
    tiers = (regras or {}).get("full", {}).get("custo_fixo_por_unidade_brl", []) or []
    try:
        p = float(preco)
    except (TypeError, ValueError):
        return 0.0

    for t in tiers:
        if "max_preco" in t and t["max_preco"] is not None:
            try:
                if p <= float(t["max_preco"]) + 1e-9:
                    return float(t.get("valor", 0.0))
            except (TypeError, ValueError):
                continue

    for t in tiers:
        if t.get("otherwise"):
            try:
                return float(t.get("valor", 0.0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


# =========================
# Preço efetivo & subsídio
# =========================

def preco_efetivo(preco_cheio, rebate_price_discounted, considerar_rebate=True) -> Optional[float]:
    """Preço efetivo = rebate (se considerar e válido) senão preço cheio; jamais <= 0."""
    p = None
    if considerar_rebate and rebate_price_discounted not in (None, ""):
        p = _num(rebate_price_discounted)
    if p is None:
        p = _num(preco_cheio)
    if p is None or p <= 0:
        return None
    return p


def subsidio_ml_valor(price, rebate_price_discounted, considerar_rebate=True) -> Optional[float]:
    """Subsídio do ML em valor (R$): max(price - rebate, 0) quando considerar_rebate=True."""
    if not considerar_rebate:
        return None
    p = _num(price)
    r = _num(rebate_price_discounted)
    if p is None or r is None:
        return None
    if p <= 0 or r >= p:
        return None
    return max(0.0, p - r)


def subsidio_ml_taxa(price, rebate_price_discounted, considerar_rebate=True) -> Optional[float]:
    """Taxa de subsídio (0..1): 1 - rebate/price, se rebate < price."""
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


def _alocar_subsidio_sobre_taxas(
    subs_valor: float,
    base_comissao_brl: float,
    base_marketing_brl: float,
    base_imposto_brl: float,
    ordem_campos: List[str],
) -> Tuple[float, float, float, dict]:
    """
    Abate o subsídio (R$) na ordem definida: p.ex. ["comissao"] ou ["comissao","marketing","imposto"].
    Nunca negativar custos. Retorna (comissao_aj, marketing_aj, imposto_aj, alloc_map).
    """
    rem = max(0.0, float(subs_valor))
    c, m, i = float(base_comissao_brl or 0), float(base_marketing_brl or 0), float(base_imposto_brl or 0)
    alloc = {"comissao": 0.0, "marketing": 0.0, "imposto": 0.0}

    for campo in ordem_campos:
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


# =========================
# Custo total & MCP
# =========================

def custo_total(preco_compra,
                frete=0, comissao_pct=0, imposto_pct=0, marketing_pct=0,
                custo_fixo_full=0) -> Optional[Tuple[float, float, float, float]]:
    """
    Retorna (ct_base, comissao_pct, imposto_pct, marketing_pct).
    ct_base = preco_compra + frete + custo_fixo_full
    """
    pc = _num(preco_compra)
    if pc is None or pc < 0:
        return None
    fr = _num(frete, 0.0)
    cf = _num(custo_fixo_full, 0.0)

    c = clamp_percent(_num(comissao_pct, 0.0))
    i = clamp_percent(_num(imposto_pct, 0.0))
    m = clamp_percent(_num(marketing_pct, 0.0))

    return pc + fr + cf, c, i, m


def mcp(preco_venda_efetivo: Optional[float],
        preco_compra: Optional[float],
        frete=0, comissao_pct=0, imposto_pct=0, marketing_pct=0,
        custo_fixo_full=0) -> dict:
    """
    Retorna dict com mcp_abs, mcp_pct (ou ambos None) + 'null_reasons' quando não calculável.
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
    custos_percentuais = (c or 0) * pv + (i or 0) * pv + (m or 0) * pv
    ct = ct_base + custos_percentuais

    m_abs = pv - ct
    m_pct = m_abs / pv

    return {"mcp_abs": m_abs, "mcp_pct": m_pct, "null_reasons": reasons}


# =========================
# Núcleo por item (com overrides)
# =========================

def calcular_metricas_item(item: dict, *args, **kwargs) -> dict:
    """
    Calcula MCP por item e anota custos absolutos, priorizando chaves *_override quando presentes.
    Compat:
      - calcular_metricas_item(item)
      - calcular_metricas_item(item, True/False)                      # considerar_rebate
      - calcular_metricas_item(item, considerar_rebate=True/False)
      - calcular_metricas_item(item, use_rebate_as_price=True/False)  # alias legado
      - calcular_metricas_item(item, regras=<dict>)                   # regras YAML (opcional)
    """
    # --- 1) Flags/kwargs ---
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
    aplicar_em = default.get("aplicar_subsidio_em") or ["comissao"]
    if isinstance(aplicar_em, str):
        aplicar_em = [aplicar_em]

    # Helpers de override
    def _num_or_none(x):
        try:
            return float(x)
        except Exception:
            return None

    def _pick_override(d: dict, key_base: str):
        """Ex.: key_base='comissao_pct' -> usa d['comissao_pct_override'] se existir."""
        cand = d.get(f"{key_base}_override")
        return _num_or_none(cand)

    # --- 3) Preço efetivo + subsídios ---
    price  = item.get("price")
    rebate = item.get("rebate_price_discounted")
    pe = preco_efetivo(price, rebate, considerar_rebate=considerar_rebate)
    if pe is not None:
        item["preco_efetivo"] = pe

    subs_valor = subsidio_ml_valor(price, rebate, considerar_rebate=considerar_rebate)
    subs_tx    = subsidio_ml_taxa(price, rebate, considerar_rebate=considerar_rebate)

    # --- 4) Percentuais (com overrides) ---
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

    ov_com = _pick_override(item, "comissao_pct")
    ov_imp = _pick_override(item, "imposto_pct")
    ov_mkt = _pick_override(item, "marketing_pct")

    comissao_pct  = clamp_percent(ov_com if ov_com is not None else _pct_or_default("comissao_pct", _pct(comissao_base)))
    imposto_pct   = clamp_percent(ov_imp if ov_imp is not None else _pct_or_default("imposto_pct",  _pct(default.get("imposto_pct"))))
    marketing_pct = clamp_percent(ov_mkt if ov_mkt is not None else _pct_or_default("marketing_pct",_pct(default.get("marketing_pct"))))

    # --- 5) Frete (com override) ---
    preco_compra = item.get("preco_compra")

    ov_frete = _pick_override(item, "frete_full")
    if ov_frete is None:
        ov_frete = _pick_override(item, "frete_sobre_custo")

    frete_val = ov_frete
    if frete_val is None:
        frete_val = _to_num(item.get("frete_full"))
    if frete_val is None:
        frete_val = _to_num(item.get("frete_sobre_custo"))
    if frete_val is None:
        fr_pct  = _pct(default.get("frete_pct_sobre_custo"))
        fr_base = _to_num(preco_compra) or 0.0
        frete_val = fr_base * fr_pct

    # --- 6) Custos variáveis brutos (antes do subsídio), se houver preço efetivo ---
    if pe is not None:
        imposto_val_base   = (imposto_pct   or 0.0) * pe
        marketing_val_base = (marketing_pct or 0.0) * pe
        comissao_val_base  = (comissao_pct  or 0.0) * pe
    else:
        imposto_val_base = marketing_val_base = comissao_val_base = None

    # --- 7) Aplicação do subsídio em valor sobre as taxas ---
    if pe is not None and subs_valor and subs_valor > 0:
        c_adj, m_adj, i_adj, alloc = _alocar_subsidio_sobre_taxas(
            subs_valor,
            comissao_val_base or 0.0,
            marketing_val_base or 0.0,
            imposto_val_base or 0.0,
            ordem_campos=aplicar_em,
        )
    else:
        c_adj = comissao_val_base or 0.0
        m_adj = marketing_val_base or 0.0
        i_adj = imposto_val_base  or 0.0
        alloc = {"comissao": 0.0, "marketing": 0.0, "imposto": 0.0}

    # Percentuais efetivos após subsídio
    if pe and pe > 0:
        comissao_pct_eff  = c_adj / pe
        marketing_pct_eff = m_adj / pe
        imposto_pct_eff   = i_adj / pe
    else:
        comissao_pct_eff = marketing_pct_eff = imposto_pct_eff = 0.0

    # --- 8) Custo fixo FULL (com override) ---
    ov_fix = _pick_override(item, "custo_fixo_full")  # R$/unid
    if _is_full_item(item):
        if ov_fix is not None:
            fixo_val = float(ov_fix)
            fixo_origem = "override"
        else:
            fixo_val = float(custo_fixo_full(pe, regras) if pe is not None else 0.0)
            fixo_origem = "yaml"
    else:
        fixo_val = 0.0
        fixo_origem = "nao_full"

    # --- 9) MCP (usando percentuais AJUSTADOS e fixo FULL já decidido) ---
    res = mcp(
        preco_venda_efetivo=pe,
        preco_compra=preco_compra,
        frete=frete_val,
        comissao_pct=comissao_pct_eff,
        imposto_pct=imposto_pct_eff,
        marketing_pct=marketing_pct_eff,
        custo_fixo_full=fixo_val,
    )

    # --- 10) Saída padronizada ---
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
        "custo_fixo_full": fixo_val if _is_full_item(item) else None,
        "custo_fixo_full_origem": fixo_origem,
        "frete_sobre_custo": frete_val,

        # subsídio em valor e taxa
        "subsidio_ml_valor": subs_valor,
        "subsidio_ml_taxa":  subs_tx,

        # rastros úteis
        "comissao_bruta":  comissao_val_base,
        "marketing_bruta": marketing_val_base,
        "imposto_bruta":   imposto_val_base,
        "subsidio_alocado": alloc,
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

def aplicar_metricas_no_documento(
    documento: Dict[str, Any], *,
    regras: dict | None = None,
    only_full: bool = False,
    use_rebate_as_price: bool = True,
    canal: str = "meli",
) -> Dict[str, Any]:
    itens_in = documento.get("itens", []) or []

    itens_out = []
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
