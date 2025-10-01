from __future__ import annotations
from typing import Dict, Tuple, Any
import unicodedata
import re

# ---------- Slug helpers ----------
def _to_slug(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s).strip()
    return s

# ---------- Result calc (mantido p/ compatibilidade) ----------
def compute_result(
    venda_bruta: float,
    custo_total: float,
    imposto: float,
    frete: float,
    gastos_meli: float,
) -> Dict[str, float]:
    venda_bruta = float(venda_bruta or 0.0)
    custo_total = float(custo_total or 0.0)
    imposto = float(imposto or 0.0)
    frete = float(frete or 0.0)
    gastos_meli = float(gastos_meli or 0.0)

    resultado = venda_bruta - (custo_total + imposto + frete + gastos_meli)
    margem = (resultado / venda_bruta) if venda_bruta else 0.0
    return {
        "venda_bruta": round(venda_bruta, 2),
        "custo_produtos": round(custo_total, 2),
        "custo_imposto": round(imposto, 2),
        "custo_frete": round(frete, 2),
        "gastos_mercado_livre": round(gastos_meli, 2),
        "resultado_financeiro": round(resultado, 2),
        "margem": round(margem, 4),
    }

# ---------- Summaries previously used ----------
def summarize_ml_charges(
    meli_fatura_resumo: Dict,
    *,
    exclude_terms: Tuple[str, ...] = ("consultoria", "assessoria"),
) -> Dict[str, float]:
    if not isinstance(meli_fatura_resumo, dict):
        return {
            "inclui_sem_assessoria": 0.0,
            "inclui_assessoria": 0.0,
            "cobramos_total": 0.0,
            "cobramos_assessoria": 0.0,
            "cobramos_sem_assessoria": 0.0,
        }

    def _is_assessoria(item) -> bool:
        key = _to_slug(item.get("key") or "")
        label = _to_slug(item.get("label") or "")
        excl = tuple(_to_slug(x) for x in exclude_terms)
        return any(term in key or term in label for term in excl)

    soma_inclui_sem_ass = 0.0
    soma_inclui_ass = 0.0
    for it in (meli_fatura_resumo.get("sua_fatura_inclui") or []):
        val = it.get("valor")
        if not isinstance(val, (int, float)):
            continue
        if _is_assessoria(it):
            soma_inclui_ass += float(val)
        else:
            soma_inclui_sem_ass += float(val)

    soma_cobramos_total = 0.0
    soma_cobramos_ass = 0.0
    soma_cobramos_sem_ass = 0.0
    for it in (meli_fatura_resumo.get("ja_cobramos") or []):
        val = it.get("valor")
        if not isinstance(val, (int, float)):
            continue
        if _is_assessoria(it):
            soma_cobramos_ass += float(val)
        else:
            soma_cobramos_total += float(val)
            soma_cobramos_sem_ass += float(val)

    return {
        "inclui_sem_assessoria": round(soma_inclui_sem_ass, 2),
        "inclui_assessoria": round(soma_inclui_ass, 2),
        "cobramos_total": round(soma_cobramos_total, 2),
        "cobramos_assessoria": round(soma_cobramos_ass, 2),
        "cobramos_sem_assessoria": round(soma_cobramos_sem_ass, 2),
    }

# ---------- New simple totals (pedido atual) ----------
def _slug_meli(s: str) -> str:
    return _to_slug(s)

_INCLUI_ALIASES = {
    "outras_tarifas": ["outras tarifas", "outros", "outras-tarifas"],
    "tarifas_venda": ["tarifas de venda", "tarifa de venda", "tarifas_venda"],
    "tarifas_envios_ml": ["envios ml", "tarifas envios ml", "envio mercado livre", "envios do mercado livre"],
    "tarifas_publicidade": ["publicidade", "ads", "anuncios", "tarifas publicidade"],
    "tarifas_envios_full": ["envios full", "fulfillment", "tarifas envios full"],
    "taxas_parcelamento": ["taxas de parcelamento", "parcelamento", "taxa parcelamento"],
    "minha_pagina": ["minha pagina", "minha página"],
    "servicos_mercado_pago": ["servicos mercado pago", "serviços mercado pago", "mercado pago"],
    "cancelamentos": ["cancelamentos", "cancelamentos de tarifas", "estornos de tarifas"],
}

_COBRAMOS_ALIASES = {
    "estornos": ["estornos", "estorno"],
    "debito_automatico": ["debito automatico", "débito automático", "debito_automatico"],
    "cobrado_operacao": ["cobrado na operacao", "cobrado na operação", "cobrado_operacao"],
}

def meli_map_alias(item: Dict[str, Any], aliases: Dict[str, list]) -> str | None:
    key = _slug_meli(item.get("key") or "")
    label = _slug_meli(item.get("label") or "")
    # exact
    for canon, variants in aliases.items():
        if key in variants or label in variants:
            return canon
    # contains
    for canon, variants in aliases.items():
        if any(v in key for v in variants) or any(v in label for v in variants):
            return canon
    return None

def summarize_meli_inclui(fr: Dict[str, Any]) -> Dict[str, float]:
    buckets = {
        "outras_tarifas": 0.0,
        "tarifas_venda": 0.0,
        "tarifas_envios_ml": 0.0,
        "tarifas_publicidade": 0.0,
        "tarifas_envios_full": 0.0,
        "taxas_parcelamento": 0.0,
        "minha_pagina": 0.0,
        "servicos_mercado_pago": 0.0,
        "cancelamentos": 0.0,
    }
    inc = fr.get("sua_fatura_inclui") or {}
    # aceita dict (novo formato) OU lista (formato antigo)
    if isinstance(inc, dict):
        for k, v in inc.items():
            if k in buckets:
                try:
                    buckets[k] += float(v or 0.0)
                except Exception:
                    pass
    else:
        for it in (inc or []):
            val = it.get("valor")
            if not isinstance(val, (int, float)):
                continue
            canon = meli_map_alias(it, _INCLUI_ALIASES)
            if canon and canon in buckets:
                buckets[canon] += float(val)
    return {k: round(v, 2) for k, v in buckets.items()}

def summarize_meli_cobramos(fr: Dict[str, Any]) -> Dict[str, float]:
    buckets = {
        "estornos": 0.0,
        "debito_automatico": 0.0,
        "cobrado_operacao": 0.0,
    }
    cob = fr.get("ja_cobramos") or {}
    if isinstance(cob, dict):
        for k, v in cob.items():
            if k in buckets:
                try:
                    buckets[k] += float(v or 0.0)
                except Exception:
                    pass
    else:
        for it in (cob or []):
            val = it.get("valor")
            if not isinstance(val, (int, float)):
                continue
            canon = meli_map_alias(it, _COBRAMOS_ALIASES)
            if canon and canon in buckets:
                buckets[canon] += float(val)
    return {k: round(v, 2) for k, v in buckets.items()}

def summarize_meli_totais(fr: Dict[str, Any]) -> Dict[str, float]:
    # Soma TOTAL da fatura (inclui) e apenas o bucket 'estornos' do 'ja_cobramos'.
    # 'liquido' é a soma de inclui_total e estornos_total (estornos normalmente negativo).
    # Não considera débito automático / cobrado na operação neste subtotal.
    
    inc = summarize_meli_inclui(fr)
    cob = summarize_meli_cobramos(fr)
    inclui_total = round(sum(inc.values()), 2)
    estornos_total = round(cob.get("estornos", 0.0), 2)
    liquido = round(inclui_total + estornos_total, 2)
    return {
        "inclui_total": inclui_total,
        "estornos_total": estornos_total,
        "liquido": liquido,
    }