from __future__ import annotations
from typing import Dict, List

def montar_base_precificacao(
    anuncios: List[dict],
    produtos_index: Dict[object, dict],  # pode ter chaves str ou int
) -> List[dict]:
    """
    Une anúncios com cadastro de produtos via GTIN.
    Não calcula MCP aqui — apenas estrutura os campos e injeta preco_compra.
    """
    out: List[dict] = []

    for ad in anuncios:
        gtin_raw = ad.get("gtin")
        gtin_str = str(gtin_raw).strip() if gtin_raw is not None else ""

        # --- match no índice de produtos (aceita str/int e zeros à esquerda) ---
        prod = {}
        if gtin_str:
            prod = produtos_index.get(gtin_str) or {}
            if not prod:
                try:
                    prod = produtos_index.get(int(gtin_str)) or {}
                except ValueError:
                    pass
            if not prod and gtin_str.startswith("0"):
                try:
                    prod = produtos_index.get(int(gtin_str.lstrip("0"))) or {}
                except ValueError:
                    pass

        preco_compra = prod.get("preco_compra")
        if preco_compra is not None:
            try:
                preco_compra = float(preco_compra)
            except (TypeError, ValueError):
                preco_compra = None  # invalida se vier ruim

        item = {
            # chaves do anúncio
            "mlb": ad.get("mlb") or ad.get("id"),
            "gtin": gtin_str or None,                   
            "sku": ad.get("seller_sku") or ad.get("sku"),
            "titulo_anuncio": ad.get("title"),
            "price_atual": ad.get("price"),
            "status": ad.get("status"),
            "logistic_type": ad.get("logistic_type"),
            "listing_type_id": ad.get("listing_type_id"),
            "permalink": ad.get("permalink"),
            # chaves/custos do produto
            "titulo_produto": prod.get("titulo") or prod.get("nome"),
            "marca": prod.get("marca"),
            "preco_compra": preco_compra,
            "fonte_preco_compra": "produtos.json" if preco_compra is not None else None,
            # placeholders para próxima etapa (metrics)
            "preco_minimo": None,
            "preco_maximo": None,
            "mcp_atual": None,
            "mcp_simulado": None,
        }
        if preco_compra is None:
            item.setdefault("warnings", []).append(
                f"preco_compra_ausente(gtin={gtin_str or '∅'})"
            )

        out.append(item)

    return out
