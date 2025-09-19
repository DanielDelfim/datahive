from __future__ import annotations
from typing import List, Dict, Any, Optional
from .aggregator import _carregar_pp
from .schemas import PPAnuncio, has_minimal_fields
from . import filters  # usa os filtros puros já criados (by_* / apply_filters)

# ------------------- API de serviço (sem I/O em pages) -------------------

def listar_anuncios(
    regiao: str,
    mlbs: Optional[list[str]] = None,
    title_q: Optional[str] = None,
    sku_q: Optional[str] = None,
    fulfillment_only: bool = False,
    active_only: bool = False,
) -> List[PPAnuncio]:
    """
    Retorna a lista PP filtrada por critérios opcionais.
    """
    data = _carregar_pp(regiao)
    if not any([mlbs, title_q, sku_q, fulfillment_only, active_only]):
        return data
    return filters.apply_filters(
        data,
        mlbs=mlbs,
        title_q=title_q,
        sku_q=sku_q,
        fulfillment_only=fulfillment_only,
        active_only=active_only,
    )

def obter_anuncio_por_mlb(regiao: str, mlb: str) -> Optional[PPAnuncio]:
    """
    Retorna um único anúncio por MLB (ou None se não encontrado).
    """
    if not mlb:
        return None
    q = mlb.strip().casefold()
    for rec in _carregar_pp(regiao):
        rid = str(rec.get("mlb") or "").strip().casefold()
        if rid == q:
            return rec
    return None

def campos_basicos(rec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai apenas os campos mínimos/mais usados para exibição rápida.
    """
    return {
        "mlb": rec.get("mlb"),
        "sku": rec.get("sku"),
        "title": rec.get("title"),
        "estoque": rec.get("estoque"),
        "price": rec.get("price"),
        "original_price": rec.get("original_price"),
        "status": rec.get("status"),
        "logistic_type": rec.get("logistic_type"),
    }

def validar_integridade_pp(regiao: str) -> Dict[str, Any]:
    """
    Valida estrutura básica do PP da região.
    Retorna dicionário com {'ok': bool, 'total': int, 'erros': [...] }.
    """
    erros: List[str] = []
    data = _carregar_pp(regiao)
    if not isinstance(data, list):
        return {"ok": False, "total": 0, "erros": ["Envelope PP inválido ou ausente."]}

    total = len(data)
    for i, rec in enumerate(data):
        if not has_minimal_fields(rec):
            erros.append(f"Registro #{i} sem campos mínimos (mlb/title).")
        # validações adicionais opcionais:
        # - estoque >= 0? price/original_price numéricos? status conhecido? etc.

    return {"ok": len(erros) == 0, "total": total, "erros": erros}
