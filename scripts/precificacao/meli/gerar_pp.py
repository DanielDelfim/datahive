#!/usr/bin/env python
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config.paths import DATA_DIR, Regiao  # DATA_DIR é transversal (ok)
from app.utils.precificacao.service import precificar_meli
from app.utils.core.result_sink.service import resolve_sink_from_flags


def _iso_now() -> str:
    # ISO 8601 com timezone (UTC); dashboards podem exibir em local time
    return datetime.now(timezone.utc).isoformat()


def _parse_regiao(s: Optional[str]) -> Optional[Regiao]:
    if not s:
        return None
    s_norm = s.strip().lower()
    for r in Regiao:
        if r.value.lower() == s_norm or r.name.lower() == s_norm:
            return r
    raise SystemExit(f"Região inválida: {s!r}. Use um dos valores: {[e.value for e in Regiao]}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Gera JSON PP de precificação para Mercado Livre (consumível pelo dashboard)."
    )
    ap.add_argument("--stdout", action="store_true", help="Imprimir em tela em vez de salvar arquivo")
    ap.add_argument("--to-file", action="store_true", help="Salvar arquivo JSON (padrão)")
    ap.add_argument("--output-dir", type=Path, default=DATA_DIR / "precificacao" / "meli" / "pp")
    ap.add_argument("--filename", type=str, default="precificacao_meli_pp.json")
    ap.add_argument("--keep", type=int, default=5, help="Qtde de backups a manter (JsonFileSink)")
    ap.add_argument("--name", type=str, default="latest", help="Rótulo lógico (entra no nome quando aplicável)")
    ap.add_argument("--regiao", type=str, default=None, help="Ex.: sp, mg (opcional)")
    args = ap.parse_args()

    # Política padrão: se --stdout não for passado, gravar em arquivo
    to_file = args.to_file or not args.stdout
    to_stdout = args.stdout

    regiao = _parse_regiao(args.regiao)

    # 1) Calcula (somente leitura)
    itens = precificar_meli(regiao=regiao)

    # 2) Monta payload PP consumível por dashboard
    payload = {
        "canal": "meli",
        "versao": 1,
        "gerado_em": _iso_now(),
        "regiao": regiao.value if regiao else None,
        "itens": itens,  # lista já com breakdown e mcp_pct
    }

    # 3) Escolhe sink (arquivo ou stdout)
    sink = resolve_sink_from_flags(
        to_file=to_file,
        to_stdout=to_stdout,
        output_dir=args.output_dir,
        prefix=None,            # como passamos filename fixo, prefix não é necessário
        keep=args.keep,
        filename=args.filename, # grava sempre no mesmo nome (PP consumível)
    )

    # 4) Emite resultado
    sink.emit(payload, name=args.name)


if __name__ == "__main__":
    main()
