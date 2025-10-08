from __future__ import annotations
import sys
import datetime as dt
from pathlib import Path
from app.config.paths import (
    ML_API_BASE, get_loja_config, ensure_dirs,
    vendas_raw_json, meli_client_credentials
)
from app.utils.core.io import salvar_json
from app.utils.meli.client import MeliClient

USO = "Uso: python -m scripts.vendas.meli_vendas_fetch_one [sp|mg]"

def _agora_stamp():
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")

def _token_bundle(tokens_path: Path):
    from app.utils.core.io import ler_json
    data = ler_json(tokens_path)
    at = data.get("access_token")
    rt = data.get("refresh_token")
    if not at:
        raise RuntimeError(f"access_token ausente em {tokens_path}")
    return at, rt

def main(argv: list[str]) -> None:
    ensure_dirs()
    loja = (argv[1] if len(argv) > 1 else "mg").strip().lower()
    if loja not in ("sp", "mg"):
        raise SystemExit(USO)

    cfg = get_loja_config(loja)
    if not cfg.seller_id:
        raise RuntimeError(f"SELLER_ID ausente no .env para loja={loja}")

    at, rt = _token_bundle(cfg.tokens_path)
    cid, csec = meli_client_credentials(loja)

    client = MeliClient(at, rt, cid, csec, api_base=ML_API_BASE)
    print(f"-> Buscando 1 venda ({loja.upper()}) seller_id={cfg.seller_id}")
    resp = client.get_last_order(cfg.seller_id)

    # RAW fixo
    out_path = vendas_raw_json(loja)
    salvar_json(out_path, resp)
    results = resp.get("results", [])
    print(f"✓ OK | pedidos_buscados={len(results)} | file={out_path}")

if __name__ == "__main__":
    main(sys.argv)
