# scripts/produtos/gerar_produtos_pp.py
"""
Gera o arquivo produtos_pp.json a partir do Excel de cadastro.

Arquitetura:
- Leitura & normalização: app/utils/produtos/agregador.py (sem I/O de escrita)
- Paths do módulo: app/utils/produtos/config.py
- Escrita: result_sink (JsonFileSink) com rotação/backup atômico

Regra de ouro:
- Este script é o ÚNICO autor do produtos_pp.json (camada PP).
"""

from __future__ import annotations

import sys
from typing import Dict, Any

from app.config.paths import Camada  # transversal (Enums)
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.produtos.config import (
    cadastro_produtos_excel,
    produtos_dir,
    produtos_json,
)
from app.utils.produtos.aggregator import carregar_excel_normalizado_detalhado

from app.utils.produtos.config import get_paths
excel_path = get_paths().excel  # agora aponta para data/produtos/excel/cadastro_produtos_template.xlsx

def build_payload() -> Dict[str, Any]:
    """
    Carrega o Excel, normaliza em memória e devolve o payload pronto
    para escrita no JSON PP.
    """
    excel_path = cadastro_produtos_excel()
    registros, skipped = carregar_excel_normalizado_detalhado(excel_path)
    payload: Dict[str, Any] = {
        "count": len(registros),
        "source": str(excel_path),
        "items": registros,
        "skipped_count": len(skipped),
    }
    return payload, skipped


def write_payload(payload: Dict[str, Any], skipped: list, *, to_file: bool, to_stdout: bool, keep: int, filename: str) -> str:
    """
    Emite o payload usando JsonFileSink (result_sink) para o diretório PP do módulo.
    Retorna o caminho final (str) para conveniência de logs.
    """
    out_dir = produtos_dir(Camada.PP)
    out_path = produtos_json(Camada.PP)  # apenas para log; o sink também salva neste dir
    sink = resolve_sink_from_flags(
        to_file=to_file,
        to_stdout=to_stdout,
        output_dir=out_dir,
        prefix="produtos",
        keep=keep,
        filename=filename,
    )
    sink.emit(payload)
    # Relatório de ignorados
    if skipped and to_file:
        skipped_sink = resolve_sink_from_flags(
            to_file=to_file,
            to_stdout=False,
            output_dir=out_dir,
            prefix="produtos_skipped",
            keep=max(keep, 5),
            filename="produtos_skipped.json",
        )
        skipped_sink.emit({"count": len(skipped), "items": skipped})
    return str(out_path)


def main() -> int:
    try:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--to-file", dest="to_file", action="store_true", default=True)
        ap.add_argument("--no-to-file", dest="to_file", action="store_false")
        ap.add_argument("--stdout", dest="to_stdout", action="store_true", default=True)
        ap.add_argument("--no-stdout", dest="to_stdout", action="store_false")
        ap.add_argument("--keep", type=int, default=3, help="Qtde de backups a manter")
        ap.add_argument("--filename", type=str, default="produtos.json")
        args = ap.parse_args()

        payload, skipped = build_payload()
        final_path = write_payload(
            payload, skipped,
            to_file=args.to_file, to_stdout=args.to_stdout,
            keep=args.keep, filename=args.filename
        )
        print(f"[OK] Produtos PP -> {final_path} (itens: {payload['count']}, ignorados: {payload.get('skipped_count', 0)})")
        # Log amigável dos ignorados (até 10 linhas)
        if skipped:
            print("\n[INFO] Produtos ignorados (primeiros 10):")
            for s in skipped[:10]:
                sku = s.get("sku_detectado") or "-"
                tit = (s.get("titulo_detectado") or "-")[:60]
                motivos = ",".join(s.get("motivos") or [])
                print(f"  • linha {s['row_index']}: sku={sku} | titulo={tit} | motivos={motivos}")
        return 0
    except Exception as exc:
        # Log simples para CI/terminal; detalhes ficam no traceback padrão do Python se necessário
        print(f"[ERR] Falha ao gerar produtos_pp.json: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
