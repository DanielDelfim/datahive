# scripts/anuncios/meli/gerar_pp.py
from __future__ import annotations
import argparse
import json
import re
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List, Tuple

from app.config.paths import DATA_DIR, backup_path  # fonte única de paths
from app.utils.core.result_sink.service import resolve_sink_from_flags  # fábrica de sinks

# ---------------- utils locais: io atômico + rotação ---------------- #
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def atomic_write_json(target: Path, obj: Any, do_backup: bool = True) -> None:
    target = Path(target)
    ensure_dir(target.parent)
    if do_backup and target.exists():
        bkp = backup_path(target)
        ensure_dir(bkp.parent)
        with target.open("rb") as src, bkp.open("wb") as dst:
            dst.write(src.read())
    tmp = Path(tempfile.gettempdir()) / f".{target.name}.tmp"
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(target)

def list_backups_sorted_newest_first(target: Path) -> List[Path]:
    bdir = target.parent / "backups"
    if not bdir.exists():
        return []
    prefix = f"{target.stem}_"
    return sorted(
        [p for p in bdir.glob(f"{prefix}*{target.suffix}") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

def rotate_backups(target: Path, keep_last_n: int = 2) -> None:
    try:
        backups = list_backups_sorted_newest_first(target)
        for p in backups[keep_last_n:]:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

# ---------------- paths RAW/PP (derivados de DATA_DIR) ---------------- #
def anuncios_raw_path(regiao: str) -> Path:
    base = DATA_DIR / "marketplaces" / "meli" / "anuncios" / "raw"
    ensure_dir(base)
    return base / f"anuncios_{regiao.lower()}_raw.json"

def anuncios_pp_path(regiao: str) -> Path:
    base = DATA_DIR / "marketplaces" / "meli" / "anuncios" / "pp"
    ensure_dir(base)
    return base / f"anuncios_{regiao.lower()}_pp.json"

# --------------------- extractors --------------------- #
def _extract_sku(item: Dict[str, Any]) -> Optional[str]:
    """
    Regra:
    1) Priorizar atributo SELLER_SKU -> value_name (ou name dentro de values)
    2) Fallback: campos livres conhecidos do item
    """
    attrs = item.get("attributes") or []
    if isinstance(attrs, list):
        for a in attrs:
            if not isinstance(a, dict):
                continue
            aid = str(a.get("id") or "").upper()
            aname = str(a.get("name") or "").upper()
            if aid == "SELLER_SKU" or "SKU" in aname:
                val = a.get("value_name")
                if not val:
                    vals = a.get("values") or []
                    if isinstance(vals, list) and vals:
                        val = vals[0].get("name")
                if isinstance(val, str) and val.strip():
                    return val.strip()
    for k in ("seller_custom_field", "seller_sku", "catalog_product_id", "sku"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def _only_digits(s: Optional[str]) -> Optional[str]:
    if not isinstance(s, str):
        return None
    d = re.sub(r"\D+", "", s)
    return d or None

def _extract_gtin(item: Dict[str, Any]) -> Optional[str]:
    """
    Procura atributo GTIN e retorna value_name (normalizado em dígitos).
    Aceita variações de name: 'GTIN' ou 'Código universal de produto'.
    """
    attrs = item.get("attributes") or []
    if not isinstance(attrs, list):
        return None
    for a in attrs:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or "").upper()
        aname = str(a.get("name") or "").strip().upper()
        if aid == "GTIN" or "GTIN" in aname or "CÓDIGO UNIVERSAL DE PRODUTO" in aname:
            val = a.get("value_name")
            if not val:
                vals = a.get("values") or []
                if isinstance(vals, list) and vals:
                    val = vals[0].get("name")
            val = _only_digits(val) if isinstance(val, str) else None
            if val:
                return val
    return None

def _extract_title(item: Dict[str, Any]) -> Optional[str]:
    t = item.get("title")
    return t.strip() if isinstance(t, str) else None

def _extract_available_qty(item: Dict[str, Any]) -> Optional[float]:
    vars_ = item.get("variations") or []
    if isinstance(vars_, list) and len(vars_) > 0:
        total = 0.0
        for var in vars_:
            try:
                total += float(var.get("available_quantity", 0) or 0)
            except Exception:
                pass
        return total
    aq = item.get("available_quantity")
    try:
        return float(aq) if aq is not None else None
    except Exception:
        return None

def _to_float(x) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

def _extract_price_fields(item: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    price = _to_float(item.get("price")) or _to_float(item.get("base_price"))
    original_price = _to_float(item.get("original_price"))
    return price, original_price

def _extract_status(item: Dict[str, Any]) -> Optional[str]:
    st = item.get("status")
    return st.strip() if isinstance(st, str) else None

def _extract_logistic_type(item: Dict[str, Any]) -> Optional[str]:
    ship = item.get("shipping") or {}
    lt = ship.get("logistic_type")
    return lt.strip() if isinstance(lt, str) else None

# --------------------- preprocess lista --------------------- #
def preprocess_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in items:
        mlb = it.get("id")
        price, original_price = _extract_price_fields(it)
        out.append({
            "mlb": mlb,
            "sku": _extract_sku(it),
            "gtin": _extract_gtin(it),
            "title": _extract_title(it),
            "estoque": _extract_available_qty(it),
            "price": price,
            "original_price": original_price,
            "status": _extract_status(it),
            "logistic_type": _extract_logistic_type(it),
        })
    return out

# ------------------------------ main ------------------------------ #
def main():
    ap = argparse.ArgumentParser(description="Gera PP de anúncios (MELI) a partir do RAW agregado.")
    ap.add_argument("--regiao", required=True, choices=["MG", "SP"], help="Região (MG ou SP)")
    # flags para emitir relatório via result_sink
    ap.add_argument("--to-file", dest="to_file", action="store_true")
    ap.add_argument("--no-to-file", dest="to_file", action="store_false")
    ap.set_defaults(to_file=True)
    ap.add_argument("--stdout", dest="to_stdout", action="store_true")
    ap.add_argument("--no-stdout", dest="to_stdout", action="store_false")
    ap.set_defaults(to_stdout=True)
    ap.add_argument("--outfile", help="Nome exato de saída do relatório (opcional)")
    ap.add_argument("--prefix", default="anuncios_pp", help="Prefixo do relatório (JsonFileSink)")
    ap.add_argument("--keep", type=int, default=2, help="Qtde de backups do relatório (JsonFileSink)")
    args = ap.parse_args()

    regiao = args.regiao.upper()
    src = anuncios_raw_path(regiao)
    dst = anuncios_pp_path(regiao)

    if not src.exists():
        raise FileNotFoundError(f"RAW não encontrado: {src}")

    raw_payload = json.loads(src.read_text(encoding="utf-8"))

    # RAW agregado deve conter 'items'
    items = raw_payload.get("items")
    if not isinstance(items, list):
        # fallback: RAW unitário antigo (compatibilidade)
        one = raw_payload.get("item")
        if isinstance(one, dict):
            items = [one]
        else:
            items = []

    pp_list = preprocess_items(items)

    output = {
        "_generated_at": datetime.now().isoformat(),
        "_source": str(src),
        "regiao": regiao.lower(),
        "marketplace": "meli",
        "total": len(pp_list),
        "data": pp_list,  # lista enxuta pronta para dashboards/tabelas
    }

    atomic_write_json(dst, output, do_backup=True)
    rotate_backups(dst, keep_last_n=2)

    # Relatório via result_sink (stdout/json configurável) — não substitui o PP oficial
    sink = resolve_sink_from_flags(
        to_file=args.to_file,
        to_stdout=args.to_stdout,
        output_dir=dst.parent,  # grava relatório no mesmo diretório do PP
        prefix=args.prefix,
        keep=args.keep,
        filename=args.outfile,
    )
    sink.emit({"path": str(dst), "total": len(pp_list), "regiao": regiao.lower()}, name=f"pp_{regiao.lower()}")

    print(f"OK: PP gerado ({len(pp_list)} anúncios) em {dst}")

if __name__ == "__main__":
    main()
