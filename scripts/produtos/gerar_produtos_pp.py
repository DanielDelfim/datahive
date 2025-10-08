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

import hashlib
import json
import sys
from typing import Dict, Any

from datetime import datetime, timezone

from app.config.paths import Camada  # transversal (Enums)
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.produtos.config import (
    cadastro_produtos_excel,
    produtos_dir,
    produtos_json,
)
from app.utils.produtos.service import normalizar_excel_detalhado

from app.utils.produtos.config import get_paths

excel_path = (
    get_paths().excel
)  # agora aponta para data/produtos/excel/cadastro_produtos_template.xlsx

MARKETPLACE = "site"  # ou "meli" se preferir
REGIAO = None  # Produtos PP é transversal; pode ser "br" ou None
SCHEMA_VERSION = "1.0.0"
SCRIPT_NAME = "scripts/produtos/gerar_produtos_pp.py"
SCRIPT_VERSION = "1.0.0"

# --- NOVO util: sanitização recursiva p/ JSON ---
from pathlib import Path
from decimal import Decimal
import numpy as np


def _to_jsonable(obj):
    """Converte recursivamente valores não-serializáveis (Path, Decimal, numpy, sets) em tipos JSON."""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (Path,)):
        return str(obj)
    if isinstance(obj, (Decimal, np.floating, np.integer)):
        return float(obj)
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    # fallback: stringifica
    return str(obj)


def _stable_hash(items: dict) -> str:
    ordered = json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(ordered).hexdigest()


# --- SUBSTITUA build_payload por esta versão ---
def build_payload() -> Dict[str, Any]:
    registros, skipped = normalizar_excel_detalhado()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload: Dict[str, Any] = {
        "_meta": {
            "generated_at_utc": now,
            "stage": "dev",
            "marketplace": MARKETPLACE,
            "regiao": REGIAO,
            "camada": Camada.PP.value,
            "schema_version": SCHEMA_VERSION,
            "script_name": SCRIPT_NAME,
            "script_version": SCRIPT_VERSION,
            # ⚠️ converter Path -> str
            "source_paths": [str(cadastro_produtos_excel())],
            "row_count": len(registros),
            "hash": _stable_hash(registros),
            "warnings": [],
        },
        "count": len(registros),
        "source": str(cadastro_produtos_excel()),
        "items": dict(sorted(registros.items())),  # determinismo
        "skipped_count": len(skipped),
        "skipped_preview": skipped[:3],  # útil p/ debug rápido no JSON
    }
    return payload, skipped


# --- SUBSTITUA write_payload por esta versão (usa o sanitizador) ---
def write_payload(
    payload: Dict[str, Any],
    skipped: list,
    *,
    to_file: bool,
    to_stdout: bool,
    keep: int,
    filename: str,
) -> str:
    out_dir = produtos_dir(Camada.PP)
    out_path = produtos_json(Camada.PP)
    sink = resolve_sink_from_flags(
        to_file=to_file,
        to_stdout=to_stdout,
        output_dir=out_dir,
        prefix="produtos",
        keep=keep,
        filename=filename,
    )
    # ⚠️ sanitiza antes de emitir
    sink.emit(_to_jsonable(payload))

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
        skipped_sink.emit(_to_jsonable({"count": len(skipped), "items": skipped}))
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
            payload,
            skipped,
            to_file=args.to_file,
            to_stdout=args.to_stdout,
            keep=args.keep,
            filename=args.filename,
        )
        print(
            f"[OK] Produtos PP -> {final_path} (itens: {payload['count']}, ignorados: {payload.get('skipped_count', 0)})"
        )
        # Log amigável dos ignorados (até 10 linhas)
        if skipped:
            print("\n[INFO] Produtos ignorados (primeiros 10):")
            for s in skipped[:10]:
                sku = s.get("sku_detectado") or "-"
                tit = (s.get("titulo_detectado") or "-")[:60]
                motivos = ",".join(s.get("motivos") or [])
                print(
                    f"  • linha {s['row_index']}: sku={sku} | titulo={tit} | motivos={motivos}"
                )
        return 0
    except Exception as exc:
        # Log simples para CI/terminal; detalhes ficam no traceback padrão do Python se necessário
        print(f"[ERR] Falha ao gerar produtos_pp.json: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
