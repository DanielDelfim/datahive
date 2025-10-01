from __future__ import annotations
from pathlib import Path
from typing import Literal
from app.config.paths import (
    anuncios_json, Marketplace, Camada, Regiao, DATA_DIR
)

RegiaoStr = Literal["mg", "sp"]

# Mantido para consumo externo; usado pelo script de atualização.
RETENCAO_BACKUPS = 2

# (Opcional) diretórios auxiliares não-críticos do domínio de anúncios.
def cache_xml_dir() -> Path:
    d = (DATA_DIR / "marketplaces" / "meli" / "anuncios" / "cache_xml")
    d.mkdir(parents=True, exist_ok=True)
    return d

def RAW_PATH(regiao: RegiaoStr) -> Path:
    """Delegado aos paths centralizados (fonte única)."""
    return anuncios_json(Marketplace.MELI, Camada.RAW, Regiao(regiao))

def PP_PATH(regiao: RegiaoStr) -> Path:
    """Delegado aos paths centralizados (fonte única)."""
    return anuncios_json(Marketplace.MELI, Camada.PP, Regiao(regiao))

CACHE_XML_DIR = cache_xml_dir()