from __future__ import annotations
from pathlib import Path
from typing import Literal
from app.config.paths import DATA_DIR  # fonte única de paths

RegiaoStr = Literal["mg", "sp"]

RETENCAO_BACKUPS = 2

def base_dir() -> Path:
    # data/marketplaces/meli/anuncios/
    return (DATA_DIR / "marketplaces" / "meli" / "anuncios")

def raw_dir() -> Path:
    d = base_dir() / "raw"
    d.mkdir(parents=True, exist_ok=True)
    return d

def pp_dir() -> Path:
    d = base_dir() / "pp"
    d.mkdir(parents=True, exist_ok=True)
    return d

def backups_dir() -> Path:
    d = base_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d

def cache_xml_dir() -> Path:
    # reservado para caches de descrições/imagens, se necessário
    d = base_dir() / "cache_xml"
    d.mkdir(parents=True, exist_ok=True)
    return d

def RAW_PATH(regiao: RegiaoStr) -> Path:
    return raw_dir() / f"anuncios_{regiao.lower()}_raw.json"

def PP_PATH(regiao: RegiaoStr) -> Path:
    return pp_dir() / f"anuncios_{regiao.lower()}_pp.json"

# atalhos requisitados pelo enunciado
BACKUPS_DIR = backups_dir()
CACHE_XML_DIR = cache_xml_dir()
