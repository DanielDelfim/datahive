from __future__ import annotations
from typing import Dict, Any
from app.config.paths import Regiao, Camada
from .aggregator import load_resumo
from .rules import get_rates
from .metrics import build_result
from .config import frete_imposto_json
import json
from pathlib import Path

def calcular_frete_imposto(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    """
    Carrega o resumo_transacoes.json e calcula imposto/frete conforme regras.
    (Somente leitura/cálculo; sem escrita em disco.)
    """
    resumo = load_resumo(ano, mes, regiao, camada, debug=debug)
    if debug:
        print(f"[DBG] resumo -> {resumo}")
    rates = get_rates()
    if debug:
        print(f"[DBG] rates  -> {rates}")
    result = build_result(resumo, rates)
    if debug:
        print(f"[DBG] result -> {result}")
    return result


def read_frete_imposto_file(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    """
    Lê o resultado já calculado em frete_imposto.json (somente leitura).
    """
    src = frete_imposto_json(ano, mes, regiao, camada)
    if debug:
        print(f"[DBG] frete_imposto.json → {src}")
    p = Path(src)
    if not p.exists():
        if debug:
            print("[WARN] frete_imposto.json não encontrado")
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
