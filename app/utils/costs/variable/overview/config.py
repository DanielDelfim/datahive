from __future__ import annotations
from pathlib import Path
from app.config.paths import DATA_DIR, Regiao, Camada

def base_dir(ano: int, mes: int, regiao: Regiao, camada: Camada) -> Path:
    # Pasta de saída do consolidado
    return Path(DATA_DIR) / "costs" / "variable" / "overview" / f"{ano:04d}" / f"{mes:02d}" / regiao.value / camada.value

def overview_all_dir(ano: int, mes: int) -> Path:
    # Pasta "all" para consolidados MG+SP (sem camada/região)
    return Path(DATA_DIR) / "costs" / "variable" / "overview" / f"{ano:04d}" / f"{mes:02d}" / "all"


def overview_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    return base_dir(ano, mes, regiao, camada) / "overview.json"

def resumo_meli_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    return base_dir(ano, mes, regiao, camada) / "resumo_meli.json"

def meli_totais_json(ano:int, mes:int, regiao:Regiao, camada:Camada=Camada.PP)->Path:
    return base_dir(ano, mes, regiao, camada) / "meli_totais.json"

def frete_imposto_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    # data/costs/variable/frete_imposto/2025/08/mg/pp/frete_imposto.json
    return Path(DATA_DIR) / "costs" / "variable" / "frete_imposto" / f"{ano:04d}" / f"{mes:02d}" / regiao.value / camada.value / "frete_imposto.json"

def resultado_empresa_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    # data/costs/variable/overview/2025/08/mg/pp/resultado_empresa.json
    return base_dir(ano, mes, regiao, camada) / "resultado_empresa.json"