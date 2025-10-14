# scripts/anuncios/amazon/enriquecer_precos.py
from __future__ import annotations
import argparse
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import os
from pathlib import Path
from app.utils.amazon.client import AmazonSpApiClient

from app.utils.anuncios.config import PP_PATH_AMAZON
from app.utils.core.result_sink.json_file_sink import JsonFileSink


BR_MKT = "A2Q3Y263D00KWC"

# --- loader simples do .env + factory do client ---


def _load_env_fallback():
    root = Path(__file__).resolve().parents[3]  # C:\Apps\Datahive
    env_path = root / ".env"
    try:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass

_load_env_fallback()

def _build_client() -> AmazonSpApiClient:
    base_url = (
        os.getenv("SPAPI_BASE_URL")
        or os.getenv("AMZ_API_BASE_URL")
        or "https://sellingpartnerapi-na.amazon.com"
    )
    client_id     = os.getenv("SPAPI_CLIENT_ID")     or os.getenv("AMZ_LWA_CLIENT_ID")
    client_secret = os.getenv("SPAPI_CLIENT_SECRET") or os.getenv("AMZ_LWA_CLIENT_SECRET")
    refresh_token = os.getenv("SPAPI_REFRESH_TOKEN") or os.getenv("AMZ_LWA_REFRESH_TOKEN_BR")
    user_agent    = os.getenv("SPAPI_USER_AGENT")    or os.getenv("AMZ_APP_USER_AGENT") or "Datahive/1.0"

    missing = [k for k,v in {
        "SPAPI_CLIENT_ID|AMZ_LWA_CLIENT_ID": client_id,
        "SPAPI_CLIENT_SECRET|AMZ_LWA_CLIENT_SECRET": client_secret,
        "SPAPI_REFRESH_TOKEN|AMZ_LWA_REFRESH_TOKEN_BR": refresh_token,
    }.items() if not v]
    if missing:
        raise RuntimeError("Faltam credenciais SP-API: " + ", ".join(missing))

    return AmazonSpApiClient(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        user_agent=user_agent,
    )
# --- fim do loader/factory ---

def _price_from_offer(o: Dict[str, Any]) -> Optional[float]:
    # pega ListingPrice.Amount (fallback p/ LandedPrice)
    lp = o.get("ListingPrice") or o.get("listingPrice") or {}
    amt = lp.get("Amount") or lp.get("amount")
    if amt is None:
        lp = o.get("LandedPrice") or o.get("landedPrice") or {}
        amt = lp.get("Amount") or lp.get("amount")
    try:
        return float(amt) if amt is not None else None
    except Exception:
        return None

# REMOVA a função get_prices_for_asins_batch existente
# e COLE esta no lugar:



def get_prices_for_asins_bulk_get(cli, asins: list[str]) -> dict[str, float | None]:
    """
    Usa GET /products/pricing/v0/items com vários ASINs por chamada.
    - Aceita ~20 ASINs por requisição
    - Params exigem MarketplaceId (M maiúsculo), ItemType=Asin, ItemCondition=New
    Retorna {asin: price_or_None}.
    """
    out: dict[str, float | None] = {}
    if not asins:
        return out

    def _chunked(seq, n):
        for i in range(0, len(seq), n):
            yield seq[i:i+n]

    path = "/products/pricing/v0/items"
    for group in _chunked(asins, 20):
        params = {
            "MarketplaceId": "A2Q3Y263D00KWC",   # BR
            "ItemType": "Asin",
            "ItemCondition": "New",
            "Asins": ",".join(a for a in group),
        }
        resp = cli.get(path, params=params)  # client GET já funciona
        # Respostas possíveis:
        # - {"payload":[{"ASIN":"B0...","Offers":[...]}, ...]}
        # - ou direto com chave "Offers"/"Summary" em itens
        payload = resp.get("payload") or resp.get("Payload") or []
        if not isinstance(payload, list):
            payload = []

        for item in payload:
            asin = item.get("ASIN") or item.get("asin")
            offers = item.get("Offers") or item.get("offers") or []
            price = None
            if isinstance(offers, list) and offers:
                lp = offers[0].get("ListingPrice") or offers[0].get("listingPrice") or {}
                amt = lp.get("Amount") or lp.get("amount")
                try:
                    price = float(amt) if amt is not None else None
                except Exception:
                    price = None
            if asin:
                out[asin] = price
    return out



