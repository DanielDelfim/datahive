# scripts/reposicao/gerar_metricas.py
from __future__ import annotations
import argparse
from pathlib import Path

from app.utils.reposicao.aggregator import build_snapshot, write_snapshot
from app.utils.reposicao.config import RESULTS_DIR


def _parse_list_csv(s: str | None, cast=int):
    if not s:
        return None
    out = []
    for x in s.split(","):
        x = x.strip()
        if not x:
            continue
        out.append(cast(x) if cast else x)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Gera snapshot de reposição com métricas por MLB "
            "(médias diárias, projeções 30/60d, consumo e reposição em horizonte). "
            "Salva no JSON padrão, sobrescrevendo."
        )
    )
    parser.add_argument("--lojas", default="SP,MG", help="Ex.: SP,MG (default: SP,MG)")
    parser.add_argument("--windows", default="7,15,30", help="Ex.: 7,15,30 (default: 7,15,30)")
    parser.add_argument(
        "--horizonte",
        type=int,
        default=7,
        help="Horizonte de reposição (dias) para consumo/reposição/estoque projetado. Default: 7",
    )
    parser.add_argument(
        "--outfile",
        default=None,
        help="Arquivo de saída (opcional). Default: sobrescreve RESULTS_DIR()/vendas_7_15_30.json",
    )

    args = parser.parse_args()

    lojas = _parse_list_csv(args.lojas, cast=str) or ["SP", "MG"]
    lojas = [loja.strip().lower() for loja in lojas]
    windows = _parse_list_csv(args.windows, cast=int) or [7, 15, 30]

    payload = build_snapshot(
        lojas=lojas,
        windows=windows,
        horizonte_reposicao_dias=int(args.horizonte),
        # lote_multiplo: ainda não habilitado
    )

    out = (
        write_snapshot(payload, dest=Path(args.outfile))
        if args.outfile
        else write_snapshot(payload, dest=RESULTS_DIR() / "vendas_7_15_30.json")
    )

    print(f"[OK] Snapshot salvo em: {out}")
    print(f"     Lojas: {', '.join(lojas)} | Janelas: {', '.join(map(str, windows))} | Horizonte: {args.horizonte}d")


if __name__ == "__main__":
    main()
