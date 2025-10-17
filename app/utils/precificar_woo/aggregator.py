# app/utils/precificar_woo/aggregator.py
from __future__ import annotations
from typing import Any, Dict, List
from pathlib import Path
import logging
import yaml

from app.utils.produtos.service import listar_produtos
from .config import get_paths


# ------------------------- helpers -------------------------

def _safe_load_yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def _to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    # Trata "1.234,56" e "1234,56"
    if "," in s and s.count(",") == 1:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def _extract_title(p: dict) -> str:
    # Aliases planos mais comuns
    for k in ["title", "nome", "name", "titulo", "descricao", "descricao_comercial",
              "nome_produto", "produto_nome", "produto_titulo"]:
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # Aliases aninhados comuns
    nested_candidates = [
        (p.get("produto") or {}).get("nome"),
        (p.get("produto") or {}).get("titulo"),
        (p.get("dados") or {}).get("nome"),
        (p.get("dados") or {}).get("titulo"),
        (p.get("attributes") or {}).get("name"),
        (p.get("attributes") or {}).get("title"),
    ]
    for v in nested_candidates:
        if isinstance(v, str) and v.strip():
            return v.strip()

    return ""  # fallback tratado no _coerce_prod

def _extract_cost(p: dict) -> float:
    # Se você já ajustou o custo no service de produtos, pode simplificar.
    # Mantemos cobertura ampla para evitar zeros por diferença de chaves.
    cand = [
        p.get("preco_compra"),
        p.get("preco_custo"),
        p.get("custo"),
        p.get("custo_medio"),
        p.get("purchase_price"),
        p.get("cost"),
        (p.get("precos") or {}).get("compra"),
        (p.get("precos") or {}).get("custo"),
        (p.get("pricing") or {}).get("cost"),
    ]
    for v in cand:
        val = _to_float(v)
        if val > 0:
            return val
    return 0.0

def _coerce_prod(p: Any) -> Dict[str, Any]:
    """
    Normaliza um registro de produto para:
    {gtin, title, preco_compra}
    """
    if isinstance(p, dict):
        gtin = str(p.get("gtin") or p.get("GTIN") or p.get("ean") or p.get("codigo") or "").strip()
        if not gtin:
            return {}
        title = _extract_title(p)
        if not title:
            title = gtin  # fallback: mostra ao menos o GTIN
        preco_compra = _extract_cost(p)
        return {"gtin": gtin, "title": title, "preco_compra": preco_compra}

    if isinstance(p, (list, tuple)) and p:
        gtin = str(p[0]).strip()
        if not gtin:
            return {}
        # tuple/list: (gtin, custo, title?)
        preco_compra = _to_float(p[1]) if len(p) > 1 else 0.0
        title = (str(p[2]).strip() if len(p) > 2 and p[2] is not None else "") or gtin
        return {"gtin": gtin, "title": title, "preco_compra": preco_compra}

    if isinstance(p, str):
        s = p.strip()
        return {"gtin": s, "title": s, "preco_compra": 0.0} if s else {}

    return {}

# ------------------------- público -------------------------

def _iter_produtos(produtos_raw):
    if produtos_raw is None:
        return []
    if isinstance(produtos_raw, dict):
        return produtos_raw.values()  # itera só nos valores
    # já é lista/tupla/gerador
    return produtos_raw

def _sample_prod(produtos_raw):
    try:
        if isinstance(produtos_raw, dict):
            return next(iter(produtos_raw.values()))
        if isinstance(produtos_raw, (list, tuple)):
            return produtos_raw[0] if produtos_raw else None
        it = iter(produtos_raw)
        return next(it)
    except Exception:
        return None

def carregar_base() -> Dict[str, Any]:
    paths = get_paths()  # sem região
    regras = _safe_load_yaml(paths.regras_yaml)
    ovrs   = _safe_load_yaml(paths.overrides_yaml)

    produtos_raw = listar_produtos()

    # log de amostra sem depender de índice 0
    amostra = _sample_prod(produtos_raw)
    if amostra is None:
        logging.warning("listar_produtos() retornou vazio.")
    else:
        logging.debug(
            "Amostra produtos: type=%s keys=%s",
            type(amostra).__name__,
            list(amostra.keys()) if isinstance(amostra, dict) else "n/a"
        )

    itens: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for p in _iter_produtos(produtos_raw):
        it = _coerce_prod(p)
        if not it:
            continue
        gtin = it["gtin"]
        if gtin in seen:
            continue

        # Overrides por GTIN (opcionais)
        o = ((ovrs.get("por_item") or {}).get(gtin) or {})
        if "preco_compra_override" in o:
            it["preco_compra"] = _to_float(o["preco_compra_override"])
        if "mcp_min_override" in o:
            it["mcp_min_override"] = _to_float(o["mcp_min_override"])
        if "mcp_max_override" in o:
            it["mcp_max_override"] = _to_float(o["mcp_max_override"])
        if "title_override" in o:
            t = str(o["title_override"]).strip()
            if t:
                it["title"] = t

        seen.add(gtin)
        itens.append(it)

    return {"_meta": {"canal": "site"}, "regras": regras, "itens": itens}

