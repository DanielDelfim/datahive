from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
from app.config.paths import Regiao
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.costs.variable.meli.config import (
    excel_dir, pp_dir,
    pp_outfile_pagamentos_estornos, pp_outfile_detalhe_pagamentos
)
from app.utils.costs.variable.meli.pagamento_faturas.service import (
    read_pagamentos_estornos, read_detalhe_pagamentos_mes
)
# --- bootstrap para rodar de qualquer diretório ---
def _find_project_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "app").exists():
            return p
    return start
THIS_FILE = Path(__file__).resolve()
ROOT = _find_project_root(THIS_FILE)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# --- fim bootstrap ---

def parse_args():
    ap = argparse.ArgumentParser(description="Pré-processar Relatório de Pagamento de Faturas (2 abas)")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", type=str, choices=[r.value for r in Regiao], required=True)
    ap.add_argument("--arquivo", type=str, default=None, help="Caminho do XLSX (opcional)")
    ap.add_argument("--competencia", type=str, default=None, help="YYYY-MM; se omitido, será inferido")
    ap.add_argument("--data-root", type=str, default=None, help="Override DATA_DIR")
    ap.add_argument("--header-row", type=int, default=9, help="Linha do cabeçalho (0-based). Padrão: 9 (linha 10).")
    ap.add_argument("--to-file", dest="to_file", action="store_true")
    ap.set_defaults(to_file=True)
    ap.add_argument("--stdout", dest="to_stdout", action="store_true")
    ap.set_defaults(to_stdout=True)
    ap.add_argument("--debug", action="store_true")
    return ap.parse_args()

def _pick_xlsx(xdir: Path, pattern: str) -> Path:
    xs = sorted(xdir.glob(pattern))
    if not xs:
        raise FileNotFoundError(f"Nenhum XLSX com padrão {pattern} em {xdir}")
    if len(xs) > 1:
        raise RuntimeError(f"Mais de um XLSX: {', '.join(p.name for p in xs)}")
    return xs[0]

def main():
    args = parse_args()
    if args.data_root:
        os.environ["DATA_DIR"] = args.data_root

    reg = Regiao(args.regiao)
    xdir = excel_dir(args.ano, args.mes, reg)

    if args.arquivo:
        xlsx = Path(args.arquivo)
    else:
        pattern = "Relatorio_Pagamento_Faturas_*.xlsx"
        xlsx = _pick_xlsx(xdir, pattern)

    if args.debug:
        print(f"[DBG] lendo: {xlsx} | header_row={args.header_row}")

    # --- ABA 1 ---
    rows_1 = read_pagamentos_estornos(str(xlsx), competencia=args.competencia, header_row=args.header_row)
    outfile_1 = pp_outfile_pagamentos_estornos(args.ano, args.mes, reg)
    sink_1 = resolve_sink_from_flags(
        to_file=args.to_file, to_stdout=args.to_stdout,
        output_dir=pp_dir(args.ano, args.mes, reg),
        filename=outfile_1.name, prefix="pagamentos_estornos", keep=3
    )
    payload_1 = {
        "meta": {
            "ano": args.ano, "mes": args.mes, "regiao": reg.value,
            "competencia": args.competencia, "fonte": str(xlsx),
            "aba": "Pagamentos e estornos", "total_registros": len(rows_1),
        },
        "rows": rows_1,
    }
    sink_1.emit(payload_1, name=f"{args.ano}-{args.mes:02d}-{reg.value}-aba1")

    # --- ABA 2 ---
    rows_2 = read_detalhe_pagamentos_mes(str(xlsx), competencia=args.competencia, header_row=args.header_row)
    outfile_2 = pp_outfile_detalhe_pagamentos(args.ano, args.mes, reg)
    sink_2 = resolve_sink_from_flags(
        to_file=args.to_file, to_stdout=args.to_stdout,
        output_dir=pp_dir(args.ano, args.mes, reg),
        filename=outfile_2.name, prefix="detalhe_pagamentos_mes", keep=3
    )
    payload_2 = {
        "meta": {
            "ano": args.ano, "mes": args.mes, "regiao": reg.value,
            "competencia": args.competencia, "fonte": str(xlsx),
            "aba": "Detalhe do Pagamentos deste mês", "total_registros": len(rows_2),
        },
        "rows": rows_2,
    }
    sink_2.emit(payload_2, name=f"{args.ano}-{args.mes:02d}-{reg.value}-aba2")

    if args.debug:
        print(f"[OK] Aba1: {len(rows_1)} → {outfile_1 if args.to_file else '(sem arquivo)'}")
        print(f"[OK] Aba2: {len(rows_2)} → {outfile_2 if args.to_file else '(sem arquivo)'}")

if __name__ == "__main__":
    main()
