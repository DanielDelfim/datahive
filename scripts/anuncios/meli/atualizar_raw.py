
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from app.config.paths import (
    Marketplace, Regiao, Camada,
    get_loja_config, meli_client_credentials,
    anuncios_json, atomic_write_json, list_backups_sorted_newest_first,
    LOGS_DIR,
)

from app.utils.meli.client import MeliClient
# Quando executado direto (python scripts\anuncios\meli\atualizar_raw.py), __package__ pode estar vazio.
# Usamos import relativo se rodar com `-m`, e absoluto se rodar como script.

from app.utils.anuncios import config as anuncios_cfg


def _setup_logger() -> None:
    log_dir = (LOGS_DIR / "anuncios")
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"atualizar_raw_{stamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    logging.info("Log inicializado em %s", log_file)


def _build_client(loja: str) -> tuple[MeliClient, str]:
    cfg = get_loja_config(loja)  # seller_id + tokens_path
    client_id, client_secret = meli_client_credentials(loja)

    if not cfg.seller_id:
        raise RuntimeError(f"SELLER_ID ausente para loja={loja}.")
    if not Path(cfg.tokens_path).exists():
        raise RuntimeError(f"Tokens JSON ausente: {cfg.tokens_path}")

    # Base URL default do client é suficiente; não passamos api_base.
    cli = MeliClient.from_tokens_json(
        path=cfg.tokens_path,
        client_id=client_id,
        client_secret=client_secret,
    )
    return cli, cfg.seller_id


def _fetch_all_items(cli: MeliClient, seller_id: str) -> List[str]:
    logging.info("Listando MLBs do seller %s ...", seller_id)
    ids = cli.search_seller_items(seller_id=seller_id, limit=100)
    logging.info("Total de MLBs obtidos: %d", len(ids))
    return ids


def _fetch_items_details(cli: MeliClient, ids: List[str]) -> List[Dict[str, Any]]:
    logging.info("Baixando detalhes em lote ...")
    items = cli.get_items_bulk(ids)
    logging.info("Itens detalhados baixados: %d", len(items))
    return items


def _persist_raw(regiao: Regiao, payload: Dict[str, Any]) -> Path:
    target = anuncios_json(Marketplace.MELI, Camada.RAW, regiao)
    logging.info("Gravando RAW em %s ...", target)
    atomic_write_json(target, payload, do_backup=True)
    # retenção de backups (keep N mais recentes)
    keep = getattr(anuncios_cfg, "RETENCAO_BACKUPS", 2)
    backups = list_backups_sorted_newest_first(target)
    for old in backups[keep:]:
        try:
            old.unlink()
        except FileNotFoundError:
            pass
    logging.info("Backups mantidos: %d | removidos: %d", min(len(backups), keep), max(0, len(backups) - keep))
    return target


def run_for_regiao(regiao: Regiao) -> Path:
    loja = regiao.value  # "sp" / "mg"
    cli, seller_id = _build_client(loja)
    ids = _fetch_all_items(cli, seller_id)
    items = _fetch_items_details(cli, ids)
    payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "marketplace": Marketplace.MELI.value,
            "regiao": regiao.value,
            "seller_id": seller_id,
            "count": len(items),
            "source": "users/{seller}/items/search + items?ids",
        },
        "items": items,
    }
    return _persist_raw(regiao, payload)


def main() -> None:
    _setup_logger()
    parser = argparse.ArgumentParser(description="Atualiza anúncios RAW (SP/MG).")
    parser.add_argument("--regiao", choices=["sp", "mg", "ambas"], type=lambda s: s.lower(), default="ambas")
    args = parser.parse_args()

    regioes = [Regiao.SP, Regiao.MG] if args.regiao == "ambas" else [Regiao(args.regiao)]
    for r in regioes:
        try:
            path = run_for_regiao(r)
            logging.info("✓ RAW atualizado para %s em %s", r.value.upper(), path)
        except Exception as e:
            logging.exception("Falha ao atualizar RAW para %s: %s", r.value.upper(), e)


if __name__ == "__main__":
    main()
