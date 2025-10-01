from __future__ import annotations
from typing import Dict, Any
from app.config.paths import Regiao, Camada
from app.utils.costs.variable.frete_imposto.service import read_frete_imposto_file
from app.utils.costs.variable.meli.resumo_fatura.service import read_fatura_resumo_pp_file
from app.utils.costs.variable.produtos.service import read_resumo_transacoes_file

def fetch_frete_imposto(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    return read_frete_imposto_file(ano, mes, regiao, camada, debug=debug) or {}

def fetch_fatura_resumo(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    return read_fatura_resumo_pp_file(ano, mes, regiao, camada, debug=debug) or {}

def fetch_resumo_transacoes(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    return read_resumo_transacoes_file(ano, mes, regiao, camada, debug=debug) or {}
