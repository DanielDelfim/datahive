# app/utils/anuncios/config.py
from __future__ import annotations
from pathlib import Path
from typing import Literal

# Transversais (fonte única): raiz de dados + enums
from app.config.paths import DATA_DIR, Marketplace

RegiaoStr = Literal["mg", "sp"]

# Mantido p/ consumo externo; usado pelos scripts (ML e Amazon)
RETENCAO_BACKUPS = 2

# =========================
# MERCADO LIVRE (compat)
# =========================
def RAW_PATH(regiao: RegiaoStr) -> Path:
    """
    Caminho RAW (fixo) do ML — compatibilidade com código existente.
    Ex.: data/marketplaces/meli/anuncios/raw/anuncios_sp_raw.json
    """
    base = DATA_DIR / "marketplaces" / "meli" / "anuncios" / "raw"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"anuncios_{regiao}_raw.json"

def PP_PATH(regiao: RegiaoStr) -> Path:
    """
    Caminho PP current do ML — compatibilidade com código existente.
    Ex.: data/marketplaces/meli/anuncios/pp/current/sp/anuncios_current_sp.json
    """
    base = DATA_DIR / "marketplaces" / "meli" / "anuncios" / "pp" / "current" / regiao
    base.mkdir(parents=True, exist_ok=True)
    return base / f"anuncios_current_{regiao}.json"

# =========================
# AMAZON (NOVO)
# =========================
def RAW_PATH_AMAZON(regiao: RegiaoStr) -> Path:
    """
    Caminho RAW (fixo) da Amazon.
    Ex.: data/marketplaces/amazon/anuncios/raw/anuncios_sp_raw.json
    """
    base = DATA_DIR / "marketplaces" / "amazon" / "anuncios" / "raw"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"anuncios_{regiao}_raw.json"

def PP_PATH_AMAZON(regiao: RegiaoStr) -> Path:
    """
    Caminho PP current da Amazon.
    Ex.: data/marketplaces/amazon/anuncios/pp/current/sp/anuncios_current_sp.json
    """
    base = DATA_DIR / "marketplaces" / "amazon" / "anuncios" / "pp" / "current" / regiao
    base.mkdir(parents=True, exist_ok=True)
    return base / f"anuncios_current_{regiao}.json"

# =========================
# Facades genéricos (opcional)
# =========================
def raw_path(market: Marketplace, regiao: RegiaoStr) -> Path:
    if market == Marketplace.MELI:
        return RAW_PATH(regiao)
    if market == Marketplace.AMAZON:
        return RAW_PATH_AMAZON(regiao)
    raise NotImplementedError(f"raw_path: marketplace não suportado: {market}")

def pp_current_path(market: Marketplace, regiao: RegiaoStr) -> Path:
    if market == Marketplace.MELI:
        return PP_PATH(regiao)
    if market == Marketplace.AMAZON:
        return PP_PATH_AMAZON(regiao)
    raise NotImplementedError(f"pp_current_path: marketplace não suportado: {market}")

# =========================
# Auxiliares (existente)
# =========================
def cache_xml_dir() -> Path:
    d = DATA_DIR / "marketplaces" / "meli" / "anuncios" / "cache_xml"
    d.mkdir(parents=True, exist_ok=True)
    return d

CACHE_XML_DIR = cache_xml_dir()
