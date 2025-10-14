from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.utils.anuncios.config import RAW_PATH_AMAZON as RAW_PATH

# === Paths + escrita: igual ao ML ===
from app.config.paths import (
    Regiao,
    atomic_write_json, list_backups_sorted_newest_first,
    LOGS_DIR,
)

# === FIX DO IMPORT: usamos a classe que existe no seu client ===
# (se quiser, mantenha o alias AmazonClient p/ não tocar no resto do código)

# retenção/backups igual ao módulo anúncios do ML
from app.utils.anuncios import config as anuncios_cfg

try:
    from dotenv import load_dotenv, find_dotenv
    _env_file = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[3] / ".env")
    load_dotenv(_env_file)
except Exception:
    pass

# Attempt to find and load a .env file; ignore errors if find/load fail.
_env_file = None
try:
    _env_file = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[3] / ".env")
except Exception:
    _env_file = None

try:
    if _env_file:
        load_dotenv(_env_file)
except Exception:
    pass

# -------- infra básica --------
def _setup_logger() -> None:
    log_dir = LOGS_DIR / "anuncios"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"amazon_atualizar_raw_{stamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    logging.info("Log em %s", log_file)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _build_client(regiao: Regiao):
    import os
    from pathlib import Path
    from app.utils.amazon.client import AmazonSpApiClient  # seu client real

    # ---- loader .env simples (sem dependências) ----
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
    # ------------------------------------------------

    # Prioriza SPAPI_*, cai para AMZ_* se faltarem
    base_url = (
        os.getenv("SPAPI_BASE_URL")
        or os.getenv("AMZ_API_BASE_URL")
        or "https://sellingpartnerapi-na.amazon.com"
    )
    client_id     = os.getenv("SPAPI_CLIENT_ID")        or os.getenv("AMZ_LWA_CLIENT_ID")
    client_secret = os.getenv("SPAPI_CLIENT_SECRET")    or os.getenv("AMZ_LWA_CLIENT_SECRET")
    refresh_token = os.getenv("SPAPI_REFRESH_TOKEN")    or os.getenv("AMZ_LWA_REFRESH_TOKEN_BR")
    user_agent    = os.getenv("SPAPI_USER_AGENT")       or os.getenv("AMZ_APP_USER_AGENT") or "Datahive/1.0"

    missing = [k for k, v in {
        "SPAPI_CLIENT_ID|AMZ_LWA_CLIENT_ID": client_id,
        "SPAPI_CLIENT_SECRET|AMZ_LWA_CLIENT_SECRET": client_secret,
        "SPAPI_REFRESH_TOKEN|AMZ_LWA_REFRESH_TOKEN_BR": refresh_token,
    }.items() if not v]
    if missing:
        raise RuntimeError("Faltam variáveis SP-API/Amazon: " + ", ".join(missing))

    return AmazonSpApiClient(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        user_agent=user_agent,
    )

# -------- coleta Listings com paginação --------
# marketplaceId do Brasil (Amazon.com.br)
# no parse_args(), acrescente:
# ap.add_argument("--max-pages", type=int, default=200)

_BR_MKT = "A2Q3Y263D00KWC"

