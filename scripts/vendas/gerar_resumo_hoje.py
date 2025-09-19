# scripts/vendas/gerar_resumo_hoje.py
from __future__ import annotations
import sys

from app.config.paths import ensure_dirs, vendas_resumo_hoje_json, pp_dir
from app.utils.core.io import atomic_write_json
from app.services.vendas_service import get_resumo_hoje

USO = "Uso: python -m scripts.vendas.gerar_resumo_hoje [sp|mg]"

def main(argv: list[str]) -> None:
    ensure_dirs()
    if len(argv) < 2 or argv[1].strip().lower() not in ("sp", "mg"):
        raise SystemExit(USO)
    loja = argv[1].strip().lower()

    payload = get_resumo_hoje(loja)
    out = vendas_resumo_hoje_json(loja)
    pp_dir(loja).mkdir(parents=True, exist_ok=True)
    atomic_write_json(out, payload, do_backup=True)
    print(f"✓ resumo_today salvo: {out}")

if __name__ == "__main__":
    try:
        main(sys.argv)
    except SystemExit as e:
        print(str(e) or USO)
        raise
    except Exception as e:
        print(f"✗ ERRO: {e}")
        raise
