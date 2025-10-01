# scripts/custos/variaveis/produtos/enriquecer_transacoes_com_gtin.py
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable

from app.config.paths import Marketplace, Regiao
from app.utils.core.io import atomic_write_json
from app.utils.costs.variable.produtos.config import transacoes_por_produto_json

# Normalização central (se o util não existir, cai no quick-fix local)
try:
    from app.utils.core.identifiers import normalize_gtin  # type: ignore
except Exception:
    _FIX_MAP = {
        "78989153800197908883300183": "7908883300183",
        "78989153808047898915380927": "7898915380804",
    }
    def _only_digits(s: str) -> str:
        return "".join(ch for ch in s if ch.isdigit())
    def normalize_gtin(gtin: Optional[str]) -> Optional[str]:  # type: ignore
        if gtin is None:
            return None
        raw = gtin.strip()
        if not raw:
            return None
        if raw in _FIX_MAP:
            return _FIX_MAP[raw]
        digits = _only_digits(raw)
        if digits in _FIX_MAP:
            return _FIX_MAP[digits]
        return digits or None

# Service de anúncios (opcional)
try:
    from app.utils.anuncios.service import obter_anuncio_por_mlb  # type: ignore
except Exception:
    obter_anuncio_por_mlb = None  # type: ignore


# ----------------- utilidades -----------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S")


def _project_root_from_here() -> Path:
    here = Path(__file__).resolve()
    # .../<repo>/app/utils/... => parents[5] == 'app'
    if len(here.parents) >= 6 and here.parents[5].name == "app":
        return here.parents[6]
    for p in here.parents:
        if p.name == "app":
            return p.parent
    return here.parents[-1]


def _resolve_placeholders(p: str) -> Path:
    if isinstance(p, Path):
        return p
    if "${BASE_PATH}" in p or "{BASE_PATH}" in p:
        root = _project_root_from_here()
        p = p.replace("${BASE_PATH}", str(root)).replace("{BASE_PATH}", str(root))
    return Path(p)


def _safe_load_json_maybe(path: Path, debug: bool = False) -> Any | None:
    """Carrega JSON se existir; caso contrário, retorna None (sem lançar)."""
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    if debug:
        print(f"[WARN] Arquivo não encontrado (opcional): {path}")
    return None


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _pick_from_attributes(attrs: Iterable[Dict[str, Any]]) -> Optional[str]:
    if not attrs:
        return None
    keys_like = {"gtin", "ean", "barcode", "código de barras", "codigo de barras", "código universal", "codigo universal"}
    for a in attrs:
        id_ = str(a.get("id", "")).strip().lower()
        name = str(a.get("name", "")).strip().lower()
        if id_ in keys_like or name in keys_like:
            v = a.get("value_name") or a.get("value") or a.get("value_id")
            if v is not None and str(v).strip():
                return str(v).strip()
    return None


def _pick_gtin(anuncio: Dict[str, Any]) -> Optional[str]:
    for k in ("gtin", "ean", "barcode", "gtin13", "ean_code", "gtin_13"):
        v = anuncio.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    gt = _pick_from_attributes(anuncio.get("attributes") or [])
    if gt:
        return gt
    for var in (anuncio.get("variations") or []):
        gt = _pick_from_attributes(var.get("attributes") or [])
        if gt:
            return gt
    for k in ("body", "data", "detail", "metadata"):
        obj = anuncio.get(k)
        if obj and isinstance(obj, dict) and "attributes" in obj:
            gt = _pick_from_attributes(obj["attributes"])
            if gt:
                return gt
    return None


def _build_mlb_to_gtin_index(anuncios_obj: Any) -> Dict[str, Optional[str]]:
    items: List[Dict[str, Any]] = []
    if isinstance(anuncios_obj, list):
        items = [x for x in anuncios_obj if isinstance(x, dict)]
    elif isinstance(anuncios_obj, dict):
        for key in ("records", "data", "items", "anuncios", "list"):
            v = anuncios_obj.get(key)
            if isinstance(v, list) and (not v or isinstance(v[0], dict)):
                items = v
                break
        if not items:
            for v in anuncios_obj.values():
                if isinstance(v, list) and (not v or isinstance(v[0], dict)):
                    items = v
                    break
                if isinstance(v, dict):
                    inner = v.get("items")
                    if isinstance(inner, list) and (not inner or isinstance(inner[0], dict)):
                        items = inner
                        break

    idx: Dict[str, Optional[str]] = {}
    for it in items:
        mlb = (it.get("mlb") or it.get("numero_anuncio") or it.get("id") or it.get("listing_id"))
        if not mlb:
            continue
        mlb = str(mlb).strip()
        if not mlb:
            continue
        idx[mlb] = _pick_gtin(it)
    return idx


