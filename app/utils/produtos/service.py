# app/utils/produtos/service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

# --- Paths transversais (fonte única) ---
from app.config.paths import DATA_DIR, Camada

# --- Mappers (pacote) ---
# __init__ do pacote deve reexportar estes símbolos:
#   build_indices, sku_to_gtin, gtin_to_sku, normalize_peso_dimensoes
from app.utils.produtos.mappers import (
    sku_to_gtin as _sku_to_gtin,
    gtin_to_sku as _gtin_to_sku,
    normalize_peso_dimensoes,
)

# --- Aggregator (opcional; apenas leitura/normalização de Excel) ---
# Deixe estes helpers existirem no seu módulo produtos/aggregator.py;
# caso não existam, as fachadas que dependem deles apenas não serão usadas.
try:
    from app.utils.produtos.aggregator import (
        carregar_excel_normalizado,
        carregar_excel_normalizado_detalhado,
    )
except Exception:  # fallback: funções-espelho não disponíveis
    carregar_excel_normalizado = None
    carregar_excel_normalizado_detalhado = None


# =============================================================================
# Paths canônicos (PP)
# =============================================================================

def get_produtos_pp_path() -> Path:
    """Caminho canônico do PP de produtos (sem hardcode fora deste service)."""
    return DATA_DIR / "produtos" / Camada.PP.value / "produtos.json"


# =============================================================================
# Leitura do PP
# =============================================================================

def carregar_produtos_pp() -> Dict[str, Any]:
    """
    Lê o produtos.json (PP canônico). Aceita {"items":[...]} ou {"items":{...}}.
    Retorna sempre um dict.
    """
    p = get_produtos_pp_path()
    if not p.exists():
        return {"items": {}}
    with p.open("r", encoding="utf-8") as f:
        obj = json.load(f) or {}
    # saneamento leve
    if "items" not in obj:
        obj["items"] = {}
    return obj


def carregar_pp(camada: Camada = Camada.PP) -> Dict[str, Any]:
    """
    Mantém compat com chamadas antigas que esperam:
      {"count":int, "source":str|None, "items":{sku: {...}}}
    """
    # Usa o path canônico; parâmetro 'camada' hoje só admite PP para produtos.
    p = get_produtos_pp_path() if camada == Camada.PP else get_produtos_pp_path()
    if not p.exists():
        return {"count": 0, "source": None, "items": {}}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f) or {}
    items = data.get("items") or {}
    # normaliza para dict por SKU (quando vier lista)
    if isinstance(items, list):
        items = {str(x.get("sku") or x.get("seller_sku") or f"row{ix}"): x for ix, x in enumerate(items)}
    data["items"] = items
    data["count"] = len(items)
    data.setdefault("source", str(p))
    return data


# =============================================================================
# Índices e resoluções GTIN↔SKU (cache em memória)
# =============================================================================

# --- SUBSTITUIR a implementação de get_indices() por esta ---

_indices_cache: Optional[Dict[str, Dict[str, Any]]] = None

def get_indices(force_refresh: bool = False) -> dict:
    """
    Retorna índices com chaves NORMALIZADAS:
      - por_gtin: chaves str(gtin).strip(); cria também um alias numérico (sem zeros à esquerda) quando aplicável.
      - por_sku : chaves str(sku).strip()
    Cache em memória para performance; use force_refresh=True se regravou o produtos.json.
    """
    global _indices_cache
    if _indices_cache is not None and not force_refresh:
        return _indices_cache

    obj = carregar_produtos_pp()  # <<< usar o leitor já existente
    items = obj.get("items") or {}

    # Aceita tanto dict[sku]->rec quanto lista de registros
    if isinstance(items, dict):
        iterable = items.values()
    elif isinstance(items, list):
        iterable = items
    else:
        iterable = []

    por_gtin: Dict[str, Dict[str, Any]] = {}
    por_sku: Dict[str, Dict[str, Any]] = {}

    for p in iterable:
        gtin_raw = p.get("gtin") or p.get("seller_sku") or p.get("sku") or ""
        sku_raw  = p.get("sku") or p.get("seller_sku") or ""

        gtin_key = str(gtin_raw).strip()
        sku_key  = str(sku_raw).strip()

        if gtin_key:
            # chave "canônica" como string
            por_gtin[gtin_key] = p
            # alias numérico (cobre casos em que algum consumidor compara como int)
            if gtin_key.isdigit():
                por_gtin.setdefault(str(int(gtin_key)), p)

        if sku_key:
            por_sku[sku_key] = p

    _indices_cache = {"por_gtin": por_gtin, "por_sku": por_sku}
    return _indices_cache

