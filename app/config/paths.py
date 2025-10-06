from __future__ import annotations
import os
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

# ----------------------------- util internos -----------------------------
def _expand_path(p: str | os.PathLike | None) -> Optional[Path]:
    if p is None:
        return None
    s = str(p).strip().strip('"').strip("'")
    s = os.path.expandvars(os.path.expanduser(s))
    try:
        return Path(s).resolve()
    except Exception:
        return Path(s)

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def backup_path(target: Path) -> Path:
    """
    Retorna o caminho de backup padronizado para `target`,
    com timestamp no nome dentro de um diretório `backup` irmão.
    """
    target = Path(target)
    bdir = target.parent.parent / "backup" if target.parent.name in {"raw", "pp"} else target.parent / "backup"
    ensure_dir(bdir)
    stamp = f"{target.stem}_{get_timestamp()}{target.suffix}"
    return bdir / stamp

def atomic_write_json(target: Path, obj, do_backup: bool = True) -> None:
    """
    Escrita atômica de JSON com backup opcional do arquivo antigo.
    """
    target = Path(target)
    ensure_dir(target.parent)
    if do_backup and target.exists():
        shutil.copy2(target, backup_path(target))
    tmp = Path(tempfile.gettempdir()) / f".{target.name}.tmp"
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(target)

def list_backups_sorted_newest_first(target: Path) -> list[Path]:
    """
    Lista os backups do arquivo `target` ordenados do mais recente para o mais antigo.
    """
    target = Path(target)
    bdir = target.parent.parent / "backup" if target.parent.name in {"raw", "pp"} else target.parent / "backup"
    if not bdir.exists():
        return []
    prefix = f"{target.stem}_"
    files = [p for p in bdir.glob(f"{prefix}*{target.suffix}") if p.is_file()]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

# ----------------------------- Enums padrão ------------------------------
class Stage(str, Enum):
    DEV = "dev"
    PROD = "prod"

class Marketplace(str, Enum):
    MELI = "meli"
    AMAZON = "amazon"
    WOO = "woocommerce"

class Regiao(str, Enum):
    MG = "mg"
    SP = "sp"
    ES = "es"

class Camada(str, Enum):
    RAW = "raw"
    PP = "pp"
    EXCEL = "excel"
    RESULTS = "results"

# --------------------------- Variáveis de ambiente ------------------------
BASE_PATH   = _expand_path(os.getenv("BASE_PATH", r"C:/Apps/Datahive")) or Path(r"C:/Apps/Datahive")
DATA_DIR    = _expand_path(os.getenv("DATA_DIR", str(BASE_PATH / "data"))) or (BASE_PATH / "data")
TOKENS_DIR  = _expand_path(os.getenv("TOKENS_DIR", str(BASE_PATH / "tokens"))) or (BASE_PATH / "tokens")
LOGS_DIR    = _expand_path(os.getenv("LOGS_DIR", str(BASE_PATH / "logs"))) or (BASE_PATH / "logs")
DESIGNER_DIR= _expand_path(os.getenv("DESIGNER_DIR"))  # opcional
APP_STAGE   = Stage(os.getenv("APP_STAGE", "dev").lower())
APP_TIMEZONE= os.getenv("APP_TIMEZONE", "America/Sao_Paulo")

# APIs / credenciais
ML_API_BASE = os.getenv("ML_API_BASE", "https://api.mercadolibre.com").rstrip("/")

# Sellers & tokens (por loja/região)
SP_SELLER_ID = os.getenv("SP_SELLER_ID", "").strip()
MG_SELLER_ID = os.getenv("MG_SELLER_ID", "").strip()

_sp_tokens_env = _expand_path(os.getenv("SP_TOKENS_JSON"))
_mg_tokens_env = _expand_path(os.getenv("MG_TOKENS_JSON"))
SP_TOKENS_JSON = _sp_tokens_env or (TOKENS_DIR / "meli" / "sp.json")
MG_TOKENS_JSON = _mg_tokens_env or (TOKENS_DIR / "meli" / "mg.json")

def meli_client_credentials(loja: str) -> Tuple[Optional[str], Optional[str]]:
    if loja.lower() == "sp":
        return os.getenv("SP_CLIENT_ID"), os.getenv("SP_CLIENT_SECRET")
    return os.getenv("MG_CLIENT_ID"), os.getenv("MG_CLIENT_SECRET")

# --------------------------- Domínio: VENDAS (MELI) ----------------------
MELI_VENDAS_DIR = DATA_DIR / "marketplaces" / Marketplace.MELI.value / "vendas"

def loja_dir(loja: str) -> Path:
    return MELI_VENDAS_DIR / loja.lower()

def raw_dir(loja: str) -> Path:
    return ensure_dir(loja_dir(loja) / Camada.RAW.value)

def pp_dir(loja: str) -> Path:
    return ensure_dir(loja_dir(loja) / Camada.PP.value)

