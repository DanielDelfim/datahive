# app/utils/anuncios/mappers/produto_ids.py
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Iterable, Optional

try:
    # opcional: normalizador central de GTIN, se existir no seu core
    from app.utils.core.identifiers import normalize_gtin as _normalize_gtin
except Exception:  # pragma: no cover
    def _normalize_gtin(v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        s = "".join(ch for ch in str(v) if ch.isdigit())
        return s or None

# ------------------------------------------------------------
# API PÚBLICA
# ------------------------------------------------------------

def resolver_gtin(
    chaves: Dict[str, Any],
    *,
    regiao: str,
) -> Optional[str]:
    """
    Resolve GTIN/EAN para um item, a partir de múltiplas chaves possíveis.

    Prioridade:
      1) gtin direto nas chaves
      2) mlb -> gtin (via PP anúncios)
      3) sku (seller_sku) -> gtin (via PP anúncios)
      4) asin -> gtin (se existir no PP; Amazon virá depois)
    """
    # 1) GTIN direto
    g = _normalize_gtin(chaves.get("gtin"))
    if g:
        return g

    # 2/3/4) via índices do PP
    idx = _get_indices_pp(regiao)

    mlb = _norm_key(chaves.get("mlb"))
    if mlb:
        g = idx.mlb_to_gtin.get(mlb)
        if g:
            return g

    sku = _norm_key(chaves.get("seller_sku") or chaves.get("sku"))
    if sku:
        g = idx.sku_to_gtin.get(sku)
        if g:
            return g

    asin = _norm_key(chaves.get("asin"))
    if asin:
        g = idx.asin_to_gtin.get(asin)
        if g:
            return g

    return None


def mlb_para_gtin(mlb: str, *, regiao: str) -> Optional[str]:
    """Atalho: MLB -> GTIN via PP anúncios."""
    if not mlb:
        return None
    idx = _get_indices_pp(regiao)
    return idx.mlb_to_gtin.get(_norm_key(mlb))


def sku_para_gtin(sku: str, *, regiao: str) -> Optional[str]:
    """Atalho: SellerSKU -> GTIN via PP anúncios."""
    if not sku:
        return None
    idx = _get_indices_pp(regiao)
    return idx.sku_to_gtin.get(_norm_key(sku))


def asin_para_gtin(asin: str, *, regiao: str) -> Optional[str]:
    """
    Atalho: ASIN -> GTIN (se já estiver presente no PP anúncios).
    Para Amazon 'de verdade', o ideal é enriquecer via Catalog Items (futuro).
    """
    if not asin:
        return None
    idx = _get_indices_pp(regiao)
    return idx.asin_to_gtin.get(_norm_key(asin))


def refresh_cache(regiao: Optional[str] = None) -> None:
    """
    Invalida o cache dos índices. Se regiao=None, invalida tudo.
    Use quando regenerar o PP (current) de anúncios.
    """
    if regiao is None:
        _get_indices_pp.cache_clear()
    else:
        # técnica: limpar tudo e reidratar apenas a região pedida
        _get_indices_pp.cache_clear()
        _ = _get_indices_pp(regiao)


# ------------------------------------------------------------
# ÍNDICES (internos)
# ------------------------------------------------------------

class _IndicesPP:
    __slots__ = ("mlb_to_gtin", "sku_to_gtin", "asin_to_gtin")

    def __init__(self) -> None:
        self.mlb_to_gtin: Dict[str, str] = {}
        self.sku_to_gtin: Dict[str, str] = {}
        self.asin_to_gtin: Dict[str, str] = {}


@lru_cache(maxsize=16)
def _get_indices_pp(regiao: str) -> _IndicesPP:
    """
    Constrói índices a partir do PP 'current' de anúncios daquela região.
    Usa o service do domínio anúncios (já preparado no projeto).
    """
    from app.utils.anuncios.service import listar_anuncios  # import tardio p/ evitar ciclos

    idx = _IndicesPP()
    rows = listar_anuncios(regiao)

    for row in _iter_rows(rows):
        mlb = _norm_key(row.get("mlb"))
        sku = _norm_key(row.get("seller_sku") or row.get("sku"))
        asin = _norm_key(row.get("asin"))
        gtin = _best_effort_gtin(row)

        if gtin:
            if mlb:
                idx.mlb_to_gtin.setdefault(mlb, gtin)
            if sku:
                idx.sku_to_gtin.setdefault(sku, gtin)
            if asin:
                idx.asin_to_gtin.setdefault(asin, gtin)

    return idx


# ------------------------------------------------------------
# HELPERS (internos)
# ------------------------------------------------------------

def _iter_rows(rows: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(rows, dict) and "data" in rows:
        rows = rows.get("data") or []
    if not isinstance(rows, Iterable):
        return []
    for r in rows:
        if isinstance(r, dict):
            yield r


def _best_effort_gtin(row: Dict[str, Any]) -> Optional[str]:
    """
    Extrai GTIN do registro PP usando heurísticas comuns:
      - chave direta 'gtin'
      - attributes[].id in {'EAN','GTIN','GTIN-13','GTIN_13'} ou name contendo 'ean'/'gtin'
      - variantes: 'ean', 'barcode'
    """
    # 1) direto
    g = _normalize_gtin(row.get("gtin") or row.get("ean") or row.get("barcode"))
    if g:
        return g

    # 2) attributes (padrão Mercado Livre)
    attrs = row.get("attributes") or []
    for a in attrs if isinstance(attrs, list) else []:
        # formatos possíveis
        cand = (
            a.get("value") or a.get("value_name") or a.get("value_id") or a.get("value_struct")
        )
        k_id = (a.get("id") or "").strip().upper()
        k_nm = (a.get("name") or "").strip().lower()

        # valores em str/dict
        if isinstance(cand, dict):
            # alguns schemas trazem em {"code": "789..."} etc.
            for v in cand.values():
                g = _normalize_gtin(v)
                if g:
                    return g
        else:
            g = _normalize_gtin(cand)
            if g:
                # conferimos se o atributo é plausível para GTIN
                if k_id in {"GTIN", "EAN", "GTIN-13", "GTIN_13"} or ("gtin" in k_nm or "ean" in k_nm):
                    return g

    # 3) nada encontrado
    return None


def _norm_key(v: Any) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip()
    return s or None
