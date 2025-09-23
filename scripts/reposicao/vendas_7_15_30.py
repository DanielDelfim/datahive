# scripts/reposicao/vendas_7_15_30.py
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from app.utils.core.result_sink.service import make_sink
from typing import Iterable, Dict, Any

# --- Imports do projeto ---
# Serviços de vendas (resumos por janela/MLB)
from app.services.vendas_service import get_por_mlb  # noqa: E402
# Config de reposição: fornece diretórios padronizados sob data/marketplaces/meli/reposicao/
from app.utils.reposicao.config import RESULTS_DIR  # noqa: E402


def _parse_list_csv(s: str | None, default: Iterable[str]) -> list[str]:
    if not s:
        return list(default)
    return [x.strip().lower() for x in s.split(",") if x.strip()]


def _parse_int_csv(s: str | None, default: Iterable[int]) -> list[int]:
    if not s:
        return list(default)
    out: list[int] = []
    for x in s.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(int(x))
        except ValueError:
            raise ValueError(f"Valor de janela inválido: {x!r}. Use inteiros (ex.: 7,15,30).")
    return out


def build_payload(lojas: Iterable[str], windows: Iterable[int]) -> Dict[str, Any]:
    """
    Monta um payload consolidado com métricas por MLB para cada loja e cada janela.
    Usa o 'mode=\"ml\"' (padrão) do serviço de vendas.
    """
    lojas_norm = [loja.lower() for loja in lojas]
    windows_norm = list(windows)

    data: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "windows": windows_norm,
        "lojas": lojas_norm,
        "results": {},  # por loja
    }

    for loja in lojas_norm:
        # get_por_mlb retorna um dicionário com agregações por MLB para as janelas pedidas
        # (o serviço já carrega o PP correto da loja e aplica os filtros/modo)
        per_mlb = get_por_mlb(loja=loja, windows=windows_norm, mode="ml")
        data["results"][loja] = per_mlb

    return data


# saída agora é delegada ao ResultSink (json com backup+rotação)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera vendas agregadas (7/15/30) para reposição em um JSON único."
    )
    parser.add_argument(
        "--lojas",
        help="Lista de lojas separadas por vírgula (ex.: SP,MG). Default: SP,MG",
        default="SP,MG",
    )
    parser.add_argument(
        "--windows",
        help="Janelas de dias separadas por vírgula (ex.: 7,15,30). Default: 7,15,30",
        default="7,15,30",
    )
    parser.add_argument(
        "--outfile",
        help="Caminho de saída do JSON. Por padrão usa RESULTS_DIR()/vendas_7_15_30.json",
        default=None,
    )
    args = parser.parse_args()

    lojas = _parse_list_csv(args.lojas, default=("sp", "mg"))
    windows = _parse_int_csv(args.windows, default=(7, 15, 30))

    payload = build_payload(lojas=lojas, windows=windows)

    # Caminho de saída: C:\Apps\Datahive\data\marketplaces\meli\reposicao\results\vendas_7_15_30.json
    results_dir = RESULTS_DIR()
    if args.outfile:
        # respeita caminho explícito do usuário
        out_path = Path(args.outfile)
        sink = make_sink("json", output_dir=out_path.parent, filename=out_path.name, keep=2)
    else:
        sink = make_sink("json", output_dir=results_dir, filename="vendas_7_15_30.json", keep=2)
    sink.emit(payload)

    # Log simpático no console
    print(f"[OK] JSON gerado em: {(out_path if args.outfile else (results_dir/'vendas_7_15_30.json'))}")
    print(f"     Lojas: {', '.join(lojas)} | Janelas: {', '.join(map(str, windows))}")


if __name__ == "__main__":
    main()
