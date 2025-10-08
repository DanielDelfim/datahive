# scripts/vendas/gerar_resumos.py
from __future__ import annotations
import sys
from typing import Dict, Iterable, Tuple, Optional, Any
import json
import argparse

from app.config.paths import vendas_resumo_json, vendas_por_mlb_json
from app.utils.core.io import atomic_write_json
from app.services.vendas_service import get_resumos, get_por_mlb

from app.config.paths import anuncios_pp_json, Marketplace, Regiao

import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

USO = ("Uso: python -m scripts.vendas.gerar_resumos [sp|mg] "
       "[--windows 7,15,30] [--mlb MLB...] [--sku SKU...] [--title \"texto\"]")

def _regiao_enum(loja: str) -> Regiao:
    return Regiao.SP if loja.lower() == "sp" else Regiao.MG

def _carregar_estoque_por_mlb(loja: str) -> Dict[str, float]:
    """
    Lê o PP de anúncios e retorna {mlb: estoque_total}.
    PP deriva do RAW que contém 'available_quantity' (estoque).  :contentReference[oaicite:10]{index=10}
    """
    path = anuncios_pp_json(Marketplace.MELI, _regiao_enum(loja))  # :contentReference[oaicite:11]{index=11}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    data = payload.get("data") or []
    out: Dict[str, float] = {}
    for rec in data:
        mlb = str(rec.get("mlb") or "").strip()
        if not mlb:
            continue
        est = rec.get("estoque")
        try:
            out[mlb] = float(est) if est is not None else 0.0
        except Exception:
            out[mlb] = 0.0
    return out

def _dig_number(obj) -> float:
    """Extrai número de estruturas variadas (int/float ou dicts aninhados)."""
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        # tentativas comuns
        for k in ("qtd_vendida", "qtd", "sum", "total", "value"):
            v = obj.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        # janelas como chaves
        for k, v in obj.items():
            if str(k).isdigit():
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, dict):
                    n = _dig_number(v)
                    if n:
                        return n
    return 0.0

def _qtd_30d_por_mlb(por_mlb_obj: Dict[str, Any]) -> Dict[str, float]:
    """
    Normaliza o retorno de get_por_mlb(...) em {mlb: qtd_30d}.
    Considera formato {"result": {...}} ou direto {...}, e nós 'per_mlb' se existirem.  :contentReference[oaicite:12]{index=12}
    """
    base = por_mlb_obj.get("result", por_mlb_obj) if isinstance(por_mlb_obj, dict) else {}
    if not isinstance(base, dict):
        return {}
    if "per_mlb" in base and isinstance(base["per_mlb"], dict):
        base = base["per_mlb"]

    out: Dict[str, float] = {}
    for mlb, val in base.items():
        qty30 = 0.0
        if isinstance(val, dict):
            # preferir janela explícita 30/“30”
            if 30 in val:
                qty30 = _dig_number(val[30])
            elif "30" in val:
                qty30 = _dig_number(val["30"])
            else:
                qty30 = _dig_number(val)
        else:
            qty30 = _dig_number(val)
        out[str(mlb)] = float(qty30 or 0.0)
    return out

def _injetar_reposicao(por_mlb_obj: Dict[str, Any], estoque_map: Dict[str, float]) -> Dict[str, Any]:
    """
    Calcula e injeta bloco 'reposicao' no dicionário por_mlb (não remove chaves existentes).
    Campos: estoque_total, md_30d, sug_30d, sug_60d.
    """
    qtd30 = _qtd_30d_por_mlb(por_mlb_obj)
    reposicao: Dict[str, Dict[str, float | None]] = {}
    for mlb, sold_30 in qtd30.items():
        est = float(estoque_map.get(mlb, 0.0))
        md_30 = float(sold_30) / 30.0 if sold_30 > 0 else 0.0
        sug_30 = max(0.0, 30.0 * md_30 - est)
        sug_60 = max(0.0, 60.0 * md_30 - est)
        reposicao[mlb] = {
            "estoque_total": est,
            "md_30d": md_30,
            "sug_30d": sug_30,
            "sug_60d": sug_60,
        }
    # injeta no objeto final (lado a lado com 'result' etc.)
    por_mlb_obj = dict(por_mlb_obj)  # cópia rasa
    por_mlb_obj["reposicao"] = reposicao
    return por_mlb_obj

def _parse_windows(arg: str | None) -> Iterable[int]:
    if not arg:
        return (7, 15, 30)
    try:
        return tuple(int(x.strip()) for x in arg.split(",") if x.strip())
    except Exception:
        return (7, 15, 30)

def _parse_args(argv: list[str]) -> Tuple[str, Iterable[int], Optional[str], Optional[str], Optional[str]]:
    if len(argv) < 2:
        raise SystemExit(USO)
    loja = argv[1].strip().lower()
    if loja not in ("sp", "mg"):
        raise SystemExit(USO)

    windows = (7, 15, 30)
    mlb = sku = title = None
    if "--windows" in argv:
        i = argv.index("--windows")
        if i + 1 < len(argv):
            windows = _parse_windows(argv[i + 1])
    if "--mlb" in argv:
        i = argv.index("--mlb")
        if i + 1 < len(argv):
            mlb = argv[i + 1].strip()
    if "--sku" in argv:
        i = argv.index("--sku")
        if i + 1 < len(argv):
            sku = argv[i + 1].strip()
    if "--title" in argv:
        i = argv.index("--title")
        if i + 1 < len(argv):
            title = argv[i + 1].strip()
    return loja, windows, mlb, sku, title

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("loja", choices=("sp", "mg"))
    ap.add_argument("--materializar", action="store_true",
                    help="Se presente, grava JSONs auxiliares; caso contrário, só imprime/loga.")
    args = ap.parse_args(argv[1:])

    # calcula em memória usando o service
    por_mlb = get_por_mlb(args.loja, windows=(7, 15, 30))
    resumo_windows = get_resumos(args.loja, windows=(7, 15, 30))

    if args.materializar:
        # grava SOMENTE se flag for passada
        out_por_mlb = vendas_por_mlb_json(args.loja)      # caminho helper do seu config/paths
        out_resumo  = vendas_resumo_json(args.loja)       # idem (se quiser manter um deles)
        atomic_write_json(out_por_mlb, por_mlb, do_backup=True)
        atomic_write_json(out_resumo, resumo_windows, do_backup=True)
        print(f"[OK] JSONs auxiliares materializados: {out_por_mlb} | {out_resumo}")
    else:
        # padrão: sem escrita
        print(f"[OK] Resumos calculados em memória (loja={args.loja}); nada gravado.")
        # opcional: logar 3 números úteis
        total_7  = resumo_windows["result"]["7"]["qty_total"]
        total_15 = resumo_windows["result"]["15"]["qty_total"]
        total_30 = resumo_windows["result"]["30"]["qty_total"]
        print(f"Totais qty (7/15/30): {total_7}/{total_15}/{total_30}")

if __name__ == "__main__":
    import sys
    main(sys.argv)
