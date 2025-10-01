from __future__ import annotations
import argparse
from app.config.paths import Camada
from app.utils.costs.variable.overview.config import overview_all_dir
from app.utils.core.result_sink.service import make_sink, resolve_sink_from_flags
from app.utils.costs.variable.overview.service import build_metrics_consolidado

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extrai metrics de MG, SP e gera consolidado ALL")
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--to-file", dest="to_file", action="store_true", default=True)
    p.add_argument("--no-to-file", dest="to_file", action="store_false")
    p.add_argument("--stdout", dest="to_stdout", action="store_true", default=True)
    p.add_argument("--no-stdout", dest="to_stdout", action="store_false")
    return p.parse_args()

def main():
    args = parse_args()
    out_dir = overview_all_dir(args.ano, args.mes)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.debug:
        print(f"[DBG] output_dir = {out_dir}")

    bundle = build_metrics_consolidado(args.ano, args.mes, Camada.PP, debug=args.debug)
    mg, sp, allm = bundle["mg"], bundle["sp"], bundle["all"]

    sink_mg  = make_sink("json", output_dir=out_dir, filename="metrics_mg.json", keep=3)
    sink_sp  = make_sink("json", output_dir=out_dir, filename="metrics_sp.json", keep=3)
    sink_all = make_sink("json", output_dir=out_dir, filename="metrics_all.json", keep=5)

    if args.to_file:
        sink_mg.emit(mg, name="mg")
        sink_sp.emit(sp, name="sp")
        sink_all.emit(allm, name="all")

    if args.to_stdout:
        stdout_sink = resolve_sink_from_flags(to_file=False, to_stdout=True)
        stdout_sink.emit(mg, name="metrics_mg")
        stdout_sink.emit(sp, name="metrics_sp")
        stdout_sink.emit(allm, name="metrics_all")

if __name__ == "__main__":
    main()
