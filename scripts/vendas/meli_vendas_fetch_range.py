# scripts/vendas/meli_vendas_fetch_range.py
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Tuple
from pathlib import Path

from app.config.paths import (
    APP_TIMEZONE, ML_API_BASE, ensure_dirs, get_loja_config,
    vendas_raw_json, meli_client_credentials,
)
from app.utils.core.io import salvar_json, ler_json
from app.utils.meli.client import MeliClient

USO = "Uso: python -m scripts.vendas.meli_vendas_fetch_range [sp|mg] [--days 60]"

def _parse_args(argv: list[str]) -> Tuple[str, int]:
    loja = (argv[1] if len(argv) > 1 else "").strip().lower()
    if loja not in ("sp", "mg"):
        raise SystemExit(USO)
    days = 60
    if "--days" in argv:
        i = argv.index("--days")
        if i + 1 < len(argv):
            try:
                days = int(argv[i + 1])
            except ValueError:
                pass
    return loja, days

def _token_bundle(tokens_path: Path) -> Tuple[str, str | None]:
    data = ler_json(tokens_path)
    at = data.get("access_token")
    rt = data.get("refresh_token")
    if not at:
        raise RuntimeError(f"access_token ausente em {tokens_path}")
    return at, rt

def main(argv: list[str]) -> None:
    ensure_dirs()
    loja, days = _parse_args(argv)

    cfg = get_loja_config(loja)
    if not cfg.seller_id:
        raise RuntimeError(f"SELLER_ID ausente no .env para loja={loja}")

    at, rt = _token_bundle(cfg.tokens_path)
    cid, csec = meli_client_credentials(loja)

    client = MeliClient(at, rt, cid, csec, api_base=ML_API_BASE)

    # Janela [agora-days, agora] no fuso do projeto
    tz = ZoneInfo(APP_TIMEZONE)
    dt_to = datetime.now(tz)
    dt_from = dt_to - timedelta(days=days)
    iso_from = dt_from.isoformat(timespec="seconds")   # ex.: 2025-07-01T00:00:00-03:00
    iso_to   = dt_to.isoformat(timespec="seconds")

    print(f"→ Buscando pedidos de {loja.upper()} de {iso_from} até {iso_to} (fuso={APP_TIMEZONE})")
    data = client.search_orders_range(cfg.seller_id, iso_from, iso_to, limit=50)

    # Acrescenta metadados e salva no RAW fixo
    payload = {
        "window": {
            "from": iso_from,
            "to": iso_to,
            "timezone": APP_TIMEZONE,
            "days": days,
        },
        "paging": data.get("paging", {}),
        "results": data.get("results", []),
    }
    out = vendas_raw_json(loja)
    salvar_json(out, payload)  # atômico + backup
    print(f"✓ RAW atualizado: {out} | total={payload['paging'].get('total', len(payload['results']))}")

if __name__ == "__main__":
    main(sys.argv)
