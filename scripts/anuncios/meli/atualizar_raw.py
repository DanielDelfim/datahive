# scripts/anuncios/meli/atualizar_raw.py
from __future__ import annotations
import argparse
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.config.paths import (
    DATA_DIR, ML_API_BASE,
    get_loja_config, meli_client_credentials, backup_path,
)
from app.utils.meli.client import MeliClient  # usa _get() e from_tokens_json(...)

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

# ---------------- MELI: busca IDs e detalhes ----------------
def build_client_for_regiao(regiao: str) -> Tuple[MeliClient, str]:
    loja_cfg = get_loja_config(regiao)  # tokens + seller_id
    client_id, client_secret = meli_client_credentials(regiao)
    client = MeliClient.from_tokens_json(
        path=loja_cfg.tokens_path,
        client_id=client_id,
        client_secret=client_secret,
        api_base=ML_API_BASE,
    )
    return client, loja_cfg.seller_id

def fetch_all_item_ids(client: MeliClient, seller_id: str, limit: int = 50, max_pages: int = 1000) -> List[str]:
    """
    Lista itens do seller via /users/{seller_id}/items/search paginando por offset/limit.
    """
    ids: List[str] = []
    path = f"/users/{seller_id}/items/search"
    params = {"limit": limit, "offset": 0}
    page = 0
    while True:
        r = client._get(path, params=params)
        r.raise_for_status()
        data = r.json() or {}
        results = data.get("results") or []
        if not results:
            break
        ids.extend([str(x) for x in results])
        params["offset"] = int(params["offset"]) + limit
        page += 1
        if page >= max_pages:
            break
        # se a API informar total, podemos encerrar cedo
        total = int((data.get("paging") or {}).get("total") or 0)
        if total and len(ids) >= total:
            break
    return ids

def fetch_items_details(client: MeliClient, ids: List[str]) -> List[Dict[str, Any]]:
    """
    Baixa os detalhes de cada item via /items/{id}.
    (Simples e confiável; pode ser otimizado depois com endpoint em lote.)
    """
    items: List[Dict[str, Any]] = []
    for item_id in ids:
        r = client._get(f"/items/{item_id}")
        r.raise_for_status()
        items.append(r.json())
    return items

# ------------------------------- main -------------------------------
def main():
    ap = argparse.ArgumentParser(description="Atualiza RAW de anúncios (MELI) buscando TODOS os anúncios da loja.")
    ap.add_argument("--regiao", required=True, choices=["MG", "SP"], help="Região (MG ou SP)")
    ap.add_argument("--limit", type=int, default=50, help="Tamanho da página da busca de IDs (padrão: 50)")
    ap.add_argument("--max-pages", type=int, default=1000, help="Máximo de páginas para paginação (padrão: 1000)")
    args = ap.parse_args()

    regiao = args.regiao.upper()  # "MG" | "SP"
    client, seller_id = build_client_for_regiao(regiao.lower())

    # 1) Buscar todos os IDs
    ids = fetch_all_item_ids(client, seller_id, limit=args.limit, max_pages=args.max_pages)

    # 2) Baixar detalhes de cada item
    items = fetch_items_details(client, ids)

    # 3) Montar payload RAW (agora agregado)
    payload = {
        "fetched_at": datetime.now().isoformat(),
        "marketplace": "meli",
        "regiao": regiao.lower(),
        "seller_id": seller_id,
        "total": len(items),
        "items": items,
    }

    # 4) Persistir RAW (atômico + backup + rotação)
    target = anuncios_raw_path(regiao)
    atomic_write_json(target, payload, do_backup=True)
    rotate_backups(target, keep_last_n=2)

    print(f"OK: RAW atualizado ({len(items)} anúncios) em {target}")

if __name__ == "__main__":
    main()
