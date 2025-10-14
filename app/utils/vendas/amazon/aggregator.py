# app/utils/vendas/amazon/agregador.py
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.utils.amazon.client import AmazonSpApiClient
from app.utils.amazon import config as amz_cfg

_ORDERS = "/orders/v0/orders"

def _iso(dt: str) -> str:
    # aceita "YYYY-MM-DD" ou "YYYY-MM-DDThh:mm:ssZ"
    return dt if "T" in dt else f"{dt}T00:00:00Z"

def listar_pedidos_intervalo(
    cli: AmazonSpApiClient,
    inicio_utc: str,
    fim_utc: str,
    marketplace_id: Optional[str] = None,
    status: Optional[List[str]] = None,
    max_per_page: int = 100,
) -> List[Dict[str, Any]]:
    """
    Lista pedidos no intervalo [inicio_utc, fim_utc] (ISO8601 Z).
    Retorna somente o cabeçalho (sem PII/RDT).
    """
    marketplace_id = marketplace_id or amz_cfg.MARKETPLACE_ID_BR
    params: Dict[str, Any] = {
        "MarketplaceIds": marketplace_id,
        "CreatedAfter": _iso(inicio_utc),
        "CreatedBefore": _iso(fim_utc),
        "MaxResultsPerPage": max_per_page,
    }
    if status:
        params["OrderStatuses"] = ",".join(status)

    orders: List[Dict[str, Any]] = []

    # primeira página
    resp = cli.get(_ORDERS + "?" + urlencode(params))
    orders.extend(resp.get("payload", {}).get("Orders", []))
    next_token = resp.get("payload", {}).get("NextToken")

    # paginação
    while next_token:
        resp = cli.get(_ORDERS + "?" + urlencode({"NextToken": next_token}))
        orders.extend(resp.get("payload", {}).get("Orders", []))
        next_token = resp.get("payload", {}).get("NextToken")
        time.sleep(0.2)  # cortesia de rate-limit

    # determinismo
    orders.sort(key=lambda o: str(o.get("AmazonOrderId", "")))
    return orders
