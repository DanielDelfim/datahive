from __future__ import annotations

from collections import defaultdict
from typing import Dict, Any, Iterable, List

def _soma_totais(acum: Dict[str, float], n: Dict[str, Any]) -> None:
    t = n.get("totais") or {}
    campos = [
        "valor_produtos", "descontos", "frete", "outras_despesas",
        "base_icms", "icms", "ipi", "pis", "cofins", "valor_total_nfe",
    ]
    for c in campos:
        acum[c] += float(t.get(c) or 0.0)

def totalizadores(notas: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    notas = list(notas)
    out = defaultdict(float)
    for n in notas:
        _soma_totais(out, n)
    out["qtd_notas"] = len(notas)
    return dict(out)

def agrupar_por_chave(notas: Iterable[Dict[str, Any]], chave: str) -> Dict[str, Dict[str, Any]]:
    grupos: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for n in notas:
        k = n.get(chave)
        if k is None:
            continue
        grupos[str(k)].append(n)
    return {k: totalizadores(v) for k, v in grupos.items()}

def agrupar_por_regiao(notas: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return agrupar_por_chave(notas, "regiao")

def agrupar_por_mes(notas: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return agrupar_por_chave(notas, "mes_competencia")

def agrupar_por_cfop(notas: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    # cada nota pode ter múltiplos CFOPs → expandir
    grupos: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for n in notas:
        for cfop in n.get("cfops") or []:
            grupos[str(cfop)].append(n)
    return {k: totalizadores(v) for k, v in grupos.items()}

def agrupar_por_natureza(notas: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return agrupar_por_chave(notas, "natureza_operacao")