def vendas_raw_json(loja: str) -> Path:
    return raw_dir(loja) / "vendas.json"  # nome fixo

def vendas_pp_json(loja: str) -> Path:
    return pp_dir(loja) / "vendas_pp.json"

def vendas_resumo_json(loja: str) -> Path:   # compatível com versão anterior
    return pp_dir(loja) / "resumo_windows.json"

def vendas_por_mlb_json(loja: str) -> Path:  # compatível
    return pp_dir(loja) / "por_mlb.json"

def vendas_resumo_hoje_json(loja: str) -> Path:  # compatível
    return pp_dir(loja) / "resumo_today.json"

@dataclass(frozen=True)
class LojaConfig:
    nome: str
    seller_id: str
    tokens_path: Path

def get_loja_config(loja: str) -> LojaConfig:
    k = loja.lower()
    if k == "sp":
        return LojaConfig("sp", SP_SELLER_ID, Path(SP_TOKENS_JSON))
    if k == "mg":
        return LojaConfig("mg", MG_SELLER_ID, Path(MG_TOKENS_JSON))
    raise ValueError(f"Loja inválida: {loja} (use 'sp' ou 'mg')")

def ensure_dirs():
    for loja in ("sp", "mg"):
        raw_dir(loja)
        pp_dir(loja)
    ensure_dir(TOKENS_DIR / "meli")
    ensure_dir(LOGS_DIR)

# ------------------------- Domínio: ANÚNCIOS (MELI) ----------------------
MELI_ANUNCIOS_DIR = DATA_DIR / "marketplaces" / Marketplace.MELI.value / "anuncios"

def meli_anuncios_raw_dir() -> Path:
    return ensure_dir(MELI_ANUNCIOS_DIR / Camada.RAW.value)

def meli_anuncios_pp_dir() -> Path:
    return ensure_dir(MELI_ANUNCIOS_DIR / Camada.PP.value)

def anuncios_raw_json(market: Marketplace, regiao: Regiao) -> Path:
    if market is not Marketplace.MELI:
        raise NotImplementedError("Anúncios RAW: implementado apenas para MELI neste momento.")
    return meli_anuncios_raw_dir() / f"anuncios_{regiao.value}_raw.json"

def anuncios_pp_json(market: Marketplace, regiao: Regiao) -> Path:
    if market is not Marketplace.MELI:
        raise NotImplementedError("Anúncios PP: implementado apenas para MELI neste momento.")
    return meli_anuncios_pp_dir() / f"anuncios_{regiao.value}_pp.json"

# Atalhos solicitados no módulo novo
ANUNCIOS_MG_RAW_JSON = anuncios_raw_json(Marketplace.MELI, Regiao.MG)
ANUNCIOS_SP_RAW_JSON = anuncios_raw_json(Marketplace.MELI, Regiao.SP)

# ---------------------- Helpers mínimos exigidos -------------------------
def anuncios_json(market: Marketplace, camada: Camada, regiao: Optional[Regiao] = None) -> Path:
    """
    Retorna o JSON de anúncios por marketplace/camada.
    Por padrão, MELI usa {anuncios_<regiao>_<camada>.json}.
    """
    if market is Marketplace.MELI:
        if regiao is None:
            raise ValueError("Para MELI é obrigatório informar a regiao (MG/SP).")
        return (meli_anuncios_raw_dir() if camada is Camada.RAW else meli_anuncios_pp_dir()) / \
               f"anuncios_{regiao.value}_{camada.value}.json"
    raise NotImplementedError("anuncios_json: implementado apenas para MELI neste momento.")

def ads_json(market: Marketplace, janela: str, regiao: Regiao) -> Path:
    """
    Caminho para métricas agregadas de publicidade (ex.: '7d', '15d', '30d') por regiao.
    Por padrão salvo em DATA_DIR/marketplaces/<market>/ads/<janela>/<regiao>.json
    """
    base = DATA_DIR / "marketplaces" / market.value / "ads" / janela.lower()
    ensure_dir(base)
    return base / f"ads_{regiao.value}.json"

def estoque_json(regiao: Regiao) -> Path:
    base = DATA_DIR / "estoque" / regiao.value
    ensure_dir(base)
    return base / "estoque.json"

def nf_json(market: Optional[Marketplace] = None) -> Path:
    """
    Caminho consolidado de notas fiscais. Se market=None, usa consolidado geral.
    """
    base = DATA_DIR / "notas_fiscais"
    ensure_dir(base)
    if market:
        mdir = base / market.value
        ensure_dir(mdir)
        return mdir / "nf.json"
    return base / "nf.json"

# --------------------------- Logs por domínio ----------------------------
def anuncios_log_dir() -> Path:
    return ensure_dir(LOGS_DIR / "meli" / "anuncios")

def vendas_log_dir() -> Path:
    return ensure_dir(LOGS_DIR / "meli" / "vendas")
