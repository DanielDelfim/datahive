from __future__ import annotations
from pathlib import Path
from app.config.paths import DATA_DIR, Regiao, Camada

def base_dir(ano: int, mes: int, regiao: Regiao, camada: Camada) -> Path:
    return Path(DATA_DIR) / "costs" / "variable" / "produtos" / f"{ano:04d}" / f"{mes:02d}" / regiao.value / camada.value

def resumo_transacoes_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    # Fonte oficial dos totais (pré-calculados)
    return base_dir(ano, mes, regiao, camada) / "resumo_transacoes.json"

def frete_imposto_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    # Opcional: destino padrão para um script salvar o resultado
    return base_dir(ano, mes, regiao, camada) / "frete_imposto.json"
