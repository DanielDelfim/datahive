#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Exporta fatura_totais.json SEPARADO por região e, se aplicável, o consolidado em all/.

Saídas (exemplos):
  data/fiscal/meli/results/billing/2025/08/sp/fatura_totais.json
  data/fiscal/meli/results/billing/2025/08/mg/fatura_totais.json   (se mg tiver dados)
  data/fiscal/meli/results/billing/2025/08/all/fatura_totais.json  (se 2+ regiões tiverem dados)

Uso:
  python scripts/billing/excel/exportar_fatura_totais.py --ano 2025 --mes 8 --regiao sp --regiao mg --periodo_por ml --sink file --debug
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

from app.utils.billing.excel.service import consolidar_fatura_totais
from app.utils.billing.config import fatura_totais_json, excel_dir

def _emit_json(obj: Dict[str, Any], target: Path, sink: str = "file") -> None:
    """Emite JSON via result_sink.make_sink('json'|'stdout'), fallback atomic_write_json."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from app.utils.core.result_sink.service import make_sink
        if sink in ("file", "both"):
            make_sink("json", output_dir=target.parent, filename=target.name).emit(obj)
        if sink in ("stdout", "both"):
            make_sink("stdout").emit(obj)
    except Exception:
        from app.config.paths import atomic_write_json
        atomic_write_json(target, obj, do_backup=True)
        if sink in ("stdout", "both"):
            print(json.dumps(obj, ensure_ascii=False, indent=2))

def _listar_fontes(region_path: Path) -> Dict[str, List[str]]:
    """Lista os arquivos .xlsx/.zip presentes para diagnóstico."""
    d = {
        "xlsx": sorted([p.name for p in region_path.glob("*.xlsx")]),
        "zip":  sorted([p.name for p in region_path.glob("*.zip")]),
    }
    return d

def main():
    ap = argparse.ArgumentParser(description="Exporta fatura_totais.json por região + consolidado (se aplicável).")
    ap.add_argument("--market", default="meli")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", action="append", required=True, help="Pode repetir: --regiao sp --regiao mg")
    ap.add_argument("--periodo_por", choices=("ml", "mp", "full", "charges", "calendario"), default="ml")
    ap.add_argument("--sink", choices=("file", "stdout", "both"), default="file")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    # normaliza regiões para minúsculas (evita SP/MG vs sp/mg)
    regioes = [r.lower().strip() for r in args.regiao]

    if args.debug:
        print(f"[DBG] market={args.market} ano={args.ano} mes={args.mes} regioes={regioes} periodo_por={args.periodo_por}")

    regioes_processadas: List[str] = []
    regioes_com_linhas: List[str] = []  # regiões onde encontramos pelo menos 1 linha de cobrança
    diagnosticos: List[Tuple[str, Dict[str, List[str]]]] = []

    # 1) Exportar POR REGIÃO (sempre emite arquivo na pasta da região)
    for reg in regioes:
        # Onde o service vai procurar arquivos desta região
        dir_excel = excel_dir(args.market, args.ano, args.mes, reg)
        files_map = _listar_fontes(dir_excel)
        diagnosticos.append((reg, files_map))

        if args.debug:
            print(f"[DBG] {reg}: excel_dir = {dir_excel}")
            print(f"[DBG] {reg}: arquivos xlsx = {files_map['xlsx']}")
            print(f"[DBG] {reg}: arquivos zip  = {files_map['zip']}")

        res = consolidar_fatura_totais(
            market=args.market,
            ano=args.ano,
            mes=args.mes,
            regioes=[reg],                 # processa APENAS esta região
            periodo_por=args.periodo_por,
        )

        # Marca se houve alguma linha lida (independe do somatório final)
        cats = res.get("categorias") or {}
        houve_linha = bool(cats) and any(abs(float(v or 0.0)) > 0 for v in cats.values())
        if houve_linha:
            regioes_com_linhas.append(reg)
        regioes_processadas.append(reg)  # geramos arquivo para a região de qualquer forma

        # Enriquecer com diagnóstico de fontes
        res.setdefault("diagnostico", {})
        res["diagnostico"]["arquivos_encontrados"] = files_map
        res["diagnostico"]["regioes_processadas"] = [reg]

        out_reg = fatura_totais_json(args.market, args.ano, args.mes, reg)
        _emit_json(res, out_reg, args.sink)

        if args.debug:
            print(f"[OK] Região {reg}: gerado {out_reg} (total_cobrancas={res.get('totais',{}).get('total_cobrancas')})")

    # 2) Exportar CONSOLIDADO (all/) somente se 2+ regiões tiveram linhas lidas
    if len(regioes_com_linhas) >= 2:
        if args.debug:
            print(f"[DBG] Consolidando all/ com regioes_com_linhas={regioes_com_linhas}")
        res_all = consolidar_fatura_totais(
            market=args.market,
            ano=args.ano,
            mes=args.mes,
            regioes=regioes_com_linhas,    # usa só as que realmente tiveram linhas
            periodo_por=args.periodo_por,
        )
        # também anexa diagnóstico das fontes
        res_all.setdefault("diagnostico", {})
        res_all["diagnostico"]["regioes_processadas"] = regioes_com_linhas
        res_all["diagnostico"]["arquivos_encontrados_por_regiao"] = {reg: fm for reg, fm in diagnosticos}

        out_all = fatura_totais_json(args.market, args.ano, args.mes, "all")
        _emit_json(res_all, out_all, args.sink)

        if args.debug:
            print(f"[OK] Consolidado all/: gerado {out_all} (total_cobrancas={res_all.get('totais',{}).get('total_cobrancas')})")
    else:
        if args.debug:
            print(f"[INFO] Consolidado all/ não gerado (regiões com linhas: {regioes_com_linhas})")

if __name__ == "__main__":
    main()
