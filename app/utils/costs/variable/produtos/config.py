# app/utils/costs/variable/produtos/config.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from app.config.paths import DATA_DIR, Regiao, Camada

from app.config.paths import BASE_PATH, ensure_dir  # transversais

Market = Literal["meli", "amazon", "site"]


def _project_root_from_here() -> Path:
    """
    Infere a raiz do projeto subindo a partir deste arquivo:
    .../<repo>/app/utils/costs/variable/produtos/config.py -> .../<repo>
    """
    here = Path(__file__).resolve()
    # estrutura esperada:
    # parents[0]=config.py, [1]=produtos, [2]=variable, [3]=costs, [4]=utils, [5]=app, [6]=<repo>
    if len(here.parents) >= 6 and here.parents[5].name == "app":
        return here.parents[6]
    # fallback: sobe até encontrar "app" e pega o pai
    for p in here.parents:
        if p.name == "app":
            return p.parent
    return here.parents[-1]

def resumo_transacoes_json_path(ano:int, mes:int, regiao:Regiao, camada:Camada=Camada.PP) -> Path:
    # data/costs/variable/produtos/2025/08/mg/pp/resumo_transacoes.json
    return Path(DATA_DIR) / "costs" / "variable" / "produtos" / f"{ano:04d}" / f"{mes:02d}" / regiao.value / camada.value / "resumo_transacoes.json"

def _data_root() -> Path:
    """
    1) DATA_DIR se definido;
    2) se BASE_PATH inválido/placeholder, usa <repo>/data;
    3) senão, BASE_PATH/data.
    """
    data_dir = os.getenv("DATA_DIR")
    if data_dir:
        # Se DATA_DIR vier com ${BASE_PATH}, resolvemos para a raiz do repo
        s = str(data_dir)
        if "${BASE_PATH}" in s or "{BASE_PATH}" in s:
            root = _project_root_from_here()
            s = s.replace("${BASE_PATH}", str(root)).replace("{BASE_PATH}", str(root))
        return Path(s)

    base_env = os.getenv("BASE_PATH")
    base = Path(base_env) if base_env else (Path(BASE_PATH) if BASE_PATH else None)
    if (not base) or ("${BASE_PATH" in str(base)) or ("{BASE_PATH" in str(base)):
        return _project_root_from_here() / "data"
    return base / "data"


def base_dir(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    """
    data/costs/variable/produtos/{ano}/{mes}/{regiao}/{camada}/
    """
    p = (
        _data_root()
        / "costs"
        / "variable"
        / "produtos"
        / f"{ano:04d}"
        / f"{mes:02d}"
        / regiao.value
        / camada.value
    )
    ensure_dir(p)
    return p


# --- Helpers deste domínio (retornam str) ---

def transacoes_por_produto_json(
    ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP
) -> str:
    return str(base_dir(ano, mes, regiao, camada) / "results_transacoes_por_produto.json")


def transacoes_enriquecidas_json(
    ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP
) -> str:
    return str(base_dir(ano, mes, regiao, camada) / "results_transacoes_por_produto_enriquecido.json")

def resumo_transacoes_json(
    ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP
) -> str:
    """Arquivo de saída com 3 totais: quantidade_total, valor_transacao_total, custo_total."""
    return str(base_dir(ano, mes, regiao, camada) / "resumo_transacoes.json")

def agregado_mlb_gtin_json(
    ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP
) -> str:
    """Arquivo de saída com agregação por (mlb, gtin)."""
    return str(base_dir(ano, mes, regiao, camada) / "agregado_mlb_gtin.json")

def gtins_sem_custo_json(
    ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP
) -> str:
    return str(base_dir(ano, mes, regiao, camada) / "gtins_sem_custo.json")


# (Exemplo) outro helper de domínio
def faturamento_pp_json(market: Market, ano: int, mes: int, regiao: Regiao) -> str:
    p = _data_root() / "costs" / "variable" / market / f"{ano:04d}" / f"{mes:02d}" / regiao.value / "pp"
    ensure_dir(p)
    return str(p / f"faturamento_{market}_pp.json")

def transacoes_base_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> str:
    """
    Fonte 'primeira operação' (antes do enriquecimento):
    results_transacoes_por_produto.json
    """
    return str(base_dir(ano, mes, regiao, camada) / "results_transacoes_por_produto.json")

def transacoes_base_dedup_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> str:
    """Saída com uma única linha por numero_venda."""
    return str(base_dir(ano, mes, regiao, camada) / "results_transacoes_por_produto_dedup.json")

def resumo_base_json(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> str:
    """Resumo (quantidade_total, valor_transacao_total, custo_total) da base deduplicada."""
    return str(base_dir(ano, mes, regiao, camada) / "resumo_transacoes_base.json")