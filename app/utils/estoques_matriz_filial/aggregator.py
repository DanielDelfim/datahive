# app/utils/estoques_matriz_filial/aggregator.py
from __future__ import annotations
from typing import List, Dict, Any

def _pick(a: str, b: str) -> str:
    """Mantém o primeiro não vazio (estável)."""
    a = (a or "").strip()
    b = (b or "").strip()
    return a if a else b

def consolidar_por_ean(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Consolida registros por EAN, somando 'quantidade'.
    - Para ean vazio (""), NÃO agrupa: mantém registros como estão.
    - Para campos 'id', 'codigo', 'descricao': usa o primeiro não vazio encontrado.
    Estrutura de saída preserva chaves: id, codigo, ean, descricao, quantidade.
    """
    if not records:
        return []

    by_ean: Dict[str, Dict[str, Any]] = {}
    leftovers: List[Dict[str, Any]] = []

    for rec in records:
        ean = str(rec.get("ean", "") or "").strip()
        qtd = rec.get("quantidade", 0)
        try:
            qtd = float(qtd)
        except Exception:
            qtd = 0.0

        if ean == "":
            leftovers.append({
                "id": str(rec.get("id", "")).strip(),
                "codigo": str(rec.get("codigo", "")).strip(),
                "ean": "",
                "descricao": str(rec.get("descricao", "")).strip(),
                "quantidade": int(qtd) if qtd.is_integer() else qtd,
            })
            continue

        if ean not in by_ean:
            by_ean[ean] = {
                "id": str(rec.get("id", "")).strip(),
                "codigo": str(rec.get("codigo", "")).strip(),
                "ean": ean,
                "descricao": str(rec.get("descricao", "")).strip(),
                "quantidade": 0.0,
            }

        agg = by_ean[ean]
        agg["id"] = _pick(agg.get("id", ""), str(rec.get("id", "")))
        agg["codigo"] = _pick(agg.get("codigo", ""), str(rec.get("codigo", "")))
        agg["descricao"] = _pick(agg.get("descricao", ""), str(rec.get("descricao", "")))
        soma = (float(agg.get("quantidade", 0.0)) + qtd)
        agg["quantidade"] = soma

    # Ajusta tipos de quantidade (int se inteiro)
    out: List[Dict[str, Any]] = []
    for ean, agg in by_ean.items():
        q = float(agg["quantidade"])
        agg["quantidade"] = int(q) if q.is_integer() else q
        out.append(agg)

    # Preserva estabilidade: consolidados por ean + leftovers (ean vazio) ao final
    return out + leftovers

__all__ = ["consolidar_por_ean"]
