#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.utils.billing.xml.service import carregar_e_normalizar
from app.utils.billing.config import notas_normalizadas_json

# Preferência por result_sink; fallback para atomic_write_json se necessário
def _emit_json(obj, target: Path, sink_kind: str):
    try:
        if sink_kind in ("file", "both"):
            # tenta via result_sink
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
    ap = argparse.ArgumentParser(description="Importa ZIPs de NF (por ano/mês/região) e gera notas_normalizadas.json")
    ap.add_argument("--market", default="meli")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", action="append", required=True, help="Use múltiplas --regiao sp --regiao mg")
    ap.add_argument("--sink", choices=("file","stdout","both"), default="file")
    args = ap.parse_args()

    notas = carregar_e_normalizar(market=args.market, ano=args.ano, mes=args.mes, regioes=args.regiao)

    # Emite por REGIÃO separadamente (mantendo o “dono” regional do artefato)
    for regiao in args.regiao:
        alvo = notas_normalizadas_json(args.market, args.ano, args.mes, regiao)
        # filtra o subset da região
        subset = [n for n in notas if n.get("regiao") == regiao]
        _emit_json(subset, alvo, args.sink)

if __name__ == "__main__":
    main()
 