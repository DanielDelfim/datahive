from __future__ import annotations
from typing import Dict, List

def montar_base_precificacao(
    anuncios: List[dict],
    produtos_index: Dict[str, dict],
) -> List[dict]:
    """
    Une anúncios (por ML) com cadastro de produtos (preço de compra) via GTIN.
    Não realiza cálculos de MCP/ACoS/TACoS agora. Somente estrutura os campos.
    """
    out: List[dict] = []

    for ad in anuncios:
        gtin = (ad.get("gtin") or "").strip()
        prod = produtos_index.get(gtin, {}) if gtin else {}
        preco_compra = prod.get("preco_compra")

        item = {
            # chaves do anúncio
            "mlb": ad.get("mlb") or ad.get("id"),
            "gtin": gtin or None,
            "sku": ad.get("seller_sku") or ad.get("sku"),
            "titulo_anuncio": ad.get("title"),
            "price_atual": ad.get("price"),
            "status": ad.get("status"),
            "logistic_type": ad.get("logistic_type"),
            "listing_type_id": ad.get("listing_type_id"),
            "permalink": ad.get("permalink"),
            # chaves do produto
            "titulo_produto": prod.get("titulo") or prod.get("nome"),
            "marca": prod.get("marca"),
            "preco_compra": preco_compra,
            "fonte_preco_compra": "produtos.json" if preco_compra is not None else None,
            # placeholders para futura etapa de métricas/cálculo
            "preco_minimo": None,
            "preco_maximo": None,
            "mcp_atual": None,
            "mcp_simulado": None,
        }
        out.append(item)

    return out
