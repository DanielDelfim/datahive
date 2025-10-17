# C:\Apps\Datahive\app\utils\precificacao\config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

from app.config.paths import DATA_DIR, Marketplace, Regiao, Camada

# ======= Regras do domínio (YAML) =======
REGRAS_DIR = Path("app") / "utils" / "precificacao" / "regras"
REGRAS_ML_YAML = REGRAS_DIR / "mercado_livre.yaml"
REGRAS_OVERRIDES_YAML = REGRAS_DIR / "overrides.yaml"


def get_overrides_yaml_path() -> Path:
    return REGRAS_OVERRIDES_YAML

# ======= Período (para _meta) =======
@dataclass(frozen=True)
class Periodo:
    ano: int
    mes: int

_OVERRIDES_CACHE = None

def reset_overrides_cache():
    global _OVERRIDES_CACHE
    _OVERRIDES_CACHE = None

def get_overrides_ml() -> dict:
    """
    Carrega overrides.yaml (se existir). Retorna {} se ausente.
    Chaves esperadas:
      - por_item: { <mlb|sku|gtin>: { ...*_override, vigencia?, campanha_id? } }
      - cenarios: { <nome>: { ...*_override } }
    """
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None:
        return _OVERRIDES_CACHE
    import yaml  # PyYAML
    p = get_overrides_yaml_path()
    if not p.exists():
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE
    with open(p, "r", encoding="utf-8") as f:
        _OVERRIDES_CACHE = yaml.safe_load(f) or {}
    return _OVERRIDES_CACHE

def _reg(reg: Union[Regiao, str]) -> str:
    return reg.value if isinstance(reg, Regiao) else str(reg).lower()

# ======= Paths canônicos por região =======
def get_precificacao_out_dir(regiao: Union[Regiao, str]) -> Path:
    return DATA_DIR / "precificacao" / Marketplace.MELI.value / _reg(regiao) / Camada.PP.value

def get_precificacao_dataset_path(regiao: Union[Regiao, str]) -> Path:
    return get_precificacao_out_dir(regiao) / "dataset_precificacao.json"

def get_precificacao_metrics_path(regiao: Union[Regiao, str]) -> Path:
    return get_precificacao_out_dir(regiao) / "dataset_precificacao_metrics.json"

def get_anuncios_pp_path(regiao: Union[Regiao, str]) -> Path:
    return DATA_DIR / "marketplaces" / "meli" / "anuncios" / Camada.PP.value / f"anuncios_{_reg(regiao)}_pp.json"

# alias para o dashboard
def get_anuncios_path(regiao: str) -> Path:
    return get_anuncios_pp_path(regiao)

def get_produtos_pp_path() -> Path:
    return DATA_DIR / "produtos" / Camada.PP.value / "produtos.json"

def get_regras_meli_yaml_path() -> Path:
    return REGRAS_ML_YAML
