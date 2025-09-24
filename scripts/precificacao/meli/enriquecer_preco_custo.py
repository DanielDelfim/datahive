#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, Tuple, List, Optional

from app.config.paths import DATA_DIR
from app.utils.core.io import ler_json
from app.utils.core.result_sink.service import resolve_sink_from_flags


def _digits(s: Any) -> str:
    return re.sub(r"\D+", "", str(s or ""))


def _subdigits_windows(s_digits: str, min_len: int = 8, max_len: int = 14) -> List[str]:
    """Gera todas as substrings numéricas (janela deslizante) entre 14 e 8 dígitos, maiores primeiro."""
    out: List[str] = []
    n = len(s_digits)
    for L in range(max_len, min_len - 1, -1):
        if L > n:
            continue
        for i in range(0, n - L + 1):
            out.append(s_digits[i:i+L])
    return out


def _load_produtos_index(produtos_path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Retorna dois índices:
      - idx_by_key: chaves 'originais' (gtin e sku tal como no arquivo)
      - idx_by_digits: chaves reduzidas apenas dígitos
    Fonte de custo: campo 'preco_compra'.
    """
    data = ler_json(produtos_path)
    items = data.get("items", {}) if isinstance(data, dict) else {}
    if not items and isinstance(data, dict):
        items = data

    idx_by_key: Dict[str, Dict[str, Any]] = {}
    idx_by_digits: Dict[str, Dict[str, Any]] = {}

    if isinstance(items, dict):
        for _, prod in items.items():
            if not isinstance(prod, dict):
                continue
            gtin = str(prod.get("gtin") or "").strip()
            sku = str(prod.get("sku") or "").strip()
            for key in {gtin, sku} - {""}:
                idx_by_key[key] = prod
                idx_by_digits[_digits(key)] = prod
    elif isinstance(items, list):
        for prod in items:
            if not isinstance(prod, dict):
                continue
            gtin = str(prod.get("gtin") or "").strip()
            sku = str(prod.get("sku") or "").strip()
            for key in {gtin, sku} - {""}:
                idx_by_key[key] = prod
                idx_by_digits[_digits(key)] = prod

    return idx_by_key, idx_by_digits


def _extract_itens(payload: Any) -> Tuple[list, bool]:
    """Retorna (lista_de_itens, wrap_needed)."""
    if isinstance(payload, list):
        return payload, True
    if isinstance(payload, dict) and isinstance(payload.get("itens"), list):
        return payload["itens"], False
    raise SystemExit("Formato inesperado do PP: esperado dict com 'itens' ou lista de itens.")


def _score_candidate(prod: Dict[str, Any], anuncio: Dict[str, Any]) -> int:
    """Critérios simples de desempate: match com SKU do anúncio e pistas no título."""
    score = 0
    sku_a = _digits(anuncio.get("sku"))
    gtin_p = _digits(prod.get("gtin"))
    sku_p  = _digits(prod.get("sku"))
    if sku_a and (sku_a == gtin_p or sku_a == sku_p):
        score += 2
    title = str(anuncio.get("title") or "").lower()
    hints = ["220", "280", "300", "500", "560", "1 kg", "1kg", "900", "20ml", "30ml"]
    if any(h in title for h in hints):
        score += 1
    return score


def _find_produto_for_ad(
    ad: Dict[str, Any],
    idx_by_key: Dict[str, Dict[str, Any]],
    idx_by_digits: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Estratégia de match em camadas:
      1) GTIN (bruto) → GTIN_digits
      2) Substrings 14→8 dígitos do GTIN_digits
      3) SKU (bruto) → SKU_digits
      4) Desempate por score
    """
    candidates: List[Dict[str, Any]] = []

    g_raw = str(ad.get("gtin") or ad.get("ean") or "").strip()
    if g_raw:
        if g_raw in idx_by_key:
            candidates.append(idx_by_key[g_raw])
        g_digits = _digits(g_raw)
        if g_digits in idx_by_digits:
            candidates.append(idx_by_digits[g_digits])
        for sub in _subdigits_windows(g_digits):
            if sub in idx_by_digits:
                candidates.append(idx_by_digits[sub])

    sku_raw = str(ad.get("sku") or "").strip()
    if sku_raw:
        if sku_raw in idx_by_key:
            candidates.append(idx_by_key[sku_raw])
        sku_digits = _digits(sku_raw)
        if sku_digits in idx_by_digits:
            candidates.append(idx_by_digits[sku_digits])

    if not candidates:
        return None

    uniq: List[Dict[str, Any]] = []
    seen_ids = set()
    for p in candidates:
        pid = id(p)
        if pid not in seen_ids:
            uniq.append(p)
            seen_ids.add(pid)

    if len(uniq) == 1:
        return uniq[0]
    return sorted(uniq, key=lambda p: _score_candidate(p, ad), reverse=True)[0]


def _enriquecer(pp_path: Path, produtos_path: Path) -> Tuple[Dict[str, Any], Dict[str, int], List[Dict[str, Any]]]:
    """
    Enriquecer o PP com 'preco_custo' por GTIN/EAN/SKU.
    Retorna (payload_atualizado SOMENTE com itens que têm preco_custo,
             resumo_dict,
             missing_rows_list com {gtin,title,mlb}).
    """
    payload = ler_json(pp_path)
    itens, wrap_needed = _extract_itens(payload)

    idx_by_key, idx_by_digits = _load_produtos_index(produtos_path)

    total = 0
    casados = 0
    por_motivo = {"gtin": 0, "substring": 0, "sku": 0, "falhou": 0}
    missing_rows: List[Dict[str, Any]] = []
    itens_ok: List[Dict[str, Any]] = []

    for ad in itens:
        if not isinstance(ad, dict):
            continue
        total += 1

        prod = _find_produto_for_ad(ad, idx_by_key, idx_by_digits)
        if not isinstance(prod, dict) or "preco_compra" not in prod or prod["preco_compra"] is None:
            por_motivo["falhou"] += 1
            missing_rows.append({
                "gtin": ad.get("gtin"),
                "title": ad.get("title"),
                "mlb": ad.get("mlb") or ad.get("id"),
            })
            continue

        # classificar motivo do match (debug)
        g_raw = str(ad.get("gtin") or ad.get("ean") or "").strip()
        g_digits = _digits(g_raw)
        if g_raw and (g_raw in idx_by_key or g_digits in idx_by_digits):
            por_motivo["gtin"] += 1
        elif g_digits and any(sub in idx_by_digits for sub in _subdigits_windows(g_digits)):
            por_motivo["substring"] += 1
        else:
            por_motivo["sku"] += 1

        try:
            ad["preco_custo"] = float(prod["preco_compra"])
            casados += 1
            itens_ok.append(ad)  # <<— mantém só os que têm custo
        except (TypeError, ValueError):
            por_motivo["falhou"] += 1
            missing_rows.append({
                "gtin": ad.get("gtin"),
                "title": ad.get("title"),
                "mlb": ad.get("mlb") or ad.get("id"),
            })

    # Reconstrói payload **apenas** com itens OK
    new_payload = {"canal": "meli", "versao": 1, "itens": itens_ok}

    resumo = {
        "total_itens_lidos": total,
        "com_preco_custo": casados,
        "nao_encontrado_no_catalogo": por_motivo["falhou"],
        "match_por_gtin": por_motivo["gtin"],
        "match_por_substring": por_motivo["substring"],
        "match_por_sku": por_motivo["sku"],
        "itens_no_pp_final": len(itens_ok),
    }
    return new_payload, resumo, missing_rows


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Enriquece precificar_meli_pp.json com preco_custo (GTIN/EAN/SKU) e gera lista de não encontrados."
    )
    ap.add_argument(
        "--pp-path",
        type=Path,
        default=DATA_DIR / "precificacao" / "meli" / "pp" / "precificar_meli_pp.json",
    )
    ap.add_argument(
        "--produtos-path",
        type=Path,
        default=DATA_DIR / "produtos" / "pp" / "produtos.json",
    )
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--to-file", action="store_true")
    ap.add_argument("--output-dir", type=Path, default=DATA_DIR / "precificacao" / "meli" / "pp")
    ap.add_argument("--filename", type=str, default="precificar_meli_pp.json")
    ap.add_argument("--missing-filename", type=str, default="precificar_meli_nao_cadastrados.json")
    ap.add_argument("--keep", type=int, default=5)
    ap.add_argument("--name", type=str, default="latest")
    args = ap.parse_args()

    to_file = args.to_file or not args.stdout
    to_stdout = args.stdout

    payload, resumo, missing_rows = _enriquecer(pp_path=args.pp_path, produtos_path=args.produtos_path)

    # Feedback rápido no console
    print(
        "[enriquecer_preco_custo] "
        f"lidos={resumo['total_itens_lidos']} | com_custo={resumo['com_preco_custo']} | "
        f"gtin={resumo['match_por_gtin']} | substring={resumo['match_por_substring']} | "
        f"sku={resumo['match_por_sku']} | nao_encontrado={resumo['nao_encontrado_no_catalogo']} | "
        f"no_pp_final={resumo['itens_no_pp_final']}"
    )

    # 1) Emite PP atualizado (mesmo arquivo)
    sink_pp = resolve_sink_from_flags(
        to_file=to_file,
        to_stdout=to_stdout,
        output_dir=args.output_dir,
        prefix=None,
        keep=args.keep,
        filename=args.filename,
    )
    sink_pp.emit(payload, name=args.name)

    # 2) Emite lista de não encontrados (apenas [{gtin,title,mlb}, ...])
    sink_missing = resolve_sink_from_flags(
        to_file=True,
        to_stdout=False,
        output_dir=args.output_dir,
        prefix=None,
        keep=args.keep,
        filename=getattr(args, "missing_filename", "precificar_meli_nao_cadastrados.json"),
    )
    sink_missing.emit(missing_rows, name=args.name)


if __name__ == "__main__":
    main()
