# app/utils/estoques_matriz_filial/service.py
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config.paths import Regiao
from app.utils.estoques_matriz_filial.config import estoque_pp_json_regiao

def _read_json(path: Path) -> List[Dict[str, Any]]:
    """Leitura simples de JSON (lista de registros)."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Garante formato lista
    return data if isinstance(data, list) else []

def _cache_key_for_path(path: Path) -> str:
    """Gera uma chave de cache baseada no caminho + mtime para invalidar automaticamente."""
    try:
        stat = path.stat()
        return f"{str(path)}::{int(stat.st_mtime)}::{stat.st_size}"
    except FileNotFoundError:
        return f"{str(path)}::missing"

@lru_cache(maxsize=16)
def _cached_read(key: str, path_str: str) -> List[Dict[str, Any]]:
    """Wrapper para permitir cache por chave derivada de mtime/tamanho."""
    return _read_json(Path(path_str))

def get_estoque_pp(regiao: Regiao) -> List[Dict[str, Any]]:
    """
    Retorna o estoque PP (lista de dicts) para a região informada.
    Usa cache leve invalidado por mtime/tamanho do arquivo.
    """
    path = estoque_pp_json_regiao(regiao)
    key = _cache_key_for_path(path)
    return _cached_read(key, str(path))

def get_estoque_pp_sp() -> List[Dict[str, Any]]:
    """Atalho para estoque PP da FILIAL SP."""
    return get_estoque_pp(Regiao.SP)

def get_estoque_pp_mg() -> List[Dict[str, Any]]:
    """Atalho para estoque PP da MATRIZ MG."""
    return get_estoque_pp(Regiao.MG)

# ---------- Utilitários de consulta (somente leitura) ----------

def buscar_por_ean(ean: str, regiao: Regiao) -> List[Dict[str, Any]]:
    """Filtra registros pelo EAN (igualdade exata). EAN deve estar 'limpo' no PP."""
    alvo = (ean or "").strip()
    if not alvo:
        return []
    data = get_estoque_pp(regiao)
    return [r for r in data if str(r.get("ean", "")).strip() == alvo]

def buscar_por_codigo(codigo: str, regiao: Regiao) -> List[Dict[str, Any]]:
    """Filtra registros por 'codigo' (igualdade exata, string)."""
    alvo = (codigo or "").strip()
    if not alvo:
        return []
    data = get_estoque_pp(regiao)
    return [r for r in data if str(r.get("codigo", "")).strip() == alvo]

def total_por_ean(ean: str, regiao: Regiao) -> Optional[float]:
    """Soma a quantidade de todos os registros com EAN informado (sem consolidar/reescrever)."""
    itens = buscar_por_ean(ean, regiao)
    if not itens:
        return None
    total = 0.0
    for r in itens:
        try:
            total += float(r.get("quantidade", 0) or 0)
        except Exception:
            pass
    # retorna int se for inteiro
    return int(total) if float(total).is_integer() else total

__all__ = [
    "get_estoque_pp",
    "get_estoque_pp_sp",
    "get_estoque_pp_mg",
    "buscar_por_ean",
    "buscar_por_codigo",
    "total_por_ean",
]
