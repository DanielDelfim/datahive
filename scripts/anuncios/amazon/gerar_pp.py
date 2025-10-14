from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.core.result_sink.json_file_sink import JsonFileSink
from app.config.paths import anuncios_json, Marketplace, Camada, Regiao

from app.utils.anuncios.config import RAW_PATH_AMAZON, PP_PATH_AMAZON

# === Helpers de detecção/extração (paridade com seu gerador PP do ML) ===
def _only_digits(s: Optional[str]) -> bool:
    return bool(s) and s.isdigit()

def _looks_like_gtin(s: Optional[str]) -> bool:
    return _only_digits(s) and (8 <= len(s) <= 14)

def _extract_gtin_from_attributes(attrs: List[Dict[str, Any]]) -> Optional[str]:
    """
    Amazon Catalog Items costuma expor identificadores externos (GTIN/EAN/UPC/ISBN)
    em blocos de 'identifiers'/'externalProductIds' ou atributos normalizados.
    Mantemos heurística semelhante ao ML.
    """
    if not attrs:
        return None
    wanted = {"GTIN", "EAN", "UPC", "JAN", "ISBN", "ISBN13"}
    for a in attrs:
        aid = (a.get("id") or "").upper()
        an = (a.get("name") or "").upper()
        if aid in wanted or any(k in an for k in wanted):
            val = a.get("value_name") or a.get("value_id") or a.get("values", [{}])[0].get("name")
            if isinstance(val, str) and _looks_like_gtin(val):
                return val
    return None

def _extract_gtin(item: Dict[str, Any]) -> Optional[str]:
    # 1) atributos diretos normalizados, se houver
    gt = _extract_gtin_from_attributes(item.get("attributes") or [])
    if gt:
        return gt
    # 2) possíveis estruturas provenientes de Catalog Items (externalProductIds)
    ext = item.get("externalProductIds") or item.get("identifiers")
    if isinstance(ext, dict):
        for v in ext.values():
            if isinstance(v, str) and _looks_like_gtin(v):
                return v
            if isinstance(v, list):
                for e in v:
                    if isinstance(e, str) and _looks_like_gtin(e):
                        return e
                    if isinstance(e, dict):
                        for vv in e.values():
                            if isinstance(vv, str) and _looks_like_gtin(vv):
                                return vv
    return None

def _extract_sku(item: Dict[str, Any]) -> Optional[str]:
    # Amazon: normalmente "sellerSku" ou "sku"
    return item.get("sellerSku") or item.get("sku")

def _fulfillment_channel(item: Dict[str, Any]) -> Optional[str]:
    # "AFN" (FBA) | "MFN" (FBM). Mapeamos para o campo único 'logistic_type'.
    ch = (item.get("fulfillmentChannel") or "").upper()
    if ch in {"AFN", "MFN"}:
        return ch.lower()
    return None

def _price_currency(item: Dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    # Tente pegar preço do listing; se não houver, deixa None.
    price = item.get("price") or item.get("listingPrice")
    cur = item.get("currency") or item.get("currencyCode")
    try:
        price = float(price) if price is not None else None
    except Exception:
        price = None
    if isinstance(cur, str):
        cur = cur.strip() or None
    return price, cur

# === Normalização RAW → PP (espelho do ML) ===
def _normalizar_raw_para_pp(raw_env: Dict[str, Any], regiao: str) -> List[Dict[str, Any]]:
    rows = raw_env.get("data") or raw_env.get("items") or []
    out: List[Dict[str, Any]] = []

    def _first_summary(it: Dict[str, Any]) -> Dict[str, Any]:
        sums = it.get("summaries") or []
        return sums[0] if isinstance(sums, list) and sums else {}

    def _digits_or_none(s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        d = "".join(ch for ch in str(s) if ch.isdigit())
        return d if 8 <= len(d) <= 14 else None

    for it in rows:
        summ = _first_summary(it)
        asin = summ.get("asin")
        title = summ.get("itemName")
        status_list = summ.get("status") or []
        status = status_list[0] if status_list else None
        fnsku = summ.get("fnSku")

        seller_sku = it.get("sellerSku") or it.get("sku")
        # heurística: quando o seller_sku é um EAN/GTIN, aproveitamos
        gtin = _digits_or_none(seller_sku)

        rec = {
            "marketplace": "amazon",
            "regiao": regiao,
            "asin": asin,
            "seller_sku": seller_sku,
            "gtin": gtin,                    # se precisar 100%, enriquecemos depois via Catalog Items
            "title": title,
            "status": status,                # BUYABLE / DISCOVERABLE etc.
            "logistic_type": "afn" if fnsku else None,  # FBA se tem FNSKU
            "price": None,                   # Pricing/Offers numa próxima etapa
            "currency": "BRL",
            "raw": {
                "fnSku": fnsku,
                "productType": summ.get("productType"),
                "conditionType": summ.get("conditionType"),
            },
        }
        out.append(rec)
    return out

def _raw_path(regiao_lower: str) -> Path:
    return anuncios_json(Marketplace.AMAZON, Camada.RAW, Regiao(regiao_lower))

def _pp_path(regiao_lower: str) -> Path:
    return anuncios_json(Marketplace.AMAZON, Camada.PP, Regiao(regiao_lower))

def _parse_args():
    ap = argparse.ArgumentParser(description="Gera PP de anúncios Amazon (SP/MG).")
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

    raw_p = RAW_PATH_AMAZON(reg_lower)
    raw_env = json.loads(raw_p.read_text(encoding="utf-8")) if raw_p.exists() else {"data": []}
    pp_list = _normalizar_raw_para_pp(raw_env, reg_lower)

    payload: Dict[str, Any] = {
        "marketplace": "amazon",
        "regiao": reg_lower,
        "total": len(pp_list),
        "data": pp_list,
        "_source": raw_p.name,
    }

    if args.to_file:
        target = PP_PATH_AMAZON(reg_lower)
        sink = JsonFileSink(
            output_dir=target.parent,
            filename=target.name,
            keep=args.keep,
        )
        sink.emit(payload)

    if args.to_stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
