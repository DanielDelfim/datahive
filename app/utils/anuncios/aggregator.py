# app/utils/anuncios/aggregator.py
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any
from .config import PP_PATH
from .schemas import PPAnuncio, validate_envelope

from app.config.paths import Regiao
from . import config as ancfg  # deve expor RAW_PATH(regiao: str) -> Path

def _norm_regiao(r: Regiao | str | None) -> str:
    if isinstance(r, Regiao):
        return r.value.lower()
    if r is None:
        return ""  # deixa vazio; RAW_PATH deve lidar (ou o caller passa uma válida)
    return str(r).strip().lower()

def _read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def carregar_raw(regiao: Regiao | str | None) -> list[dict]:
    reg = _norm_regiao(regiao)
    path: Path = ancfg.RAW_PATH(reg)  # RAW_PATH("sp"/"mg"/...)
    if not path.exists():
        return []

    payload = _read_json(path)
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "anuncios"):
            arr = payload.get(key)
            if isinstance(arr, list):
                return arr
        if "id" in payload:
            return [payload]
        return []
    if isinstance(payload, list):
        return payload
    return []

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

def _get_rebate_all_methods(item: dict) -> tuple[float | None, str | None]:
    terms = item.get("sale_terms") or []
    for t in terms:
        if t.get("id") == "ALL_METHODS_REBATE_PRICE":
            vs = t.get("value_struct") or {}
            num = vs.get("number")
            cur = vs.get("unit") or "BRL"
            # fallback: se não houver struct, tentar value_name "31.04 BRL"
            if num is None and (vn := t.get("value_name")):
                parts = vn.split()
                try:
                    num = float(parts[0].replace(",", "."))
                    cur = parts[1] if len(parts) > 1 else "BRL"
                except Exception:
                    pass
            return (num, cur)
    return (None, None)

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
