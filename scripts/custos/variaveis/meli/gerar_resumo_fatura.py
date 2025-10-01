from __future__ import annotations

# --- bootstrap para rodar de qualquer diretório ---
from pathlib import Path
import sys
import argparse
from app.config.paths import Regiao
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.costs.variable.meli.config import pp_dir, pp_outfile_fatura_resumo
from app.utils.costs.variable.meli.resumo_fatura.service import build_resumo_fatura

def _find_project_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "app").exists():
            return p
    return start
THIS_FILE = Path(__file__).resolve()
ROOT = _find_project_root(THIS_FILE)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def parse_args():
    ap = argparse.ArgumentParser(description="Gerar resumo da fatura (consolidado)")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", type=str, choices=[r.value for r in Regiao], required=True)
    ap.add_argument("--competencia", type=str, default=None)
    ap.add_argument("--to-file", dest="to_file", action="store_true")
    ap.set_defaults(to_file=True)
    ap.add_argument("--stdout", dest="to_stdout", action="store_true")
    ap.set_defaults(to_stdout=True)
    ap.add_argument("--debug", action="store_true")
    return ap.parse_args()

def main():
    args = parse_args()
    reg = Regiao(args.regiao)
    resumo = build_resumo_fatura(args.ano, args.mes, reg, competencia=args.competencia)

    outfile = pp_outfile_fatura_resumo(args.ano, args.mes, reg)
    sink = resolve_sink_from_flags(
        to_file=args.to_file,
        to_stdout=args.to_stdout,
        output_dir=pp_dir(args.ano, args.mes, reg),
        filename=outfile.name,
        prefix="fatura_resumo",
        keep=3,
    )

    sink.emit(resumo, name=f"{args.ano}-{args.mes:02d}-{reg.value}")
    if args.debug:
        print(f"[OK] Resumo gerado → {outfile if args.to_file else '(sem arquivo)'}")

if __name__ == "__main__":
    main()
