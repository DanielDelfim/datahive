from __future__ import annotations
import json
from typing import Dict, Any
from app.config.paths import Regiao, Camada
from .config import resumo_transacoes_json

def load_resumo(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP, *, debug: bool = False) -> Dict[str, Any]:
    src = resumo_transacoes_json(ano, mes, regiao, camada)
    if debug:
        print(f"[DBG] resumo_transacoes → {src}")
    with src.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    # normaliza chaves esperadas
    qt = obj.get("quantidade_total", 0) or 0
    vt = obj.get("valor_transacao_total", 0.0) or 0.0
    ct = obj.get("custo_total", 0.0) or 0.0
    return {"quantidade_total": int(qt), "valor_transacao_total": float(vt), "custo_total": float(ct)}
