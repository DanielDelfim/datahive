# app/utils/estoques_matriz_filial/config.py
from __future__ import annotations
from pathlib import Path
import os
from app.config.paths import BASE_PATH, Regiao, atomic_write_json, backup_path

_DEFAULT_SP_XLSX = r"C:\Apps\Datahive\Estoque__filial_SP.xlsx"
_DEFAULT_MG_XLSX = r"C:\Apps\Datahive\Estoque__matriz_MG.xlsx"

def default_excel_sp() -> Path:
    return Path(os.getenv("ESTOQUE_SP_XLSX", _DEFAULT_SP_XLSX)).resolve()

def default_excel_mg() -> Path:
    return Path(os.getenv("ESTOQUE_MG_XLSX", _DEFAULT_MG_XLSX)).resolve()

def estoques_dir() -> Path:
    d = (BASE_PATH / "data" / "estoques").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d

def estoque_json_regiao(regiao: Regiao) -> Path:
    return estoques_dir() / f"estoque_{regiao.value}.json"

# --- NOVO: camada PP ---
def estoques_pp_dir() -> Path:
    d = (estoques_dir() / "pp").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d

def estoque_pp_json_regiao(regiao: Regiao) -> Path:
    return estoques_pp_dir() / f"estoque_{regiao.value}.json"

__all__ = [
    "Regiao",
    "default_excel_sp",
    "default_excel_mg",
    "estoques_dir",
    "estoque_json_regiao",
    "estoques_pp_dir",
    "estoque_pp_json_regiao",
    "atomic_write_json",
    "backup_path",
]