def get_price_for_sku(cli, sku: str):
    path = f"/products/pricing/v0/listings/{quote(str(sku), safe='')}/offers"
    r = cli.get(path, params={"MarketplaceId": BR_MKT, "ItemCondition": "New"})
    offers = r.get("Offers") or r.get("offers") or []
    if not offers:
        return None
    return _price_from_offer(offers[0])

def get_price_for_asin(cli, asin: str):
    path = f"/products/pricing/v0/items/{quote(str(asin), safe='')}/offers"
    r = cli.get(path, params={"MarketplaceId": BR_MKT, "ItemCondition": "New"})
    offers = r.get("Offers") or r.get("offers") or []
    if not offers:
        return None
    mine = [o for o in offers if o.get("SellerId")]
    return _price_from_offer(mine[0] if mine else offers[0])


def _digits_or_none(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    d = "".join(ch for ch in str(s) if ch.isdigit())
    return d if 8 <= len(d) <= 14 else None

def enrich_prices(regiao: str, keep: int, delay: float, only_missing: bool, limit: Optional[int]) -> int:
    cli = _build_client()  # seu client já lê .env / credenciais
    pp_path = PP_PATH_AMAZON(regiao)
    env = json.loads(pp_path.read_text(encoding="utf-8")) if pp_path.exists() else {"data": []}
    data: List[Dict[str, Any]] = env.get("data", [])

    updated = 0
    # 1) selecione os itens a processar
    # SELEÇÃO
    targets = [it for it in data if (not only_missing or it.get("price") is None)]
    if limit is not None:
        targets = targets[:limit]

    # 1ª PASSAGEM: GET em lote por ASIN (mais eficiente que 1-a-1)
    asins = [it.get("asin") for it in targets if it.get("asin")]
    prices_by_asin = get_prices_for_asins_bulk_get(cli, asins) if asins else {}

    updated = 0
    for it in targets:
        asin = it.get("asin")
        sku  = it.get("seller_sku")
        price = None

        # pegar do mapa do GET em lote
        if asin and asin in prices_by_asin:
            price = prices_by_asin[asin]

        # fallback pontual por SKU (GET individual, com MarketplaceId e ItemCondition corretos)
        if price is None and sku:
            try:
                path = f"/products/pricing/v0/listings/{quote(str(sku), safe='')}/offers"
                r = cli.get(path, params={"MarketplaceId": "A2Q3Y263D00KWC", "ItemCondition": "New"})
                offers = r.get("Offers") or r.get("offers") or []
                if offers:
                    lp = offers[0].get("ListingPrice") or {}
                    amt = lp.get("Amount")
                    price = float(amt) if amt is not None else None
            except Exception:
                price = None

        if price is not None:
            it["price"] = price
            it["currency"] = it.get("currency") or "BRL"
            updated += 1

        time.sleep(max(delay, 0.0))


    # escreve com rotação igual aos outros scripts
    sink = JsonFileSink(output_dir=pp_path.parent, filename=pp_path.name, keep=keep)
    env["_source"] = f"{env.get('_source','')} +pricing".strip()
    sink.emit(env)
    return updated

def main() -> int:
    ap = argparse.ArgumentParser(description="Enriquece preços no PP de anúncios Amazon.")
    ap.add_argument("--regiao", required=True, choices=["sp", "mg"], type=lambda s: s.lower())
    ap.add_argument("--keep", type=int, default=5, help="qtd de backups do PP")
    ap.add_argument("--delay", type=float, default=0.3, help="delay entre chamadas (s)")
    ap.add_argument("--all", dest="only_missing", action="store_false", help="atualiza todos (não só missing)")
    ap.add_argument("--limit", type=int, default=None, help="limite de itens processados (debug)")
    args = ap.parse_args()

    updated = enrich_prices(
        regiao=args.regiao,
        keep=args.keep,
        delay=args.delay,
        only_missing=args.only_missing,
        limit=args.limit,
    )
    print(f"Preços atualizados: {updated}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
