from __future__ import annotations
import json
from typing import List, Dict, Any
from .config import PP_PATH
from .schemas import PPAnuncio, validate_envelope

def _carregar_pp(regiao: str) -> List[PPAnuncio]:
    """
    Carrega o PP da região e retorna a lista enxuta de anúncios.
    Não faz I/O além da leitura do arquivo de PP (consumo).
    """
    path = PP_PATH(regiao.lower())
    if not path.exists():
        return []
    payload: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if not validate_envelope(payload):
        # envelope inválido → retorna lista vazia para evitar quebrar dashboards
        return []
    return payload.get("data", [])  # type: ignore[return-value]

# ------ Placeholders para evoluir RAW→PP sem script (futuro) ------
def _carregar_raw(regiao: str) -> Dict[str, Any]:
    """
    Placeholder: carregar RAW agregado, caso se queira normalizar em memória.
    """
    from .config import RAW_PATH
    p = RAW_PATH(regiao.lower())
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def _normalizar_raw_para_pp(raw_payload: Dict[str, Any]) -> List[PPAnuncio]:
    """
    Placeholder: transformar raw_payload['items'] -> List[PPAnuncio].
    Mantido para futura unificação do pipeline em memória.
    """
    items = raw_payload.get("items") or []
    out: List[PPAnuncio] = []
    for it in items:
        # campos conforme schema mínimo
        rec: PPAnuncio = {
            "mlb": it.get("id"),
            "sku": None,
            "title": it.get("title"),
            "estoque": float(it.get("available_quantity") or 0) if it.get("available_quantity") is not None else None,
            "price": float(it.get("price")) if it.get("price") is not None else None,
            "original_price": float(it.get("original_price")) if it.get("original_price") is not None else None,
            "status": it.get("status"),
            "logistic_type": ((it.get("shipping") or {}).get("logistic_type")),
        }
        # tentativa rápida de SKU em atributos (SELLER_SKU)
        for a in it.get("attributes") or []:
            if not isinstance(a, dict):
                continue
            aid = str(a.get("id") or "").upper()
            aname = str(a.get("name") or "").upper()
            if aid in {"SELLER_SKU", "SKU"} or "SKU" in aname:
                val = a.get("value_name") or a.get("value_id")
                if isinstance(val, str) and val.strip():
                    rec["sku"] = val.strip()
                    break
        out.append(rec)
    return out
