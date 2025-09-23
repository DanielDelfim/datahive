# scripts/anuncios/meli/atualizar_raw.py
from __future__ import annotations
import argparse
import json
import random
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from app.config.paths import (
    DATA_DIR, ML_API_BASE,
    get_loja_config, meli_client_credentials, backup_path,
)
from app.utils.meli.client import MeliClient  # from_tokens_json(), _get(...)
from app.utils.core.result_sink.service import resolve_sink_from_flags  # stdout/json sink

# ---------------- util: dirs, atomic write, backups ----------------
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def atomic_write_json(target: Path, obj: Any, do_backup: bool = True) -> None:
    target = Path(target)
    ensure_dir(target.parent)
    if do_backup and target.exists():
        bkp = backup_path(target)
        ensure_dir(bkp.parent)
        with target.open("rb") as src, bkp.open("wb") as dst:
            dst.write(src.read())
    tmp = Path(tempfile.gettempdir()) / f".{target.name}.tmp"
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(target)

def list_backups_sorted_newest_first(target: Path) -> List[Path]:
    bdir = target.parent / "backups"
    if not bdir.exists():
        return []
    prefix = f"{target.stem}_"
    return sorted(
        [p for p in bdir.glob(f"{prefix}*{target.suffix}") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

def rotate_backups(target: Path, keep_last_n: int = 2) -> None:
    try:
        backups = list_backups_sorted_newest_first(target)
        for p in backups[keep_last_n:]:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

# ---------------- paths do domínio anúncios ----------------
def anuncios_raw_path(regiao: str) -> Path:
    base = DATA_DIR / "marketplaces" / "meli" / "anuncios" / "raw"
    ensure_dir(base)
    return base / f"anuncios_{regiao.lower()}_raw.json"

# ---------------- helpers de resiliência ----------------
def _should_retry_status(code: int) -> bool:
    return code in (429, 500, 502, 503, 504)

def _sleep_backoff(base: float, attempt: int) -> None:
    time.sleep((base ** attempt) + random.uniform(0, 0.5))

# ---------------- MELI: client, busca IDs e detalhes ----------------
def build_client_for_regiao(regiao: str) -> Tuple[MeliClient, str]:
    loja_cfg = get_loja_config(regiao)  # tokens + seller_id
    cid, csec = meli_client_credentials(regiao)
    client = MeliClient.from_tokens_json(
        path=loja_cfg.tokens_path,
        client_id=cid,
        client_secret=csec,
        api_base=ML_API_BASE,
    )
    return client, loja_cfg.seller_id

def fetch_all_item_ids(
    client: MeliClient,
    seller_id: str,
    *,
    limit: int = 50,
    max_pages: int = 1000,
    status: str | None = None,
    max_retries: int = 4,
    backoff_base: float = 1.25,
) -> List[str]:
    """
    Lista itens do seller via /users/{seller_id}/items/search paginando por offset/limit,
    com retentativas para 5xx/429 (sem 'timeout', pois MeliClient já define internamente).
    """
    ids: List[str] = []
    path = f"/users/{seller_id}/items/search"
    params: Dict[str, Any] = {"limit": limit, "offset": 0}
    if status:
        params["status"] = status

    page = 0
    while True:
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                r = client._get(path, params=params)  # _get não aceita timeout (usa 30s internamente)
                if _should_retry_status(r.status_code) and attempt < max_retries - 1:
                    _sleep_backoff(backoff_base, attempt)
                    continue
                r.raise_for_status()
                data = r.json() or {}
                results = data.get("results") or []
                if not results:
                    return ids
                ids.extend([str(x) for x in results])
                # próxima página
                params["offset"] = int(params["offset"]) + limit
                page += 1
                # limites
                if page >= max_pages:
                    return ids
                total = int((data.get("paging") or {}).get("total") or 0)
                if total and len(ids) >= total:
                    return ids
                break  # sucesso na página
            except requests.RequestException as e:
                last_exc = e
                if attempt < max_retries - 1:
                    _sleep_backoff(backoff_base, attempt)
                    continue
                raise
        if last_exc:
            raise last_exc

def fetch_items_details(
    client: MeliClient,
    ids: List[str],
    *,
    max_retries: int = 4,
    backoff_base: float = 1.25,
) -> List[Dict[str, Any]]:
    """
    Baixa os detalhes de cada item via /items/{id}, com retentativas (5xx/429).
    Coleta parcial > falha total: se um ID falhar permanentemente, seguimos.
    """
    items: List[Dict[str, Any]] = []
    for idx, item_id in enumerate(ids, 1):
        for attempt in range(max_retries):
            try:
                r = client._get(f"/items/{item_id}")
                if _should_retry_status(r.status_code) and attempt < max_retries - 1:
                    _sleep_backoff(backoff_base, attempt)
                    continue
                r.raise_for_status()
                items.append(r.json())
                break
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    _sleep_backoff(backoff_base, attempt)
                    continue
                # Marca erro mas não interrompe
                items.append({"id": item_id, "_error": str(e)})
                break
    return items

# ------------------------------- main -------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Atualiza RAW de anúncios (MELI) buscando TODOS os anúncios da loja.")
    ap.add_argument("--regiao", required=True, choices=["MG", "SP"], help="Região (MG ou SP)")
    ap.add_argument("--limit", type=int, default=50, help="Tamanho da página da busca de IDs (padrão: 50)")
    ap.add_argument("--max-pages", type=int, default=1000, help="Máximo de páginas para paginação (padrão: 1000)")
    ap.add_argument("--status", choices=["active", "paused", "closed"], help="Filtrar itens por status (opcional)")
    ap.add_argument("--max-retries", type=int, default=4, help="Máximo de retentativas (paginador e detalhes)")
    ap.add_argument("--backoff-base", type=float, default=1.25, help="Base do backoff exponencial (segundos)")

    # result sink (relatório)
    ap.add_argument("--to-file", dest="to_file", action="store_true", help="Salvar relatório JSON")
    ap.add_argument("--no-to-file", dest="to_file", action="store_false")
    ap.set_defaults(to_file=True)
    ap.add_argument("--stdout", dest="to_stdout", action="store_true", help="Imprimir relatório no terminal")
    ap.add_argument("--no-stdout", dest="to_stdout", action="store_false")
    ap.set_defaults(to_stdout=True)
    ap.add_argument("--outfile", help="Nome exato do relatório (opcional)")
    ap.add_argument("--prefix", default="anuncios_raw", help="Prefixo do relatório (JsonFileSink)")
    ap.add_argument("--keep", type=int, default=2, help="Qtd. de backups do relatório (JsonFileSink)")

    args = ap.parse_args()

    regiao = args.regiao.upper()
    client, seller_id = build_client_for_regiao(regiao.lower())

    t0 = time.time()

    # 1) IDs (resiliente)
    ids = fetch_all_item_ids(
        client, seller_id,
        limit=args.limit, max_pages=args.max_pages,
        status=args.status, max_retries=args.max_retries, backoff_base=args.backoff_base,
    )

    # 2) Detalhes (coleta parcial tolerada)
    items = fetch_items_details(
        client, ids,
        max_retries=args.max_retries, backoff_base=args.backoff_base,
    )

    # 3) RAW agregado
    payload = {
        "fetched_at": datetime.now().isoformat(),
        "marketplace": "meli",
        "regiao": regiao.lower(),
        "seller_id": seller_id,
        "total": len([x for x in items if "_error" not in x]),
        "items": items,
    }

    # 4) Persistir RAW (atômico + backups)
    target = anuncios_raw_path(regiao)
    atomic_write_json(target, payload, do_backup=True)
    rotate_backups(target, keep_last_n=2)

    # 5) Relatório via result_sink
    failed = [x.get("id") for x in items if isinstance(x, dict) and x.get("_error")]
    summary = {
        "path": str(target),
        "regiao": regiao.lower(),
        "seller_id": seller_id,
        "ids_coletados": len(ids),
        "itens_ok": len(items) - len(failed),
        "itens_falha": len(failed),
        "falhas_sample": failed[:5],
        "duracao_s": round(time.time() - t0, 2),
        "status_filter": args.status or "all",
        "page_limit": args.limit,
    }
    sink = resolve_sink_from_flags(
        to_file=args.to_file,
        to_stdout=args.to_stdout,
        output_dir=target.parent,
        prefix=args.prefix,
        keep=args.keep,
        filename=args.outfile,
    )
    sink.emit(summary, name=f"raw_{regiao.lower()}")

    print(f"OK: RAW atualizado ({summary['itens_ok']} anúncios) em {target}")

if __name__ == "__main__":
    main()
