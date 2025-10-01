from __future__ import annotations
import json
from typing import Dict, Any
from app.config.paths import Regiao, Camada
from .aggregator import fetch_frete_imposto, fetch_fatura_resumo
from .metrics import compute_result
from .metrics import summarize_meli_totais, summarize_meli_inclui, summarize_meli_cobramos

from app.utils.costs.variable.overview.config import resultado_empresa_json

from .aggregator import fetch_resumo_transacoes

import re
import unicodedata
from numbers import Number

# -------------------------
# Helpers
# -------------------------

def _slug(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s).strip()
    return s

def _is_assessoria(item, exclude_terms=("consultoria", "assessoria", "outras tarifas")):
    """
    Marca itens que devem ser tratados como 'assessoria/consultoria'.
    A inclusão de 'outras tarifas' foi feita por evidência dos seus dados.
    """
    key = _slug(item.get("key") or "")
    label = _slug(item.get("label") or "")
    excl = tuple(_slug(x) for x in exclude_terms)
    return any(term in key or term in label for term in excl)

def _is_assessoria_inclui(item) -> bool:
    """
    Versão específica para o bloco 'inclui': trata explicitamente a chave 'outras_tarifas'
    como assessoria, além das heurísticas de _is_assessoria.
    """
    key_raw = (item.get("key") or "").strip().lower()
    if key_raw == "outras_tarifas":
        return True
    return _is_assessoria(item)

def _group_items(items):
    """Agrupa por 'key' (fallback para 'label'), somando 'valor'."""
    grupos: Dict[str, Dict[str, Any]] = {}
    for it in items or []:
        key = it.get("key") or it.get("label") or "desconhecido"
        label = it.get("label") or key
        val = it.get("valor")
        if not isinstance(val, (int, float)):
            continue
        g = grupos.setdefault(key, {"key": key, "label": label, "valor": 0.0})
        g["valor"] += float(val)
    for g in grupos.values():
        g["valor"] = round(g["valor"], 2)
    # ordena para estabilidade visual
    return sorted(grupos.values(), key=lambda x: _slug(x["label"]))

