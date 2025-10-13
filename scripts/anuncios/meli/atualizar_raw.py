#C:\Apps\Datahive\scripts\anuncios\meli\atualizar_raw.py
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

def _fetch_all_item_ids(cli, seller_id: str) -> list[str]:
    """
    Varre TODOS os itens do seller usando cursor (scan + scroll_id), sem filtrar por status.
    """
    ids: list[str] = []
    scroll_id = None
    while True:
        params = {"seller_id": seller_id, "limit": 100, "search_type": "scan"}
        if scroll_id:
            params["scroll_id"] = scroll_id
        # >>> AQUI: interpolar o seller_id!
        resp = cli.get(f"/users/{seller_id}/items/search", params=params)
        batch = resp.get("results") or []
        ids.extend([str(x) for x in batch])
        scroll_id = resp.get("scroll_id")
        if not batch or not scroll_id:
            break
    # dedupe preservando ordem
    seen, out = set(), []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    logging.info("SCAN seller=%s → %d IDs", seller_id, len(out))
    return out

def _rescue_ids_by_gtin(cli, seller_id: str, gtin: str) -> list[str]:
    """
    Tenta localizar IDs do seller pelo GTIN:
    1) /users/{seller_id}/items/search?q=<gtin>
    2) /sites/MLB/search?q=<gtin>&seller_id=<seller_id>
    Retorna lista (pode vir 1 id).
    """
    ids = []

    # 1) search no /users
    r1 = cli.get(f"/users/{seller_id}/items/search", params={"q": gtin, "limit": 100})
    ids += [str(x) for x in (r1.get("results") or [])]

    # 2) search no /sites (às vezes encontra onde /users não traz)
    r2 = cli.get("/sites/MLB/search", params={"q": gtin, "seller_id": seller_id, "limit": 50})
    ids += [str(x.get('id')) for x in (r2.get("results") or []) if isinstance(x, dict) and x.get('id')]

    # dedupe
    seen, out = set(), []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out

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

def _has_gtin(item: dict, gtin: str) -> bool:
    g = str(item.get("gtin") or "").strip()
    if g == gtin: 
        return True
    for a in (item.get("attributes") or []):
        name = str(a.get("name") or a.get("id") or "").lower()
        if "ean" in name or "gtin" in name or "barcode" in name:
            v = str(a.get("value_name") or a.get("value_id") or a.get("value") or "").strip()
            if v == gtin:
                return True
            vals = a.get("values") or []
            if vals and str(vals[0].get("name") or "").strip() == gtin:
                return True
    return False

def _fetch_items_details(cli: MeliClient, ids: list[str]) -> list[dict]:
    import logging
    logging.info("Baixando detalhes em lote ...")

    resp = cli.get_items_bulk(ids)  # pode vir [{"code":200,"body":{...}}, {"code":404,...}, ...]
    items, misses = [], []

    # 1) Desembrulhar {code, body} e coletar "misses"
    for r in resp:
        if isinstance(r, dict) and "body" in r:
            code = r.get("code", 200)
            body = r.get("body")
            if code == 200 and isinstance(body, dict) and body.get("id"):
                items.append(body)
            else:
                misses.append(r)
        elif isinstance(r, dict) and r.get("id"):
            items.append(r)
        else:
            misses.append(r)

    # 2) Recuperar misses individualmente via GET /items/{id}, quando possível
    recov = []
    for m in misses:
        # tenta extrair o id que falhou
        mid = None
        if isinstance(m, dict):
            if "body" in m and isinstance(m["body"], dict):
                mid = m["body"].get("id")
            mid = mid or m.get("id") or m.get("item_id") or m.get("requested_id")
        if mid:
            try:
                one = cli.get_item(mid)  # GET /items/{id}
                if isinstance(one, dict) and one.get("id"):
                    recov.append(one)
            except Exception:
                pass

    if recov:
        logging.warning("Recuperados individualmente %d itens que falharam no bulk.", len(recov))
        items.extend(recov)

    # 3) Dedupe por 'id' preservando ordem
    seen, dedup = set(), []
    for it in items:
        k = str(it.get("id") or "")
        if k and k not in seen:
            seen.add(k)
            dedup.append(it)

    if len(dedup) != len(items):
        logging.info("Removidos %d duplicados no bulk (de %d para %d).", len(items)-len(dedup), len(items), len(dedup))

    return dedup

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

    # Rescue opcional por GTIN(s)
    watch_gtins = getattr(anuncios_cfg, "WATCH_GTINS", [])  # ou passe por CLI
    for g in watch_gtins:
        if not any(_has_gtin(it, g) for it in items):
            rescue_ids = _rescue_ids_by_gtin(cli, seller_id, g)
            if rescue_ids:
                rescued = _fetch_items_details(cli, rescue_ids)
                for r in rescued:
                    if isinstance(r, dict) and r.get("id"):
                        items.append(r)

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
