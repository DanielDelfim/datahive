
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

    def _dedupe_preserve_order(seq):
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    orig = ids
    ids = _dedupe_preserve_order(ids)
    if len(ids) != len(orig):
        logging.info(
            "Removidos %d IDs duplicados antes do bulk (de %d para %d).",
            len(orig) - len(ids), len(orig), len(ids)
        )
    return ids  # <<< FALTAVA ESTE RETURN



def _fetch_items_details(cli: MeliClient, ids: List[str]) -> List[Dict[str, Any]]:
    logging.info("Baixando detalhes em lote ...")
    items = cli.get_items_bulk(ids)

    # dedup por 'id' preservando ordem
    seen, items_dedup = set(), []
    for it in items:
        k = str(it.get("id") or "")
        if k and k not in seen:
            seen.add(k)
            items_dedup.append(it)

    if len(items_dedup) != len(items):
        logging.info(
            "Removidos %d itens duplicados após o bulk (de %d para %d).",
            len(items) - len(items_dedup), len(items), len(items_dedup)
        )
    return items_dedup  # <<< FALTAVA ESTE RETURN




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

    ids = _fetch_all_items(cli, seller_id)          # agora retorna dedup
    items = _fetch_items_details(cli, ids)          # agora retorna dedup

    # blindagem extra antes de gravar
    seen, unique_items = set(), []
    for it in items:
        k = str(it.get("id") or "")
        if k and k not in seen:
            seen.add(k)
            unique_items.append(it)
    items = unique_items

    # sanity (opcional): logar se vier algo repetido
    from collections import Counter
    ids_list = [str(i.get("id") or "") for i in items]
    dups = [k for k, c in Counter(ids_list).items() if c > 1 and k]
    if dups:
        logging.warning("Ainda há IDs duplicados no payload: %s", dups)

    payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "marketplace": Marketplace.MELI.value,
            "regiao": regiao.value,
            "seller_id": seller_id,
            "count": len(items),  # contar APÓS a dedup
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
