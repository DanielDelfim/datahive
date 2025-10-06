#!/usr/bin/env python
from __future__ import annotations
import argparse
import sys
import json
from collections import Counter
from app.config.paths import Regiao
from app.utils.tax_documents.service import gerar_resumo_por_natureza_from_pp
from app.utils.tax_documents.config import pp_json_path

def parse_args():
    p = argparse.ArgumentParser(description="Resumo por Natureza a partir do PP (JSON).")
    p.add_argument("--provedor", required=True, choices=["meli","amazon","bling"])
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)   # ← CORRIGIDO
    p.add_argument("--regiao", type=str, help="SP/MG/ES (quando aplicável)")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--modo", choices=["todos","vendas","transferencias","outros"], default="todos")
    # extras
    p.add_argument("--stats", action="store_true", help="Mostra estatísticas do PP (situação/canceladas/denegadas/devolução)")
    return p.parse_args()

def _load_pp_rows(provedor, ano, mes, regiao):
    path = pp_json_path(provedor, ano, mes, regiao)
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return doc.get("rows") or []

def main():
    a = parse_args()
    regiao = Regiao[a.regiao] if a.regiao else None

    if a.stats:
        rows = _load_pp_rows(a.provedor, a.ano, a.mes, regiao)
        c_sit = Counter((r.get("Situacao NFe") or "desconhecida") for r in rows)
        c_dev = sum(1 for r in rows if str(r.get("Eh Devolucao","")).lower() in ("true","1"))
        print("[PP STATS]", {
            "total_linhas": len(rows),
            "situacao": dict(c_sit),
            "linhas_com_devolucao": c_dev,
            "exemplo_campos": ["CNPJ Emissor","Situacao NFe","Eh Devolucao","Possui CC-e","Em Contingencia"]
        })

    json_path = gerar_resumo_por_natureza_from_pp(a.provedor, a.ano, a.mes, regiao, modo=a.modo, dry_run=a.dry_run, debug=a.debug)
    print(json.dumps({"status": "dry-run" if a.dry_run else "ok", "json_target": json_path}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
