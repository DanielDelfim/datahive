#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.utils.billing.config import (
    notas_normalizadas_json,
    resumo_por_natureza_json,
    resumo_consolidado_json,
)
from app.utils.billing.xml.service import agregar_metricas

def _read_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def _emit_json(obj, target: Path, sink_kind: str):
    try:
        if sink_kind in ("file", "both"):
            try:
                from app.utils.core.result_sink.service import create_sink
            except Exception:
                create_sink = None
            if create_sink:
                target.parent.mkdir(parents=True, exist_ok=True)
                sink = create_sink(kind="file", target=str(target))
                sink.emit(obj)
            else:
                from app.config.paths import atomic_write_json
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(target, obj, do_backup=True)
        if sink_kind in ("stdout", "both"):
            try:
                from app.utils.core.result_sink.service import create_sink
                sink = create_sink(kind="stdout")
                sink.emit(obj)
            except Exception:
                print(json.dumps(obj, ensure_ascii=False, indent=2))
    except Exception as e:
        raise SystemExit(f"[ERRO] Falha ao emitir JSON: {e}")

def main():
    ap = argparse.ArgumentParser(description="Agrega notas_normalizadas.json por natureza/CFOP/mês/região")
    ap.add_argument("--market", default="meli")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", action="append", required=True)
    ap.add_argument("--por", choices=("natureza","cfop","mes","regiao"), default="natureza")
    ap.add_argument("--consolidado", action="store_true", help="Gera também all/ com SP+MG")
    ap.add_argument("--sink", choices=("file","stdout","both"), default="file")
    args = ap.parse_args()

    # regionais
    for regiao in args.regiao:
        src = notas_normalizadas_json(args.market, args.ano, args.mes, regiao)
        notas = _read_json(src)
        resumo = agregar_metricas(notas, por=args.por)
        _emit_json(resumo, resumo_por_natureza_json(args.market, args.ano, args.mes, regiao), args.sink)

    # consolidado
    if args.consolidado:
        todas = []
        for regiao in args.regiao:
            src = notas_normalizadas_json(args.market, args.ano, args.mes, regiao)
            todas.extend(_read_json(src))
        resumo_all = agregar_metricas(todas, por=args.por)
        _emit_json(resumo_all, resumo_consolidado_json(args.market, args.ano, args.mes), args.sink)

if __name__ == "__main__":
    main()
