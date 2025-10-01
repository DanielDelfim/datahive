from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Dict, Any, Optional

def extrair_mes_competencia(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"

def por_mes_competencia(notas: Iterable[Dict[str, Any]], mes_competencia: str) -> List[Dict[str, Any]]:
    return [n for n in notas if n.get("mes_competencia") == mes_competencia]

def por_periodo(notas: Iterable[Dict[str, Any]], data_ini: datetime, data_fim: datetime) -> List[Dict[str, Any]]:
    def _ok(n):
        dt = n.get("data_emissao")
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except Exception:
                return False
        return data_ini <= dt <= data_fim
    return [n for n in notas if _ok(n)]

def por_cfop(notas: Iterable[Dict[str, Any]], cfops: List[str]) -> List[Dict[str, Any]]:
    cfops_set = set(cfops)
    return [n for n in notas if cfops_set.intersection(set(n.get("cfops") or []))]

def por_natureza(notas: Iterable[Dict[str, Any]], termos: List[str]) -> List[Dict[str, Any]]:
    terms = [t.lower() for t in termos]
    return [n for n in notas if any(t in (n.get("natureza_operacao") or "").lower() for t in terms)]

def por_emitente(notas: Iterable[Dict[str, Any]], documento: Optional[str] = None, uf: Optional[str] = None) -> List[Dict[str, Any]]:
    def _ok(n):
        e = n.get("emitente") or {}
        if documento and e.get("documento") != documento:
            return False
        if uf and e.get("uf") != uf:
            return False
        return True
    return [n for n in notas if _ok(n)]

def por_tipo_documento(notas: Iterable[Dict[str, Any]], tipo: str) -> List[Dict[str, Any]]:
    return [n for n in notas if n.get("tipo_documento") == tipo]

def por_regiao(notas: Iterable[Dict[str, Any]], regiao: str) -> List[Dict[str, Any]]:
    return [n for n in notas if n.get("regiao") == regiao]
