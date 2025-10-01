# scripts/anuncios/meli/gerar_pp.py
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from app.utils.core.result_sink.json_file_sink import JsonFileSink
from app.utils.anuncios.config import PP_PATH, RAW_PATH
 

from typing import  Optional

def _only_digits(s: Optional[str]) -> bool:
    return bool(s) and s.isdigit()

def _looks_like_gtin(s: Optional[str]) -> bool:
    # EAN/UPC/ISBN etc.: 8–14 dígitos cobre EAN-8, UPC-A/EAN-12/13, etc.
    return _only_digits(s) and (8 <= len(s) <= 14)

def _pick_attr_value(attrs: List[Dict[str, Any]]) -> Optional[str]:
    """Procura GTIN/EAN/UPC/ISBN em attributes[]."""
    if not attrs:
        return None
    wanted_ids = {"GTIN", "EAN", "UPC", "JAN", "ISBN", "ISBN13"}
    for a in attrs:
        aid = (a.get("id") or "").upper()
        aname = (a.get("name") or "").upper()
        if aid in wanted_ids or any(k in aname for k in ("GTIN", "EAN", "UPC", "ISBN")):
            # value_name normalmente já está limpo
            val = a.get("value_name") or a.get("value_id") or a.get("values", [{}])[0].get("name")
            if isinstance(val, str) and _looks_like_gtin(val):
                return val
    return None

def _extract_gtin(item: Dict[str, Any]) -> Optional[str]:
    # 1) attributes no item
    gt = _pick_attr_value(item.get("attributes") or [])
    if gt:
        return gt
    # 2) attributes nas variações
    for v in (item.get("variations") or []):
        gt = _pick_attr_value(v.get("attributes") or [])
        if gt:
            return gt
    # 3) fallback: SKU do vendedor “parecido” com GTIN
    cand = item.get("seller_custom_field") or item.get("seller_sku")
    if _looks_like_gtin(cand):
        return cand
    return None

def _extract_sku(item: Dict[str, Any]) -> Optional[str]:
    # prioridade: seller_custom_field > seller_sku > variações
    sku = item.get("seller_custom_field") or item.get("seller_sku")
    if sku:
        return sku
    for v in (item.get("variations") or []):
        cand = v.get("seller_custom_field") or v.get("seller_sku")
        if cand:
            return cand
    return None

def _normalizar_raw_para_pp(raw_env: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Transforma RAW (data/items) em lista PP com campos mínimos,
    extraindo GTIN/sku/logistic_type e preço promocional de sale_terms.
    """

    # ... (helpers _only_digits, _looks_like_gtin, _pick_attr, _extract_sku, _extract_gtin permanecem iguais)

    def _sale_terms_number(item: Dict[str, Any], term_id: str) -> tuple[Optional[float], Optional[str]]:
        """Retorna (number, unit) de sale_terms[id==term_id], quando existir."""
        for st in item.get("sale_terms") or []:
            if not isinstance(st, dict):
                continue
            if str(st.get("id") or "").upper() == term_id.upper():
                vs = st.get("value_struct") or {}
                num = vs.get("number")
                unit = vs.get("unit")
                try:
                    num = float(num) if num is not None else None
                except Exception:
                    num = None
                return num, unit if isinstance(unit, str) and unit.strip() else None
        return None, None

    out: List[Dict[str, Any]] = []
    rows = raw_env.get("data") or raw_env.get("items") or []
    for it in rows:
        shipping = it.get("shipping") or {}
        logistic_type = shipping.get("logistic_type")
        tags = it.get("tags") or []
        if not logistic_type and isinstance(tags, list) and "fulfillment" in tags:
            logistic_type = "fulfillment"

        # Novo: preço com desconto para todos os meios (sale_terms)
        rebate_num, rebate_unit = _sale_terms_number(it, "ALL_METHODS_REBATE_PRICE")

        rec = {
            "mlb": it.get("id"),
            "title": it.get("title"),
            "sku": _extract_sku(it),
            "gtin": _extract_gtin(it),
            "price": it.get("price"),
            "original_price": it.get("original_price"),
            "status": it.get("status"),
            "logistic_type": logistic_type,
            # novos campos
            "rebate_price_all_methods": rebate_num,   # ex.: 34.44
            "rebate_currency": rebate_unit,          # ex.: "BRL"
        }
        out.append(rec)
    return out

def _parse_args():
    ap = argparse.ArgumentParser(description="Gera PP de anúncios do Meli (SP/MG).")
    # Aceita SP/MG em qualquer caixa
    ap.add_argument("--regiao", required=True, choices=["sp", "mg"], type=lambda s: s.lower())
    ap.add_argument("--to-file", dest="to_file", action="store_true", default=True)
    ap.add_argument("--no-to-file", dest="to_file", action="store_false")
    ap.add_argument("--stdout", dest="to_stdout", action="store_true", default=True)
    ap.add_argument("--no-stdout", dest="to_stdout", action="store_false")
    ap.add_argument("--keep", type=int, default=5)
    ap.add_argument("--debug", action="store_true")
    return ap.parse_args()

def main() -> int:
    args = _parse_args()
    reg_lower = args.regiao
    reg_lower.upper()

    raw_p: Path = RAW_PATH(reg_lower)
    raw = json.loads(raw_p.read_text(encoding="utf-8")) if raw_p.exists() else {"data": []}
    pp_list = _normalizar_raw_para_pp(raw)

    payload: Dict[str, Any] = {
        "marketplace": "meli",
        "regiao": reg_lower,
        "total": len(pp_list),
        "data": pp_list,
        "_source": raw_p.name,
    }
    # (Opcional) validar schema
    # assert validate_envelope(payload), "Envelope PP inválido"
    if args.to_file:
        target: Path = PP_PATH(reg_lower)
        # IMPORTANT: passar diretório e nome de arquivo separadamente, e como Path/str corretos
        sink = JsonFileSink(
            output_dir=target.parent,     # Path, não string do arquivo
            filename=target.name,
            keep=args.keep,
        )
        sink.emit(payload)

    if args.to_stdout:
         print(json.dumps(payload, ensure_ascii=False, indent=2))
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
