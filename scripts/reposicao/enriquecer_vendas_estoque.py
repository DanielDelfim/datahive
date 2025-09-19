# scripts/reposicao/enriquecer_vendas_estoque.py
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterable

# Paths do módulo de reposição
from app.utils.reposicao.config import RESULTS_DIR  # base: .../data/marketplaces/meli/reposicao/results/
# Serviço de anúncios para obter estoque por MLB
from app.utils.anuncios.service import obter_anuncio_por_mlb


def _parse_list_csv(s: str | None, default: Iterable[str]) -> list[str]:
    if not s:
        return list(default)
    return [x.strip().lower() for x in s.split(",") if x.strip()]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dump_json_atomic(payload: Dict[str, Any], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(dest)


def _backup_file(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = path.with_name(f"{path.stem}_backup-{ts}{path.suffix}")
    bkp.write_bytes(path.read_bytes())
    return bkp


def _get_estoque_do_anuncio(regiao: str, mlb: str) -> Any:
    """
    Busca o registro do anúncio e retorna um valor de estoque.
    Preferência: campo 'estoque'. Fallback: 'available_quantity'.
    """
    try:
        anuncio = obter_anuncio_por_mlb(regiao, mlb)
    except Exception:
        anuncio = None

    if not isinstance(anuncio, dict):
        return None

    if "estoque" in anuncio and anuncio["estoque"] is not None:
        return anuncio["estoque"]
    if "available_quantity" in anuncio and anuncio["available_quantity"] is not None:
        return anuncio["available_quantity"]
    return None


def _enrich(payload: Dict[str, Any], lojas_limit: list[str] | None = None) -> Dict[str, Any]:
    """
    Enriquecimento in-place do payload, adicionando 'estoque' a cada MLB por loja.
    Estrutura esperada:
    payload = {
      "results": {
         "sp": { "MLB123": {...}, "MLB456": {...}, ... },
         "mg": { ... }
      },
      ...
    }
    """
    results = payload.get("results")
    if not isinstance(results, dict):
        return payload

    lojas_to_process = lojas_limit or list(results.keys())

    for loja in lojas_to_process:
        loja_key = loja.lower()
        if loja_key not in results or not isinstance(results[loja_key], dict):
            continue

        for mlb, rec in results[loja_key].items():
            if not isinstance(rec, dict):
                continue
            estoque_val = _get_estoque_do_anuncio(regiao=loja_key, mlb=mlb)
            rec["estoque"] = estoque_val
            results[loja_key][mlb] = rec

    payload["results"] = results
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquece o JSON de vendas (7/15/30) com estoque por MLB a partir do serviço de anúncios (sobrescreve por padrão)."
    )
    parser.add_argument(
        "--infile",
        help="JSON de entrada (default: RESULTS_DIR()/vendas_7_15_30.json)",
        default=None,
    )
    parser.add_argument(
        "--outfile",
        help="JSON de saída alternativo. Se informado, NÃO sobrescreve o infile.",
        default=None,
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Cria um backup (<nome>_backup-YYYYMMDD_HHMMSS.json) antes de sobrescrever.",
    )
    parser.add_argument(
        "--lojas",
        help="Processar apenas lojas específicas (ex.: SP,MG). Default: todas do arquivo.",
        default=None,
    )
    args = parser.parse_args()

    results_dir = RESULTS_DIR()
    infile = Path(args.infile) if args.infile else results_dir / "vendas_7_15_30.json"

    # Se o usuário fornecer --outfile, escrevemos nele (não sobrescreve infile).
    if args.outfile:
        outfile = Path(args.outfile)
        inplace = False
    else:
        outfile = infile  # padrão: salvar no mesmo arquivo
        inplace = True

    lojas_limit = _parse_list_csv(args.lojas, default=()) if args.lojas else None

    payload = _load_json(infile)
    enriched = _enrich(payload, lojas_limit=lojas_limit)

    # Se for sobrescrever e --backup, crie cópia antes
    if inplace and args.backup and infile.exists():
        bkp = _backup_file(infile)
        print(f"[INFO] Backup criado: {bkp}")

    _dump_json_atomic(enriched, outfile)

    print(f"[OK] JSON {'sobrescrito' if inplace else 'gerado'} em: {outfile}")
    if lojas_limit:
        print(f"     Lojas processadas: {', '.join(lojas_limit)}")


if __name__ == "__main__":
    main()
