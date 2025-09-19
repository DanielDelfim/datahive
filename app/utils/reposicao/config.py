# app/utils/reposicao/config.py
from __future__ import annotations
from pathlib import Path
from typing import Literal
from app.config.paths import DATA_DIR, LOGS_DIR, ensure_dir  # fonte única

LojaStr = Literal["mg", "sp"]
RETENCAO_BACKUPS: int = 2

def BASE_DIR() -> Path:
    # data/marketplaces/meli/reposicao/
    d = DATA_DIR / "marketplaces" / "meli" / "reposicao"
    return ensure_dir(d)

def RESULTS_DIR() -> Path:
    # data/marketplaces/meli/reposicao/results/
    d = BASE_DIR() / "results"
    return ensure_dir(d)

def CACHE_DIR() -> Path:
    d = BASE_DIR() / "cache"
    return ensure_dir(d)

def REPORTS_DIR() -> Path:
    d = BASE_DIR() / "reports"
    return ensure_dir(d)

def BACKUPS_DIR() -> Path:
    d = BASE_DIR() / "backups"
    return ensure_dir(d)

def LOG_DIR() -> Path:
    d = LOGS_DIR / "meli" / "reposicao"
    return ensure_dir(d)

def janela_slug(janela: str | int) -> str:
    if isinstance(janela, int):
        return f"{max(1, janela)}d"
    s = str(janela).strip().lower()
    if s.endswith("d") and s[:-1].isdigit():
        return f"{int(s[:-1])}d"
    if s.isdigit():
        return f"{int(s)}d"
    MAP = {"7d": "7d", "15d": "15d", "30d": "30d"}
    return MAP.get(s, "7d")

def resultado_latest_json(loja: LojaStr) -> Path:
    """
    Ex.: data/marketplaces/meli/reposicao/results/reposicao_sp_latest.json
    """
    base = RESULTS_DIR()
    return base / f"reposicao_{loja.lower()}_latest.json"

def resultado_dated_json(loja: LojaStr, janela: str | int, stamp: str) -> Path:
    """
    Ex.: data/marketplaces/meli/reposicao/results/reposicao_sp_7d_20250919_101530.json
    """
    base = RESULTS_DIR()
    return base / f"reposicao_{loja.lower()}_{janela_slug(janela)}_{stamp}.json"
