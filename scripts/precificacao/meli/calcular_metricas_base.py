#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Tuple

from app.config.paths import DATA_DIR
from app.utils.core.io import ler_json
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.precificacao.config import get_regras_ml
from app.utils.precificacao.metrics import enriquecer_item_com_metricas


def _extract_itens(payload: Any) -> Tuple[list, bool]:
    """
    Retorna (lista_itens, wrap_needed).
    Se payload já for lista, wrap_needed=True para re-encapsular ao salvar.
    Se payload for dict com 'itens', wrap_needed=False.
    """
    if isinstance(payload, list):
        return payload, True
    if isinstance(payload, dict) and isinstance(payload.get("itens"), list):
        return payload["itens"], False
    raise SystemExit("Formato inesperado do PP: esperado dict com 'itens' ou lista de itens.")


def _to_float(x) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _processar(pp_path: Path) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Lê o PP, aplica métricas por item usando regras do YAML e retorna:
      (payload_atualizado, resumo)
    """
    # Carregar payload
    payload = ler_json(pp_path)
    itens, wrap_needed = _extract_itens(payload)

    # Carregar regras (já normalizadas/validadas no módulo)
    regras = get_regras_ml()

    # Loop de enriquecimento
    total = 0
    processados = 0
    ignorados_sem_preco = 0
    ignorados_sem_custo = 0

    for ad in itens:
        if not isinstance(ad, dict):
            continue
        total += 1

        preco = _to_float(ad.get("preco_venda"))
        custo = _to_float(ad.get("preco_custo"))
        if preco is None:
            ignorados_sem_preco += 1
            # mantém item como está (sem métricas)
            continue
        if custo is None:
            ignorados_sem_custo += 1
            # mantém item como está (sem métricas)
            continue

        # Enriquecer métricas neste item (PURO)
        enriquecer_item_com_metricas(ad, regras)
        processados += 1

    # Re-encapsular (mantemos a estrutura padrão do PP consumível por dashboard)
    new_payload = {"canal": "meli", "versao": 1, "itens": itens} if wrap_needed else payload

    resumo = {
        "total_itens": total,
        "processados": processados,
        "ignorados_sem_preco": ignorados_sem_preco,
        "ignorados_sem_custo": ignorados_sem_custo,
    }
    return new_payload, resumo


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Calcula e enriquece métricas no PP usando regras do YAML (fixo por faixa + frete % sobre custo + sugestões de preço)."
    )
    ap.add_argument(
        "--pp-path",
        type=Path,
        default=DATA_DIR / "precificacao" / "meli" / "pp" / "precificar_meli_pp.json",
        help="Caminho do PP a enriquecer com métricas.",
    )
    ap.add_argument("--stdout", action="store_true", help="Imprimir em tela em vez de salvar arquivo")  # False por padrão
    ap.add_argument("--to-file", action="store_true", help="Salvar arquivo JSON (padrão)")
    ap.add_argument("--output-dir", type=Path, default=DATA_DIR / "precificacao" / "meli" / "pp")
    ap.add_argument("--filename", type=str, default="precificar_meli_pp.json")
    ap.add_argument("--keep", type=int, default=5, help="Qtde de backups a manter (JsonFileSink)")
    ap.add_argument("--name", type=str, default="latest", help="Rótulo lógico (entra no nome quando aplicável)")
    args = ap.parse_args()

    # Política: se não passar --stdout, salvamos em arquivo
    to_file = args.to_file or not args.stdout
    to_stdout = args.stdout

    # Processar
    payload, resumo = _processar(pp_path=args.pp_path)

    # Feedback rápido no console
    print(
        "[calcular_metricas_base] "
        f"total={resumo['total_itens']} | "
        f"processados={resumo['processados']} | "
        f"sem_preco={resumo['ignorados_sem_preco']} | "
        f"sem_custo={resumo['ignorados_sem_custo']}"
    )

    # Emissão via sink (mesmo arquivo por padrão)
    sink = resolve_sink_from_flags(
        to_file=to_file,
        to_stdout=to_stdout,
        output_dir=args.output_dir,
        prefix=None,
        keep=args.keep,
        filename=args.filename,
    )
    sink.emit(payload, name=args.name)


if __name__ == "__main__":
    main()
