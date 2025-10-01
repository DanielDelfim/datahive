from __future__ import annotations
from pathlib import Path
from typing import Literal
from app.config.paths import DATA_DIR  # fonte única transversal

Regiao = Literal["sp", "mg"]
Market = Literal["meli"]

def _mm(mes: int) -> str: return f"{mes:02d}"

# === diretórios de resultados/entradas (já existentes) ===
def billing_results_dir(market: Market, ano: int, mes: int, regiao: Regiao | Literal["all"]) -> Path:
    return Path(DATA_DIR) / "fiscal" / market / "results" / "billing" / str(ano) / _mm(mes) / regiao

def billing_zip_raw_dir(market: Market, ano: int, mes: int, regiao: Regiao) -> Path:
    return Path(DATA_DIR) / "fiscal" / market / "xml" / "raw" / str(ano) / _mm(mes) / regiao

def excel_dir(market: Market, ano: int, mes: int, regiao: Regiao) -> Path:
    return billing_results_dir(market, ano, mes, regiao) / "excel"

# === artefatos (exemplos) ===
def fatura_totais_json(market: Market, ano: int, mes: int, regiao: Regiao | Literal["all"]) -> Path:
    return billing_results_dir(market, ano, mes, regiao) / "fatura_totais.json"

def reconciliacao_json(market: Market, ano: int, mes: int, regiao: Regiao | Literal["all"]) -> Path:
    return billing_results_dir(market, ano, mes, regiao) / "reconciliacao.json"

def detalhes_por_fonte_json(market: Market, ano: int, mes: int, regiao: Regiao | Literal["all"]) -> Path:
    return billing_results_dir(market, ano, mes, regiao) / "detalhes_por_fonte.json"

# === mapeadores e schemas (novos) ===
def billing_pkg_root() -> Path:
    # raiz do pacote de domínio (este arquivo reside em app/utils/billing/config.py)
    return Path(__file__).resolve().parent

def mappers_dir() -> Path:
    return billing_pkg_root() / "mappers"

def cfop_map_yaml() -> Path:
    return mappers_dir() / "cfop_map.yaml"

def excel_concepts_map_yaml() -> Path:
    return mappers_dir() / "excel_concepts_map.yaml"

def emitentes_yaml() -> Path:
    return mappers_dir() / "emitentes.yml"

def schemas_md() -> Path:
    return billing_pkg_root() / "schemas.md"
