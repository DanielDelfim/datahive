#!/usr/bin/env python
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app.config.paths import DATA_DIR, Regiao  # DATA_DIR transversal; Regiao enum
from app.utils.precificacao.aggregator import gerar_pp_basico
from app.utils.core.result_sink.service import resolve_sink_from_flags


def _iso_now_tz() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_regiao(opt: str | None) -> List[Regiao]:
    if not opt or opt.lower() in {"all", "ambas", "ambos"}:
        # quando 'all': pedimos SP e MG ao service e concatenamos
        # (se no futuro houver mais regiões, basta acrescentar no enum)
        regs = []
        for r in Regiao:
            # apenas valores típicos sp/mg; ajuste conforme seu Enum
            if r.value.lower() in {"sp", "mg"}:
                regs.append(r)
        return regs
    s = opt.strip().lower()
    for r in Regiao:
        if s == r.value.lower() or s == r.name.lower():
            return [r]
    raise SystemExit(f"Região inválida: {opt!r}. Use sp, mg ou all.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Gera JSON PP de precificação do Mercado Livre (consumível pelo dashboard)."
    )
    ap.add_argument("--regiao", type=str, default="all", help="sp | mg | all (default: all)")
    ap.add_argument("--stdout", action="store_true", help="Imprimir em tela em vez de salvar arquivo")
    ap.add_argument("--to-file", action="store_true", help="Salvar arquivo JSON (padrão)")
    ap.add_argument("--output-dir", type=Path, default=DATA_DIR / "precificacao" / "meli" / "pp")
    ap.add_argument("--filename", type=str, default="precificar_meli_pp.json")
    ap.add_argument("--keep", type=int, default=5, help="Qtde de backups a manter (JsonFileSink)")
    ap.add_argument("--name", type=str, default="latest", help="Rótulo lógico (entra no nome quando aplicável)")
    args = ap.parse_args()

    # Política: se --stdout não for passado, gravar em arquivo
    to_file = args.to_file or not args.stdout
    to_stdout = args.stdout

    regioes = _parse_regiao(args.regiao)
    # 1) Gera payload PP básico via aggregator (concatena SP+MG quando all)
    payload = gerar_pp_basico(regiao=None if len(regioes) > 1 else regioes[0])

    # 3) escolhe sink (arquivo ou stdout)
    sink = resolve_sink_from_flags(
        to_file=to_file,
        to_stdout=to_stdout,
        output_dir=args.output_dir,
        prefix=None,            # filename fixo (PP consumível)
        keep=args.keep,
        filename=args.filename,
    )
    sink.emit(payload, name=args.name)


if __name__ == "__main__":
    main()
