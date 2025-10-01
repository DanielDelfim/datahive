from __future__ import annotations
import argparse
from pathlib import Path
from app.config.paths import Regiao
from app.utils.core.result_sink.service import resolve_sink_from_flags   # fabrica + resolver  :contentReference[oaicite:5]{index=5}
from app.utils.costs.variable.meli.config import excel_dir, pp_outfile_faturamento_meli, pp_dir
from app.utils.costs.variable.meli.faturamento_meli.service import read_faturamento_meli_excel

def parse_args():
    ap = argparse.ArgumentParser(description="Pré-processar Relatório de Faturamento ML (REPORT)")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", type=str, choices=[r.value for r in Regiao], required=True)
    ap.add_argument("--arquivo", type=str, default=None, help="Se ausente, identifica na pasta excel/")
    ap.add_argument("--competencia", type=str, default=None, help="YYYY-MM; se omitido, será inferido")
    # Destino (result_sink)
    ap.add_argument("--to-file", dest="to_file", action="store_true", help="Gravar JSON no diretório pp/")
    ap.add_argument("--no-to-file", dest="to_file", action="store_false")
    ap.set_defaults(to_file=True)  # padrão: grava arquivo
    ap.add_argument("--stdout", dest="to_stdout", action="store_true", help="Também imprimir em tela (preview)")
    ap.add_argument("--no-stdout", dest="to_stdout", action="store_false")
    ap.set_defaults(to_stdout=True)
    ap.add_argument("--debug", action="store_true")
    return ap.parse_args()

def main():
    args = parse_args()
    reg = Regiao(args.regiao)

    xdir = excel_dir(args.ano, args.mes, reg)
    if args.arquivo:
        xlsx = Path(args.arquivo)
    else:
        xs = sorted(xdir.glob("Relatorio_Faturamento_MercadoLivre_*.xlsx"))
        if not xs:
            raise FileNotFoundError(f"Nenhum arquivo XLSX encontrado em {xdir}")
        if len(xs) > 1:
            raise RuntimeError(f"Mais de um XLSX em {xdir}: {', '.join(p.name for p in xs)}")
        xlsx = xs[0]

    records = read_faturamento_meli_excel(str(xlsx), competencia=args.competencia)

    # --- ResultSink: decide saída (arquivo pp e/ou stdout) ---
    outfile = pp_outfile_faturamento_meli(args.ano, args.mes, reg)
    sink = resolve_sink_from_flags(
        to_file=args.to_file,
        to_stdout=args.to_stdout,
        output_dir=pp_dir(args.ano, args.mes, reg),
        filename=outfile.name,   # mantém nome exato
        prefix="faturamento_meli",  # redundância segura se filename não for usado
        keep=3,  # quantos backups manter
    )

    payload = {
        "meta": {
            "ano": args.ano, "mes": args.mes, "regiao": reg.value,
            "competencia": args.competencia,
            "fonte": str(xlsx),
            "total_registros": len(records),
        },
        "rows": records,
    }

    # Emite (JSON em arquivo e/ou stdout)
    sink.emit(payload, name=f"{args.ano}-{args.mes:02d}-{reg.value}")

    if args.debug:
        print(f"[OK] Registros: {len(records)} | outfile: {outfile if args.to_file else '(sem arquivo)'}")

if __name__ == "__main__":
    main()