def _read_json(path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
    
def _sum_numeric_fields(a: dict, b: dict) -> dict:
    out: dict[str, float | None] = {}
    keys = set(a.keys()) | set(b.keys())
    for k in keys:
        av, bv = a.get(k), b.get(k)
        if isinstance(av, Number) and isinstance(bv, Number):
            out[k] = float(av) + float(bv)
        elif isinstance(av, Number) and bv is None:
            out[k] = float(av)
        elif isinstance(bv, Number) and av is None:
            out[k] = float(bv)
        else:
            out[k] = None
    return out

# -------------------------
# Overview (sem escrita)
# -------------------------

def build_overview(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    rt = fetch_resumo_transacoes(ano, mes, regiao, camada, debug=debug)
    fi = fetch_frete_imposto(ano, mes, regiao, camada, debug=debug)
    fr = fetch_fatura_resumo(ano, mes, regiao, camada, debug=debug)
    

    if debug:
        print(f"[DBG] frete_imposto keys: {list(fi.keys()) if isinstance(fi, dict) else type(fi)}")
        print(f"[DBG] fatura_resumo keys: {list(fr.keys()) if isinstance(fr, dict) else type(fr)}")

    return {
        "periodo": {"ano": ano, "mes": mes, "regiao": regiao.value, "camada": camada.value},
        "frete_imposto": fi,
        "resumo_transacoes": rt,
        "meli_fatura_resumo": fr,
    }


# -------------------------
# Resultado executivo (DRE)
# -------------------------


def build_resultado_empresa(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    """
    Resultado executivo com bloco simplificado 'fatura_mercado_livre' (inclui_total, estornos_total, liquido)
    e sem campos antigos de Mercado Livre.
    """
    fi = fetch_frete_imposto(ano, mes, regiao, camada, debug=debug) or {}
    rt = fetch_resumo_transacoes(ano, mes, regiao, camada, debug=debug) or {}
    fr = fetch_fatura_resumo(ano, mes, regiao, camada, debug=debug) or {}

    # períodos
    periodos = (fr.get("meta") or {}).get("periodos") or {}
    per_fat_meli = periodos.get("faturamento_meli") or {}
    min_date = per_fat_meli.get("min_date")
    max_date = per_fat_meli.get("max_date")

    # base monetária (venda + custos diretos)
    venda_bruta = float(fi.get("valor_transacao_total", 0.0) or 0.0)
    custo_total = float(fi.get("custo_total", 0.0) or 0.0)          # COGS
    imposto = float(fi.get("imposto_calculado", 0.0) or 0.0)
    frete = float(fi.get("frete_calculado", 0.0) or 0.0)

    # Totais + detalhamento da fatura do ML
    totais = summarize_meli_totais(fr)
    inc = summarize_meli_inclui(fr)      # dicionário com todos os buckets "sua_fatura_inclui"
    cob = summarize_meli_cobramos(fr) 

    # Usar o 'líquido' da fatura do ML como gastos_mercado_livre no resultado financeiro
    gastos_meli_liquido = float(totais.get("liquido", 0.0) or 0.0)
    metrics = compute_result(venda_bruta, custo_total, imposto, frete, gastos_meli_liquido)

    return {
        "periodos": {"faturamento_meli": {"min_date": min_date, "max_date": max_date}},
        "periodo": {"ano": ano, "mes": mes, "regiao": regiao.value, "camada": camada.value},
        "frete_imposto": fi,
        "resumo_transacoes": rt,
        "fatura_mercado_livre": {

            # detalhamento requisitado
            "sua_fatura_inclui": inc,
            # campo pontual de estornos (além de estornos_total)
            "estornos": cob.get("estornos", 0.0),
        },
        "metrics": metrics,
    }

def build_resumo_meli(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    """
    RESUMO SIMPLES (sem cálculos gerenciais): apenas reestrutura os dados de 'meli_fatura_resumo'
    para o formato padronizado solicitado, agregando por categorias conhecidas.
    Saída:
      {
        "periodos": {"faturamento_meli": {"min_date": ..., "max_date": ...}},
        "sua_fatura_inclui": {
            "outras_tarifas": 0.0,
            "tarifas_venda": 0.0,
            "tarifas_envios_ml": 0.0,
            "tarifas_publicidade": 0.0,
            "tarifas_envios_full": 0.0,
            "taxas_parcelamento": 0.0,
            "minha_pagina": 0.0,
            "servicos_mercado_pago": 0.0,
            "cancelamentos": 0.0
        },
        "ja_cobramos": {
            "estornos": 0.0,
            "debito_automatico": 0.0,
            "cobrado_operacao": 0.0
        }
      }
    """
    fr = fetch_fatura_resumo(ano, mes, regiao, camada, debug=debug) or {}

    # períodos
    periodos = (fr.get("meta") or {}).get("periodos") or {}
    per_fat_meli = periodos.get("faturamento_meli") or {}
    min_date = per_fat_meli.get("min_date")
    max_date = per_fat_meli.get("max_date")

    inclui = fr.get("sua_fatura_inclui") or []
    cobramos = fr.get("ja_cobramos") or []

    # Canonical buckets
    inclui_buckets = {
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
    cobramos_buckets = {
        "estornos": 0.0,
        "debito_automatico": 0.0,
        "cobrado_operacao": 0.0,
    }

    def _slug(s: str) -> str:
        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.lower()
        s = re.sub(r"[^a-z0-9\s]+", " ", s).strip()
        return s

    # Aliases for mapping
    inclui_aliases = {
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
    cobramos_aliases = {
        "estornos": ["estornos", "estorno"],
        "debito_automatico": ["debito automatico", "débito automático", "debito_automatico"],
        "cobrado_operacao": ["cobrado na operacao", "cobrado na operação", "cobrado_operacao"],
    }

    def _map_inclui_key(item) -> str | None:
        key = _slug(item.get("key") or "")
        label = _slug(item.get("label") or "")
        for canon, variants in inclui_aliases.items():
            if key in variants or label in variants:
                return canon
        # fallback by contains
        for canon, variants in inclui_aliases.items():
            if any(v in key for v in variants) or any(v in label for v in variants):
                return canon
        return None

    def _map_cobramos_key(item) -> str | None:
        key = _slug(item.get("key") or "")
        label = _slug(item.get("label") or "")
        for canon, variants in cobramos_aliases.items():
            if key in variants or label in variants:
                return canon
        for canon, variants in cobramos_aliases.items():
            if any(v in key for v in variants) or any(v in label for v in variants):
                return canon
        return None

    # Aggregate inclui (aceita dict ou lista)
    if isinstance(inclui, dict):
        for k, v in inclui.items():
            if k in inclui_buckets:
                try:
                    inclui_buckets[k] += float(v or 0.0)
                except Exception:
                    pass
    else:
        for it in (inclui or []):
            val = it.get("valor")
            if not isinstance(val, (int, float)):
                continue
            canon = _map_inclui_key(it)
            if canon and canon in inclui_buckets:
                inclui_buckets[canon] += float(val)

    # Aggregate cobramos (aceita dict ou lista)
    if isinstance(cobramos, dict):
        for k, v in cobramos.items():
            if k in cobramos_buckets:
                try:
                    cobramos_buckets[k] += float(v or 0.0)
                except Exception:
                    pass
    else:
        for it in (cobramos or []):
            val = it.get("valor")
            if not isinstance(val, (int, float)):
                continue
            canon = _map_cobramos_key(it)
            if canon and canon in cobramos_buckets:
                cobramos_buckets[canon] += float(val)

    # Round everything
    inclui_buckets = {k: round(v, 2) for k, v in inclui_buckets.items()}
    cobramos_buckets = {k: round(v, 2) for k, v in cobramos_buckets.items()}

    return {
        "periodos": {"faturamento_meli": {"min_date": min_date, "max_date": max_date}},
        "sua_fatura_inclui": inclui_buckets,
        "ja_cobramos": cobramos_buckets,
    }

def read_metrics_from_resultado(
    ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False
) -> dict:
    """
    Lê .../overview/<ano>/<mes>/<regiao>/<camada>/resultado_empresa.json e
    retorna apenas o bloco 'metrics'. Tolerante a arquivo ausente.
    """
    p = resultado_empresa_json(ano, mes, regiao, camada)
    if debug:
        print(f"[DBG] lendo metrics de {p} (exists={p.exists()})")
    data = _read_json(p) or {}
    return data.get("metrics") or {}

def sum_metrics(metrics_mg: dict, metrics_sp: dict) -> dict:
    """Soma MG + SP; margem = resultado_financeiro / venda_bruta."""
    summed = _sum_numeric_fields(metrics_mg, metrics_sp)
    venda = float(summed.get("venda_bruta") or 0.0)
    resultado = float(summed.get("resultado_financeiro") or 0.0)
    summed["margem"] = (resultado / venda) if venda > 0 else 0.0
    return summed

def build_metrics_consolidado(
    ano: int, mes: int, camada: Camada = Camada.PP, *, debug: bool = False
) -> dict[str, dict]:
    """
    Conveniência: retorna {'mg': {...}, 'sp': {...}, 'all': {...}} com apenas metrics.
    Escrita deve ser feita no script.
    """
    mg = read_metrics_from_resultado(ano, mes, Regiao.MG, camada, debug=debug)
    sp = read_metrics_from_resultado(ano, mes, Regiao.SP, camada, debug=debug)
    allm = sum_metrics(mg, sp)
    return {"mg": mg, "sp": sp, "all": allm}
