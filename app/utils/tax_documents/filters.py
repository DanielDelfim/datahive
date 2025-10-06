from __future__ import annotations
from typing import Iterable, Dict, Any, Optional, Set, List

# mapas de CFOP ficam no config (fonte única)
from .config import CFOPS_VENDA, CFOPS_TRANSFER, CFOPS_OUTROS

# substitua o helper _to_cfop e o filtrar_por_cfop por estas versões

_CFOP_KEYS = ("Item CFOP", "CFOP", "cfop_item", "cfop")

def _norm_cfop_value(v: any) -> str:
    """
    Normaliza CFOP para 4 dígitos (string). Aceita int/str, com/sem lixo.
    """
    s = str(v or "").strip()
    # pega apenas dígitos
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits[:4] if len(digits) >= 4 else digits

def _extract_cfop_from_row(r: dict) -> str:
    for k in _CFOP_KEYS:
        if k in r:
            cf = _norm_cfop_value(r.get(k))
            if cf:
                return cf
    return ""

def filtrar_por_cfop(
    rows: Iterable[Dict[str, Any]],
    incluir: Optional[Set[str]] = None,
    excluir: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Filtra por conjunto de CFOP (strings de 4 dígitos). Procura em várias chaves:
    'Item CFOP', 'CFOP', 'cfop_item', 'cfop'.
    """
    inc = { _norm_cfop_value(x) for x in (incluir or set()) if _norm_cfop_value(x) }
    exc = { _norm_cfop_value(x) for x in (excluir or set()) if _norm_cfop_value(x) }

    out: List[Dict[str, Any]] = []
    for r in rows:
        cf = _extract_cfop_from_row(r)
        if inc and cf not in inc:
            continue
        if exc and cf in exc:
            continue
        out.append(r)
    return out

# opcional: tornar filtrar_por_situacao mais tolerante a nomes de campo
_SIT_KEYS = ("Situacao NFe", "Situação NFe", "situacao", "status", "Status")

def filtrar_por_situacao(rows: Iterable[Dict[str, Any]], permitidas: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    if not permitidas:
        return list(rows)
    keep = {str(s).lower() for s in permitidas}
    out: List[Dict[str, Any]] = []
    for r in rows:
        val = ""
        for k in _SIT_KEYS:
            if k in r:
                val = str(r.get(k, "")).lower()
                break
        if val and val in keep:
            out.append(r)
    return out


def filtrar_por_modo(rows: Iterable[Dict[str, Any]], modo: str) -> List[Dict[str, Any]]:
    """
    modos: 'vendas' | 'transferencias' | 'outros' | 'todos'
    """
    m = (modo or "todos").lower()
    if m == "vendas":
        return filtrar_por_cfop(rows, incluir=CFOPS_VENDA)
    if m == "transferencias":
        return filtrar_por_cfop(rows, incluir=CFOPS_TRANSFER)
    if m == "outros":
        return filtrar_por_cfop(rows, incluir=CFOPS_OUTROS)
    return list(rows)

def pos_filtro_por_provedor(rows: Iterable[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
    """
    Regras pós-filtro por provedor. Ex.: Bling só série '1'.
    Mantém função pura (sem I/O).
    """
    prov = (provider or "").lower()
    if prov != "bling":
        return list(rows)
    out: List[Dict[str, Any]] = []
    for r in rows:
        serie = str(r.get("Serie","")).strip()
        if serie in {"1","01"} or serie == "":
            out.append(r)
    return out
