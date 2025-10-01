from __future__ import annotations
import argparse
import os
from pathlib import Path
from app.config.paths import Regiao
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.costs.variable.meli.config import (
    excel_dir, pp_dir, pp_outfile_faturamento_mercadopago
)
from app.utils.costs.variable.meli.faturamento_mercadopago.service import (
    read_faturamento_mercadopago_excel
)

def parse_args():
    ap = argparse.ArgumentParser(description="Pré-processar Relatório de Faturamento Mercado Pago (REPORT)")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", type=str, choices=[r.value for r in Regiao], required=True)
    ap.add_argument("--arquivo", type=str, default=None, help="Caminho do XLSX (opcional)")
    ap.add_argument("--competencia", type=str, default=None, help="YYYY-MM; se omitido, será inferido")
    ap.add_argument("--header-row", type=int, default=7, help="Linha do cabeçalho (0-based). Padrão: 7 (linha 8).")
    ap.add_argument("--sheet", type=str, default="REPORT", help="Nome da aba. Padrão: REPORT")

    # result sink flags (arquivo + stdout por padrão)
    ap.add_argument("--to-file", dest="to_file", action="store_true")
    ap.set_defaults(to_file=True)
    ap.add_argument("--stdout", dest="to_stdout", action="store_true")
    ap.set_defaults(to_stdout=True)

    # raiz de dados (override)
    ap.add_argument("--data-root", type=str, default=None, help="Override DATA_DIR para localizar planilhas")
    ap.add_argument("--debug", action="store_true")
    return ap.parse_args()

def _debug_list_xlsx(folder: Path):
    if not folder.exists():
        print(f"[DBG] pasta não existe: {folder}")
        return
    xs = list(folder.glob("*.xlsx"))
    if xs:
        print(f"[DBG] XLSX em {folder}:")
        for f in xs:
            print("   -", f.name)
    else:
        print(f"[DBG] nenhum .xlsx em {folder}")

def main():
    args = parse_args()
    if args.data_root:
        os.environ["DATA_DIR"] = args.data_root

    reg = Regiao(args.regiao)
    xdir = excel_dir(args.ano, args.mes, reg)

    if args.arquivo:
        xlsx = Path(args.arquivo)
    else:
        pattern = "Relatorio_Faturamento_MercadoPago_*.xlsx"
        xs = sorted(xdir.glob(pattern))
        if not xs:
            if args.debug:
                print(f"[DBG] padrão não encontrado: {pattern}")
                _debug_list_xlsx(xdir)
            raise FileNotFoundError(f"Sem XLSX do Mercado Pago em {xdir}")
        if len(xs) > 1:
            raise RuntimeError(f"Mais de um XLSX: {', '.join(p.name for p in xs)}")
        xlsx = xs[0]

    if args.debug:
        print(f"[DBG] lendo: {xlsx} | sheet={args.sheet} header_row={args.header_row}")

    records = read_faturamento_mercadopago_excel(
        str(xlsx),
        competencia=args.competencia,
        header_row=args.header_row,
        sheet_name=args.sheet,
    )

    outfile = pp_outfile_faturamento_mercadopago(args.ano, args.mes, reg)
    sink = resolve_sink_from_flags(
        to_file=args.to_file,
        to_stdout=args.to_stdout,
        output_dir=pp_dir(args.ano, args.mes, reg),
        filename=outfile.name,
        prefix="faturamento_mercadopago",
        keep=3,
    )

    payload = {
        "meta": {
            "ano": args.ano,
            "mes": args.mes,
            "regiao": reg.value,
            "competencia": args.competencia,
            "fonte": str(xlsx),
            "total_registros": len(records),
        },
        "rows": records,
    }

    # Como já serializamos no aggregator, não deve falhar — mas o sink também lida.
    sink.emit(payload, name=f"{args.ano}-{args.mes:02d}-{reg.value}")

    if args.debug:
        print(f"[OK] registros: {len(records)} | outfile: {outfile if args.to_file else '(sem arquivo)'}")

if __name__ == "__main__":
    main()