def _load_transacoes(src: Path) -> Dict[str, Any]:
    obj = _load_json(src)
    if isinstance(obj, list):
        return {"meta": {"legacy": True, "records_count": len(obj)}, "records": obj}
    if isinstance(obj, dict) and "records" in obj:
        return obj
    return {"meta": {"unexpected_schema": True}, "records": []}


def _select_source(ano: int, mes: int, regiao: Regiao, override: Optional[str], debug: bool) -> Path:
    if override:
        src = _resolve_placeholders(override)
        if debug:
            print(f"[DBG] lendo transações (override): {src} (exists={src.exists()})")
        return src

    src = _resolve_placeholders(transacoes_por_produto_json(ano, mes, regiao))
    if debug:
        print(f"[DBG] lendo transações (padrão): {src} (exists={src.exists()})")

    if not src.exists():
        parent = src.parent
        if debug:
            print(f"[DBG] buscando candidatos em: {parent}")
        cand = sorted(
            [p for p in parent.glob("*transacoes_por_produto*.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if debug:
            print(f"[DBG] candidatos encontrados: {[str(p) for p in cand[:5]]}")
        if cand:
            if debug:
                print(f"[DBG] usando candidato mais recente: {cand[0]}")
            return cand[0]

    return src


def _emit_atomic(destino: Path, result: dict) -> None:
    atomic_write_json(destino, result, do_backup=True)


# ----------------- CLI -----------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Enriquece transações por produto com GTIN (lookup por MLB no PP de anúncios). "
            "Informe o caminho do PP de anúncios via --anuncios-path."
        )
    )
    p.add_argument("--market", default="meli", choices=[m.value for m in Marketplace])
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--regiao", required=True, choices=[r.value for r in Regiao])
    p.add_argument("--debug", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="Limita a quantidade processada (debug).")
    p.add_argument("--source-transacoes", type=str, default="", help="Caminho explícito do JSON de transações.")
    p.add_argument("--anuncios-path", type=str, required=True,
                   help=r'Ex.: C:\Apps\Datahive\data\marketplaces\meli\anuncios\pp\anuncios_mg_pp.json')
    p.add_argument("--out", type=str, default="", help="Caminho de saída. Se vazio e --overwrite, salva no arquivo de origem.")
    p.add_argument("--overwrite", action="store_true", default=True, help="Sobrescrever o arquivo de origem (default).")
    p.add_argument("--correcoes-gtin", type=str, default="", help="JSON com correções por MLB/GTIN (opcional).")
    return p.parse_args()


# ----------------- principal -----------------

def main() -> None:
    args = parse_args()
    market = Marketplace(args.market)
    regiao = Regiao(args.regiao)

    # 1) Fonte das transações
    src = _select_source(args.ano, args.mes, regiao, args.source_transacoes, args.debug)
    if not src.exists():
        raise FileNotFoundError(f"Arquivo de transações não encontrado: {src}")
    payload = _load_transacoes(src)
    records: List[Dict[str, Any]] = payload.get("records", [])
    if args.limit and args.limit > 0:
        records = records[: args.limit]

    # 2) Índice MLB→GTIN via arquivo de anúncios (opcional, preferível)
    anuncios_path = _resolve_placeholders(args.anuncios_path)
    if args.debug:
        print(f"[DBG] carregando anúncios via arquivo: {anuncios_path} (exists={anuncios_path.exists()})")

    mlb_to_gtin: Dict[str, Optional[str]] = {}
    anuncios_obj = _safe_load_json_maybe(anuncios_path, debug=args.debug)
    if isinstance(anuncios_obj, (list, dict)):
        mlb_to_gtin = _build_mlb_to_gtin_index(anuncios_obj)
    else:
        if args.debug:
            print(f"[WARN] PP de anúncios não encontrado em: {anuncios_path} — seguindo SEM índice de arquivo (apenas service se disponível).")

    # 3) Correções externas (opcional)
    correcoes_by_mlb: Dict[str, str] = {}
    correcoes_by_gtin: Dict[str, str] = {}
    if args.correcoes_gtin:
        corr_path = _resolve_placeholders(args.correcoes_gtin)
        corr_obj = _safe_load_json_maybe(corr_path, debug=args.debug)
        if isinstance(corr_obj, dict):
            correcoes_by_mlb = {str(k).strip(): str(v).strip() for k, v in (corr_obj.get("by_mlb") or {}).items()}
            correcoes_by_gtin = {str(k).strip(): str(v).strip() for k, v in (corr_obj.get("by_gtin") or {}).items()}

    # 4) (opcional) via service para MLBs não resolvidos
    def _lookup_via_service(mlb: str) -> Optional[str]:
        if obter_anuncio_por_mlb is None:
            return None
        try:
            a = obter_anuncio_por_mlb(regiao.value, mlb)  # type: ignore
            return _pick_gtin(a) if a else None
        except Exception:
            return None

    # 5) Enriquecimento
    out: List[Dict[str, Any]] = []
    miss = hit = 0
    cache_service: Dict[str, Optional[str]] = {}

    for i, r in enumerate(records):
        gtin_existing = r.get("gtin")
        mlb_reg = (r.get("numero_anuncio") or r.get("mlb") or "").strip()

        if isinstance(gtin_existing, str) and gtin_existing.strip():
            # Correção por GTIN explícito
            forced = correcoes_by_gtin.get(gtin_existing.strip())
            old = gtin_existing
            gtin_norm = normalize_gtin(forced or gtin_existing)
            if args.debug and old != gtin_norm:
                print(f"[DBG] GTIN(normalizado do registro): '{old}' -> '{gtin_norm}'")
            gtin = gtin_norm
        else:
            gtin = None
            if mlb_reg:
                # Correção por MLB primeiro
                if mlb_reg in correcoes_by_mlb:
                    gtin = correcoes_by_mlb[mlb_reg]
                # Índice de arquivo
                if gtin is None:
                    gtin = mlb_to_gtin.get(mlb_reg)
                # Service (fallback)
                if gtin is None and (mlb_reg not in mlb_to_gtin):
                    if mlb_reg in cache_service:
                        gtin = cache_service[mlb_reg]
                    else:
                        gtin = _lookup_via_service(mlb_reg)
                        cache_service[mlb_reg] = gtin
            # Correção por GTIN (após lookup) e normalização
            if gtin:
                forced = correcoes_by_gtin.get(str(gtin).strip())
                old = gtin
                gtin = normalize_gtin(forced or old)
                if args.debug and old != gtin:
                    print(f"[DBG] GTIN(normalizado via MLB/service): '{old}' -> '{gtin}'")

        if gtin:
            hit += 1
        else:
            miss += 1

        rec = dict(r)
        rec["gtin"] = gtin
        out.append(rec)

        if args.debug and i < 3:
            print(f"[DBG] {i:>3}: MLB={mlb_reg} → GTIN={gtin}")

    # 6) Destino (overwrite por padrão)
    if args.out:
        destino = _resolve_placeholders(args.out)
    elif args.overwrite:
        destino = src
    else:
        destino = _resolve_placeholders(transacoes_por_produto_json(args.ano, args.mes, regiao))

    result = {
        "meta": {
            "generated_at": _now_iso(),
            "market": market.value,
            "ano": args.ano,
            "mes": args.mes,
            "regiao": regiao.value,
            "source": f"{src.name} + anuncios_pp",
            "records_count": len(out),
            "source_file": str(src),
            "mlb_gtin_hits": hit,
            "mlb_gtin_miss": miss,
            "anuncios_path": str(anuncios_path),
            "correcoes_gtin": args.correcoes_gtin or None,
        },
        "records": out,
    }

    # 7) Escrita (atômica + backup)
    atomic_write_json(destino, result, do_backup=True)

    if args.debug:
        print(f"[ECHO] destino: {destino}")
        print(f"[ECHO] hits={hit} miss={miss} total={len(out)}")
        print(json.dumps({"meta": result["meta"], "records": out[:3]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
