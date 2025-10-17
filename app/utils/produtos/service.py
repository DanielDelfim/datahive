# app/utils/produtos/service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.config.paths import DATA_DIR, Camada  # fonte única de paths/enums
from .aggregator import normalizar_para_envio  # adapta 1 registro para a aba Envios

# Mappers reexportados pelo pacote (índices/normalizações auxiliares)
from app.utils.produtos.mappers import (
    sku_to_gtin as _sku_to_gtin,
    gtin_to_sku as _gtin_to_sku,
    normalize_peso_dimensoes,
)

# =====================================================================
# Utilitários internos
# =====================================================================

def _as_list(obj: Any) -> List[Dict[str, Any]]:
    """
    Normaliza qualquer estrutura em list[dict].
    Aceita:
      - list[dict]                        -> retorna como está (filtrando só dicts)
      - dict com chave 'items' (list)     -> retorna items
      - dict com chave 'items' (dict)     -> retorna items.values()
      - dict genérico                     -> retorna values()
      - None / tipos não suportados       -> []
    """
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        items = obj.get("items")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
        if isinstance(items, dict):
            return [v for v in items.values() if isinstance(v, dict)]
        return [v for v in obj.values() if isinstance(v, dict)]
    return []

def _pp_path() -> Path:
    """Caminho canônico do PP de produtos."""
    return DATA_DIR / "produtos" / Camada.PP.value / "produtos.json"

def _load_pp_json() -> Dict[str, Any]:
    """
    Lê o produtos.json. Garante a presença de 'items' no retorno.
    Estrutura típica:
      {
        "_meta": {...},
        "count": int,
        "source": "path",
        "items": { sku: {...} } | [ {...}, {...} ]
      }
    """
    p = _pp_path()
    if not p.exists():
        return {"items": {}, "count": 0, "source": None}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f) or {}
    data.setdefault("items", {})
    # normaliza count/source
    items = data["items"]
    if isinstance(items, dict):
        data["count"] = len(items)
    elif isinstance(items, list):
        data["count"] = len(items)
    data.setdefault("source", str(p))
    return data

def _filter_by_regiao(rows: List[Dict[str, Any]], regiao: Optional[str]) -> List[Dict[str, Any]]:
    """Filtra por campo 'regiao' quando existir; caso contrário, mantém todos."""
    if not regiao:
        return rows
    rnorm = str(regiao).strip().lower()
    def ok(rec: Dict[str, Any]) -> bool:
        v = rec.get("regiao")
        return str(v).strip().lower() == rnorm if v not in (None, "") else True
    return [x for x in rows if ok(x)]

# =====================================================================
# Leitura canônica do PP
# =====================================================================

def carregar_produtos_pp() -> Dict[str, Any]:
    """Compat: retorna o JSON do PP como dict (mantém '_meta', 'items', etc.)."""
    return _load_pp_json()

def carregar_pp(camada: Camada = Camada.PP) -> Dict[str, Any]:
    """
    Compat com chamadas antigas:
      {"count":int, "source":str|None, "items":{sku: {...}}}
    Sempre normaliza 'items' para dict por SKU.
    """
    data = _load_pp_json()
    items = data.get("items") or {}
    if isinstance(items, list):
        # vira dict por sku; se não houver sku, usa índice sintético
        items = {
            str(x.get("sku") or x.get("seller_sku") or f"row{ix}"): x
            for ix, x in enumerate(items) if isinstance(x, dict)
        }
    data["items"] = items
    data["count"] = len(items)
    return data

# =====================================================================
# Fachada nova (para dashboards/pages)
# =====================================================================