def sku_to_gtin(sku: str) -> Optional[str]:
    """Resolve GTIN a partir do SKU (usa cache de índices)."""
    return _sku_to_gtin(sku, indices=get_indices())


def gtin_to_sku(gtin: str) -> Optional[str]:
    """Resolve SKU a partir do GTIN (usa cache de índices)."""
    return _gtin_to_sku(gtin, indices=get_indices())


# =============================================================================
# Fachadas públicas (consumo por dashboards/pages)
# =============================================================================

def listar_skus(camada: Camada = Camada.PP) -> list[str]:
    """Lista SKUs do PP (ordenados)."""
    data = carregar_pp(camada)
    return sorted(list(data["items"].keys()))


def get_itens(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    """Dict[sku] -> registro do produto (conforme PP)."""
    return carregar_pp(camada)["items"]


def listar_produtos(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    """
    Alias de domínio: produtos canônicos por SKU (sem side-effects).
    """
    return get_itens(camada)


def get_por_sku(sku: str, camada: Camada = Camada.PP) -> Optional[Dict[str, Any]]:
    """Retorna o registro por SKU, quando houver."""
    return get_itens(camada).get(sku)


def get_por_gtin(gtin: str, camada: Camada = Camada.PP) -> Optional[Dict[str, Any]]:
    """Retorna o registro por GTIN, quando houver."""
    for rec in get_itens(camada).values():
        if str(rec.get("gtin") or "").strip() == str(gtin).strip():
            return rec
    return None


def obter_custos_por_gtin(gtin: str) -> Optional[float]:
    """Preço de compra do produto (R$) via GTIN, quando disponível."""
    rec = get_por_gtin(gtin)
    return rec.get("preco_compra") if rec else None


def listar_produtos_normalizado(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    """
    Retorna dict[sku]->registro com pesos/dimensões normalizados (kg/cm),
    preenchendo somente campos ausentes. Não grava nada.
    """
    base = listar_produtos(camada)
    out: Dict[str, Dict[str, Any]] = {}
    for sku, rec in base.items():
        rec2 = dict(rec)  # cópia superficial
        try:
            dims = normalize_peso_dimensoes(rec2)  # preenche peso_kg, altura_cm, largura_cm, profundidade_cm
            for k, v in (dims or {}).items():
                if rec2.get(k) in (None, "", [], {}):
                    rec2[k] = v
        except Exception:
            # Em caso de schema inesperado, não interrompe o fluxo
            pass
        out[sku] = rec2
    return out


def get_pack_info_por_gtin(gtin: str, camada: Camada = Camada.PP) -> Dict[str, Any]:
    """
    Campos úteis para reposição/compra:
      preco_compra, multiplo_compra, caixa_cm, pesos_caixa_g, pesos_g, dimensoes_cm
    """
    rec = get_por_gtin(gtin, camada)
    if not rec:
        return {}
    keys = ["preco_compra", "multiplo_compra", "caixa_cm", "pesos_caixa_g", "pesos_g", "dimensoes_cm"]
    return {k: rec.get(k) for k in keys if rec.get(k) not in (None, "", [])}


# =============================================================================
# Fachadas de normalização a partir do Excel (somente leitura; opcional)
# =============================================================================

def preview_normalizacao_excel() -> Dict[str, Dict[str, Any]]:
    """
    Carrega o Excel (caminho do módulo produtos/config.py) e devolve a
    normalização em memória (NÃO grava). Requer aggregator.
    """
    if carregar_excel_normalizado is None:
        raise RuntimeError("Aggregator de produtos indisponível.")
    from app.utils.produtos.config import cadastro_produtos_excel
    return carregar_excel_normalizado(cadastro_produtos_excel())


def normalizar_excel_detalhado() -> tuple[dict, list[dict]]:
    """
    Versão detalhada (linhas de origem + payload normalizado). Requer aggregator.
    """
    if carregar_excel_normalizado_detalhado is None:
        raise RuntimeError("Aggregator de produtos indisponível.")
    from app.utils.produtos.config import cadastro_produtos_excel
    return carregar_excel_normalizado_detalhado(cadastro_produtos_excel())
