from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
from app.config.paths import Regiao
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.costs.variable.meli.config import (
    excel_dir, pp_dir,
    pp_outfile_tarifas_full_armazenamento,
    pp_outfile_tarifas_full_retirada_estoque,
    pp_outfile_tarifas_full_servico_coleta,
    pp_outfile_tarifas_full_armazenamento_prolongado,
)
from app.utils.costs.variable.meli.tarifas_full.service import (
    read_tarifa_armazenamento,
    read_custo_retirada_estoque,
    read_custo_servico_coleta,
    read_custo_armazenamento_prolongado,
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
    ap = argparse.ArgumentParser(description="Pré-processar Relatório de Tarifas Full (4 abas)")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", type=str, choices=[r.value for r in Regiao], required=True)
    ap.add_argument("--arquivo", type=str, default=None)
    ap.add_argument("--competencia", type=str, default=None, help="YYYY-MM; se omitido, será inferido")
    ap.add_argument("--data-root", type=str, default=None)
    ap.add_argument("--header-row", type=int, default=5, help="Linha do cabeçalho (0-based). Padrão: 5 (linha 6)")
    ap.add_argument("--to-file", dest="to_file", action="store_true")
    ap.set_defaults(to_file=True)
    ap.add_argument("--stdout", dest="to_stdout", action="store_true")
    ap.set_defaults(to_stdout=True)
    ap.add_argument("--debug", action="store_true")
    return ap.parse_args()

def main():
    args = parse_args()
    if args.data_root:
        os.environ["DATA_DIR"] = args.data_root

    reg = Regiao(args.regiao)
    xdir = excel_dir(args.ano, args.mes, reg)

    if args.arquivo:
        xlsx = Path(args.arquivo)
    else:
        pattern = "Relatorio_Tarifas_Full_*.xlsx"
        xs = sorted(xdir.glob(pattern))
        if not xs:
            raise FileNotFoundError(f"Sem XLSX com padrão {pattern} em {xdir}")
        if len(xs) > 1:
            raise RuntimeError(f"Mais de um XLSX: {', '.join(p.name for p in xs)}")
        xlsx = xs[0]

    if args.debug:
        print(f"[DBG] lendo: {xlsx} | header_row={args.header_row}")

    # --- ABA 1: Armazenamento ---
    rows1 = read_tarifa_armazenamento(str(xlsx), args.competencia, header_row=args.header_row)
    out1 = pp_outfile_tarifas_full_armazenamento(args.ano, args.mes, reg)
    sink1 = resolve_sink_from_flags(
    to_file=args.to_file,
    to_stdout=args.to_stdout,
    output_dir=pp_dir(args.ano, args.mes, reg),
    filename=out1.name,
    prefix="tarifas_full_armazenamento",
    keep=3,
)
    sink1.emit({"meta":{"ano":args.ano,"mes":args.mes,"regiao":reg.value,"competencia":args.competencia,"fonte":str(xlsx),"aba":"Tarifa de armazenamento","total_registros":len(rows1)},"rows":rows1},
               name=f"{args.ano}-{args.mes:02d}-{reg.value}-aba1")

    # --- ABA 2: Retirada de estoque ---
    rows2 = read_custo_retirada_estoque(str(xlsx), args.competencia, header_row=args.header_row)
    out2 = pp_outfile_tarifas_full_retirada_estoque(args.ano, args.mes, reg)
    # --- ABA 2 ---
    sink2 = resolve_sink_from_flags(
        to_file=args.to_file,
        to_stdout=args.to_stdout,
        output_dir=pp_dir(args.ano, args.mes, reg),
        filename=out2.name,
        prefix="tarifas_full_retirada_estoque",
        keep=3,
    )
    sink2.emit({"meta":{"ano":args.ano,"mes":args.mes,"regiao":reg.value,"competencia":args.competencia,"fonte":str(xlsx),"aba":"Custo por retirada de estoque","total_registros":len(rows2)},"rows":rows2},
               name=f"{args.ano}-{args.mes:02d}-{reg.value}-aba2")

    # --- ABA 3: Serviço de coleta ---
    rows3 = read_custo_servico_coleta(str(xlsx), args.competencia, header_row=args.header_row)
    out3 = pp_outfile_tarifas_full_servico_coleta(args.ano, args.mes, reg)
    sink3 = resolve_sink_from_flags(
    to_file=args.to_file,
    to_stdout=args.to_stdout,
    output_dir=pp_dir(args.ano, args.mes, reg),
    filename=out3.name,
    prefix="tarifas_full_servico_coleta",
    keep=3,
)
    sink3.emit({"meta":{"ano":args.ano,"mes":args.mes,"regiao":reg.value,"competencia":args.competencia,"fonte":str(xlsx),"aba":"Custo por serviço de coleta","total_registros":len(rows3)},"rows":rows3},
               name=f"{args.ano}-{args.mes:02d}-{reg.value}-aba3")

    # --- ABA 4: Armazenamento prolongado ---
    rows4 = read_custo_armazenamento_prolongado(str(xlsx), args.competencia, header_row=args.header_row)
    out4 = pp_outfile_tarifas_full_armazenamento_prolongado(args.ano, args.mes, reg)
    sink4 = resolve_sink_from_flags(
    to_file=args.to_file,
    to_stdout=args.to_stdout,
    output_dir=pp_dir(args.ano, args.mes, reg),
    filename=out4.name,
    prefix="tarifas_full_armazenamento_prolongado",
    keep=3,
)
    sink4.emit({"meta":{"ano":args.ano,"mes":args.mes,"regiao":reg.value,"competencia":args.competencia,"fonte":str(xlsx),"aba":"Custo de armazenamento prolonga","total_registros":len(rows4)},"rows":rows4},
               name=f"{args.ano}-{args.mes:02d}-{reg.value}-aba4")

    if args.debug:
        print(f"[OK] A1:{len(rows1)} → {out1 if args.to_file else '(sem arquivo)'}")
        print(f"[OK] A2:{len(rows2)} → {out2 if args.to_file else '(sem arquivo)'}")
        print(f"[OK] A3:{len(rows3)} → {out3 if args.to_file else '(sem arquivo)'}")
        print(f"[OK] A4:{len(rows4)} → {out4 if args.to_file else '(sem arquivo)'}")

if __name__ == "__main__":
    main()
