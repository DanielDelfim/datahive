# app/utils/vendas/amazon/service.py
from __future__ import annotations
import hashlib
import json
import time
from typing import Any, Dict, List
from pathlib import Path

from app.utils.amazon.client import AmazonSpApiClient
from app.utils.amazon import config as amz_cfg
from app.utils.vendas.amazon.aggregator import listar_pedidos_intervalo
from app.config.paths import (
    DATA_DIR, Marketplace, Regiao, Camada,
    ensure_dir,
)

def _hash_rows(rows: List[Dict[str, Any]]) -> str:
    s = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def obter_pedidos_por_periodo(inicio_utc: str, fim_utc: str, regiao: Regiao) -> Dict[str, Any]:
    """
    Service (fachada): não grava. Retorna dict com _meta + rows.
    """
    cli = AmazonSpApiClient(
        base_url=amz_cfg.API_BASE_URL,
        client_id=amz_cfg.LWA_CLIENT_ID,
        client_secret=amz_cfg.LWA_CLIENT_SECRET,
        refresh_token=amz_cfg.LWA_REFRESH_TOKEN_BR,
        user_agent=amz_cfg.USER_AGENT,
    )
    rows = listar_pedidos_intervalo(cli, inicio_utc, fim_utc)

    return {
        "_meta": {
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stage": "dev",
            "marketplace": Marketplace.AMAZON.value,
            "regiao": regiao.value,
            "camada": Camada.PP.value,
            "schema_version": "1.0.0",
            "script_name": "obter_pedidos_current",
            "script_version": "1.0.0",
            "source_paths": [],
            "row_count": len(rows),
            "hash": _hash_rows(rows),
        },
        "rows": rows,
    }

def destino_pp_current(regiao: Regiao) -> Path:
    """
    data/marketplaces/amazon/vendas/pp/current/<regiao>/orders_current_<regiao>.json
    """
    return ensure_dir(
        DATA_DIR / "marketplaces" / Marketplace.AMAZON.value / "vendas" / Camada.PP.value / "current" / regiao.value
    ) / f"orders_current_{regiao.value}.json"
