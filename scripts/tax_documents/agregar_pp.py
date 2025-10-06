#!/usr/bin/env python
from __future__ import annotations
import argparse
import sys
import json
from app.config.paths import Regiao
from app.utils.tax_documents.service import gerar_pp_json
from app.utils.tax_documents.config import COLUMNS

def parse_args():
    p = argparse.ArgumentParser(description="Consolida XML de NF-e (ZIP) em PP mensal (JSON).")
    p.add_argument("--provedor", required=True, choices=["meli","amazon","bling"])
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--regiao", type=str, help="SP/MG/ES (opcional para alguns provedores)")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    # 👇 novos
    p.add_argument("--preview", type=int, default=0, help="Imprime N linhas de amostra após gerar o PP")
    p.add_argument("--preview-fields", type=str, default="",
                   help="Lista de campos separados por vírgula p/ imprimir na amostra (default=auto: campos novos)")
    return p.parse_args()

def _load_rows(path: str):
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return doc.get("rows") or []

def main():
    a = parse_args()
    regiao = Regiao[a.regiao] if a.regiao else None

    # gera o JSON (ou dry-run)
    json_path = gerar_pp_json(a.provedor, a.ano, a.mes, regiao, dry_run=a.dry_run, debug=a.debug)
    status = "dry-run" if a.dry_run else "ok"
    print(json.dumps({"status": status, "json_target": json_path}, ensure_ascii=False))

    # preview opcional (só se não for dry-run e houver N > 0)
    if not a.dry_run and a.preview > 0:
        rows = _load_rows(json_path)
        if not rows:
            print("[INFO] Nenhuma linha para pré-visualizar.")
            return 0

        # quais campos imprimir?
        if a.preview_fields.strip():
            fields = [c.strip() for c in a.preview_fields.split(",") if c.strip()]
        else:
            # por padrão, mostre os novos campos + ID Nota/Item
            baseline = {
                "ID Nota","Item Codigo","Item Descricao",
                "CNPJ Emissor","Situacao NFe","Eh Devolucao","Possui CC-e","Em Contingencia",
                "Cancelada em","Prot Cancel","Justificativa Cancel"
            }
            fields = [c for c in COLUMNS if c in baseline] or list(baseline)

        print(f"[PREVIEW] {min(a.preview,len(rows))} de {len(rows)} | campos: {fields}")
        for i, r in enumerate(rows[:a.preview], 1):
            print(f"#{i}", {k: r.get(k, "") for k in fields})

    return 0

if __name__ == "__main__":
    sys.exit(main())
