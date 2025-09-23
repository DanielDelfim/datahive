# C:\Apps\Datahive\scripts\reposicao\enriquecer_vendas_estoque.py
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from app.utils.core.result_sink.service import make_sink
from typing import Dict, Any, Iterable, Optional

# Paths do módulo de reposição (base: .../data/marketplaces/meli/reposicao/results/)
from app.utils.reposicao.config import RESULTS_DIR
# Serviço de anúncios para obter dados por MLB
from app.utils.anuncios.service import obter_anuncio_por_mlb


# -------------------------
# Utilidades de I/O seguro
# -------------------------
def _parse_list_csv(s: str | None, default: Iterable[str]) -> list[str]:
    if not s:
        return list(default)
    return [x.strip().lower() for x in s.split(",") if x.strip()]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# escrita delegada ao ResultSink

def _rotate_backups(backup_dir: Path, prefix: str, suffix: str, path: Path, keep: int = 2) -> None:
    """
    Mantém apenas os 'keep' arquivos mais recentes no diretório de backup.
    Ordenação por mtime (mais novo primeiro).
    """
    backups = sorted(
        [p for p in backup_dir.glob(f"{prefix}*{suffix}") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        try:
            old.unlink()
        except FileNotFoundError:
            pass

# backup/rotação cuidada pelo sink (atomic_write_json + keep)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = backup_dir / f"{prefix}{ts}{path.suffix}"
    bkp.write_bytes(path.read_bytes())
    _rotate_backups(backup_dir, prefix=prefix, suffix=path.suffix, path=path, keep=keep)
    return bkp


# -------------------------
# Enriquecimento: ESTOQUE + GTIN
# -------------------------
def _get_anuncio(regiao: str, mlb: str) -> Optional[Dict[str, Any]]:
    """Obtém o dicionário do anúncio (ou None em erro/ausência)."""
    try:
        data = obter_anuncio_por_mlb(regiao, mlb)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _get_estoque(anuncio: Optional[Dict[str, Any]]) -> Any:
    """Preferência: 'estoque'; fallback: 'available_quantity'."""
    if not isinstance(anuncio, dict):
        return None
    if anuncio.get("estoque") is not None:
        return anuncio.get("estoque")
    if anuncio.get("available_quantity") is not None:
        return anuncio.get("available_quantity")
    return None


_RE_NUM = re.compile(r"^\d+")

def _normalize_gtin(val: Any) -> Optional[str]:
    """
    Mantém apenas os dígitos iniciais (remove sufixos como '-50').
    Aceita GTIN/EAN de 8/12/13/14 dígitos, mas retorna dígitos mesmo fora do range p/ inspeção.
    """
    if not val:
        return None
    s = str(val).strip()
    m = _RE_NUM.match(s)
    if not m:
        return None
    digits = m.group(0)
    return digits  # não validamos checksum aqui; mantemos para auditoria


def _extract_gtin(anuncio: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Estratégia:
      1) campos diretos: 'gtin' ou 'ean'
      2) attributes: id em {'GTIN','EAN'} ou name contendo 'gtin'/'código universal de produto'
         valor: 'value_name' (fallback: first values[].name)
    """
    if not isinstance(anuncio, dict):
        return None

    # 1) chaves diretas
    for key in ("gtin", "ean"):
        if anuncio.get(key):
            gt = _normalize_gtin(anuncio[key])
            if gt:
                return gt

    # 2) attributes
    attrs = anuncio.get("attributes") or []
    if isinstance(attrs, list):
        for attr in attrs:
            if not isinstance(attr, dict):
                continue
            attr_id = (attr.get("id") or "").upper()
            attr_name = (attr.get("name") or "").lower()
            if attr_id in {"GTIN", "EAN"} or "gtin" in attr_name or "código universal de produto" in attr_name:
                candidate = attr.get("value_name")
                if not candidate and isinstance(attr.get("values"), list) and attr["values"]:
                    candidate = attr["values"][0].get("name")
                gt = _normalize_gtin(candidate)
                if gt:
                    return gt

    return None


def _enrich(payload: Dict[str, Any],
            lojas_limit: list[str] | None = None,
            keep_existing_gtin: bool = False) -> Dict[str, Any]:
    """
    Enriquecimento in-place:
      - adiciona 'estoque' por MLB
      - adiciona 'gtin' normalizado (se ausente ou se keep_existing_gtin=False)
    Estrutura esperada:
      payload = { "results": { "sp": { "MLB...": {...} }, "mg": {...} }, ... }
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

            anuncio = _get_anuncio(regiao=loja_key, mlb=mlb)

            # 1) Estoque
            rec["estoque"] = _get_estoque(anuncio)

            # 2) GTIN
            if not (keep_existing_gtin and rec.get("gtin")):
                gtin_val = _extract_gtin(anuncio)
                if gtin_val:
                    rec["gtin"] = gtin_val
                else:
                    # anotação leve para auditoria
                    notes = rec.setdefault("_notes", {})
                    notes["gtin_missing"] = True

            results[loja_key][mlb] = rec

    payload["results"] = results
    return payload


# -------------------------
# CLI
# -------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquece o JSON de vendas (7/15/30) com estoque e GTIN por MLB (sobrescreve por padrão)."
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
    parser.add_argument(
        "--keep-existing-gtin",
        action="store_true",
        help="Se presente, mantém o GTIN já existente no JSON e NÃO sobrescreve."
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
    enriched = _enrich(
        payload,
        lojas_limit=lojas_limit,
        keep_existing_gtin=bool(args.keep_existing_gtin),
    )

    # Sink configurado para o arquivo correto
    if args.outfile:
        sink = make_sink("json", output_dir=outfile.parent, filename=outfile.name, keep=2)
    else:
        sink = make_sink("json", output_dir=infile.parent, filename=infile.name, keep=2)
    sink.emit(enriched)
    print(f"[OK] JSON {'sobrescrito' if inplace else 'gerado'} em: {outfile if args.outfile else infile}")

    print(f"[OK] JSON {'sobrescrito' if inplace else 'gerado'} em: {outfile}")
    if lojas_limit:
        print(f"     Lojas processadas: {', '.join(lojas_limit)}")
    print(f"     keep-existing-gtin: {bool(args.keep_existing_gtin)}")


if __name__ == "__main__":
    main()