def listar_produtos_raw(regiao: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Nova base: retorna list[dict] de produtos diretamente do PP,
    com filtro opcional de 'regiao' quando existir no payload.
    """
    data = _load_pp_json()
    rows = _as_list(data.get("items"))
    return _filter_by_regiao(rows, regiao)

def listar_produtos_para_envio(regiao: Optional[str]) -> List[Dict[str, Any]]:
    """
    **Público — aba Envios**
    Retorna list[dict] no formato canônico exigido pela aba 'Envios':
      - titulo, ean/gtin
      - multiplo_compra normalizado
      - caixa_cm.{largura, profundidade, altura}   (cm, SEM fallback)
      - pesos_caixa_g.{bruto}                      (g, SEM fallback)
      - dimensoes_cm/pesos_g do produto (apenas referência)
    """
    base = listar_produtos_raw(regiao)          # SEMPRE list[dict]
    out: List[Dict[str, Any]] = []
    for rec in base:
        try:
            out.append(normalizar_para_envio(rec))
        except Exception:
            # opcional: logar problemas de schema
            continue
    return out

# =====================================================================
# Índices e resoluções GTIN↔SKU (cache em memória)
# =====================================================================

_indices_cache: Optional[Dict[str, Dict[str, Any]]] = None

def get_indices(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Retorna índices:
      - por_gtin (string + alias numérico)
      - por_sku
    """
    global _indices_cache
    if _indices_cache is not None and not force_refresh:
        return _indices_cache

    obj = _load_pp_json()
    iterable = _as_list(obj.get("items"))

    por_gtin: Dict[str, Dict[str, Any]] = {}
    por_sku: Dict[str, Dict[str, Any]] = {}

    for p in iterable:
        gtin_raw = p.get("gtin") or p.get("seller_sku") or p.get("sku") or ""
        sku_raw  = p.get("sku") or p.get("seller_sku") or ""

        gtin_key = str(gtin_raw).strip()
        sku_key  = str(sku_raw).strip()

        if gtin_key:
            por_gtin[gtin_key] = p
            # alias numérico (cobre comparações int-like)
            if gtin_key.isdigit():
                por_gtin.setdefault(str(int(gtin_key)), p)

        if sku_key:
            por_sku[sku_key] = p

    _indices_cache = {"por_gtin": por_gtin, "por_sku": por_sku}
    return _indices_cache

def sku_to_gtin(sku: str) -> Optional[str]:
    return _sku_to_gtin(sku, indices=get_indices())

def gtin_to_sku(gtin: str) -> Optional[str]:
    return _gtin_to_sku(gtin, indices=get_indices())

# =====================================================================
# Fachadas legadas (retrocompat)
# =====================================================================

def listar_skus(camada: Camada = Camada.PP) -> List[str]:
    """Lista SKUs do PP (ordenados)."""
    data = carregar_pp(camada)
    return sorted(list(data["items"].keys()))

def get_itens(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    """Dict[sku] -> registro do produto (conforme PP)."""
    return carregar_pp(camada)["items"]

def listar_produtos(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    """
    Alias legado: produtos por SKU (dict) para chamadas antigas.
    Dashboards novos devem usar listar_produtos_raw()/listar_produtos_para_envio().
    """
    return get_itens(camada)

def get_por_sku(sku: str, camada: Camada = Camada.PP) -> Optional[Dict[str, Any]]:
    return get_itens(camada).get(sku)

def get_por_gtin(gtin: str, camada: Camada = Camada.PP) -> Optional[Dict[str, Any]]:
    for rec in get_itens(camada).values():
        if str(rec.get("gtin") or "").strip() == str(gtin).strip():
            return rec
    return None

def obter_custos_por_gtin(gtin: str) -> Optional[float]:
    rec = get_por_gtin(gtin)
    return rec.get("preco_compra") if rec else None

def listar_produtos_normalizado(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    """
    Retorna dict[sku]->registro com pesos/dimensões normalizados (kg/cm),
    preenchendo **somente** campos ausentes. Não grava nada.
    """
    base = listar_produtos(camada)
    out: Dict[str, Dict[str, Any]] = {}
    for sku, rec in base.items():
        rec2 = dict(rec)
        try:
            dims = normalize_peso_dimensoes(rec2)
            for k, v in (dims or {}).items():
                if rec2.get(k) in (None, "", [], {}):
                    rec2[k] = v
        except Exception:
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

# =====================================================================
# Preview de normalização a partir do Excel (opcional; só leitura)
# =====================================================================

try:
    from app.utils.produtos.aggregator import (
        carregar_excel_normalizado,
        carregar_excel_normalizado_detalhado,
    )
except Exception:
    carregar_excel_normalizado = None
    carregar_excel_normalizado_detalhado = None

def preview_normalizacao_excel() -> Dict[str, Dict[str, Any]]:
    if carregar_excel_normalizado is None:
        raise RuntimeError("Aggregator de produtos indisponível.")
    from app.utils.produtos.config import cadastro_produtos_excel
    return carregar_excel_normalizado(cadastro_produtos_excel())

def normalizar_excel_detalhado() -> Tuple[dict, list[dict]]:
    if carregar_excel_normalizado_detalhado is None:
        raise RuntimeError("Aggregator de produtos indisponível.")
    from app.utils.produtos.config import cadastro_produtos_excel
    return carregar_excel_normalizado_detalhado(cadastro_produtos_excel())