def _fetch_all_listings(cli, seller_id: str, max_pages: int = 200) -> list[dict]:
    """
    Varre Listings Items (2021-08-01) com paginação robusta.
    Proteções:
      - sem pageSize (usa default do endpoint)
      - corta por max_pages
      - break se nextToken faltar ou repetir
      - break se 0 itens por 3 páginas seguidas
      - 429: respeita Retry-After ou aplica backoff incremental
    """
    import time
    import logging

    rows: list[dict] = []
    path = f"/listings/2021-08-01/items/{seller_id}"

    # começamos SEM pageSize (o endpoint reclamou do nosso valor)
    base_params: dict = {"marketplaceIds": _BR_MKT}

    def _do_get(params: dict) -> dict:
        """GET com tratamento de 429/backoff e conversão para dict."""
        wait = 1.0
        while True:
            try:
                return cli.get(path, params=params)  # seu client já retorna dict
            except Exception as e:
                msg = str(e)
                # 429 - Too Many Requests
                if "429" in msg or "Too Many Requests" in msg:
                    # tenta honrar Retry-After se o client expuser headers (muitos wrappers não expõem)
                    # fallback: backoff exponencial cap 30s
                    time.sleep(wait)
                    wait = min(wait * 2.0, 30.0)
                    continue
                # 400 'Invalid pageSize' não deve acontecer pois não enviamos pageSize
                raise

    page = 0
    prev_token = None
    empty_streak = 0

    while True:
        if page >= max_pages:
            logging.warning("Interrompido por limite de páginas (%d).", max_pages)
            break

        params = dict(base_params)
        if prev_token:
            params["nextToken"] = prev_token

        resp = _do_get(params)
        items = resp.get("items") or resp.get("Items") or []
        if not isinstance(items, list):
            items = []

        if items:
            rows.extend(items)
            empty_streak = 0
        else:
            empty_streak += 1
            logging.info("Página %d: 0 itens (streak=%d).", page + 1, empty_streak)

        pag = resp.get("pagination") or resp.get("Pagination") or {}
        next_token = pag.get("nextToken") or pag.get("NextToken")

        # Breaks de segurança
        if not next_token:
            logging.info("Sem nextToken — fim da paginação (página %d).", page + 1)
            break
        if next_token == prev_token:
            logging.warning("nextToken repetido — encerrando para evitar loop (token=%s).", str(next_token)[:16])
            break
        if empty_streak >= 3:
            logging.warning("Três páginas seguidas sem itens — encerrando.")
            break

        prev_token = next_token
        page += 1

        # log leve a cada 5 páginas
        if page % 5 == 0:
            logging.info("Progresso: %d páginas, %d itens acumulados.", page, len(rows))

    logging.info("Listings coletados (Amazon): %d itens em %d páginas.", len(rows), page + 1)
    return rows


# -------- persistência RAW com rotação (sem data no caminho) --------
def _persist_raw(regiao: Regiao, payload: Dict[str, Any]) -> Path:
    target = RAW_PATH(regiao.value) 
    logging.info("Gravando RAW Amazon em %s ...", target)
    atomic_write_json(target, payload, do_backup=True)

    keep = getattr(anuncios_cfg, "RETENCAO_BACKUPS", 2)
    backups = list_backups_sorted_newest_first(target)
    removed = 0
    for old in backups[keep:]:
        try:
            old.unlink()
            removed += 1
        except FileNotFoundError:
            pass
    logging.info("Backups mantidos=%d | removidos=%d", min(len(backups), keep), removed)
    return target


def run_for_regiao(regiao: Regiao, seller_id: str | None = None, max_pages: int = 200) -> Path:
    import os
    seller_id = (
        seller_id
        or os.getenv("SPAPI_SELLER_ID")
        or os.getenv("AMZ_SELLER_ID_BR")
        or os.getenv("AMAZON_SELLER_ID")
    )
    if not seller_id:
        raise RuntimeError("Defina o sellerId via --seller-id ou .env")

    cli = _build_client(regiao)
    rows = _fetch_all_listings(cli, seller_id, max_pages=max_pages)
    payload = {
        "metadata": {
            "generated_at": _now_utc(),
            "marketplace": "amazon",
            "regiao": regiao.value,
            "count": len(rows),
            "source": "SP-API Listings Items 2021-08-01",
            "seller_id": seller_id,
        },
        "items": rows,
    }
    return _persist_raw(regiao, payload)

def main() -> None:
    _setup_logger()
    ap = argparse.ArgumentParser(description="Atualiza anúncios RAW Amazon (SP/MG).")
    ap.add_argument("--regiao", choices=["sp", "mg", "ambas"], type=lambda s: s.lower(), default="ambas")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--seller-id", dest="seller_id")  # ← ADICIONE ESTA LINHA
    args = ap.parse_args()

    regioes = [Regiao.SP, Regiao.MG] if args.regiao == "ambas" else [Regiao(args.regiao)]
    for r in regioes:
        try:
            path = run_for_regiao(r, seller_id=getattr(args, "seller_id", None), max_pages=args.max_pages)
            logging.info("✓ RAW Amazon atualizado para %s em %s", r.value.upper(), path)
        except Exception:
            logging.exception("Falha ao atualizar RAW Amazon para %s", r.value.upper())


if __name__ == "__main__":
    main()
