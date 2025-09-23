# scripts/reposicao/gerar_metricas.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

# Usamos apenas a camada de serviço (carregar/salvar + agregação por loja)
from app.utils.reposicao.service import (
    carregar_payload,        # lê RESULTS_DIR()/vendas_7_15_30.json por default
    salvar_json_atomic,      # escrita atômica (tmp + replace)
    estimativa_por_mlb,      # agrega métricas por loja sem escrever
)
from app.utils.reposicao.config import RESULTS_DIR
from app.utils.reposicao.service import escrever_reposicao_matriz

# ---- helpers CLI ----
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
        out.append(int(x))
    return out

def _bool_flag(s: str | None) -> bool:
    if s is None:
        return False
    return s.strip().lower() in {"1", "true", "t", "yes", "y", "on"}

# Campos de MÉTRICAS que podem ser atualizados sem mexer em enriquecimentos (ex.: gtin, _notes)
DEFAULT_METRIC_KEYS = {
    # volumes e médias
    "sold_7", "sold_15", "sold_30",
    "media_diaria_7", "media_diaria_15", "media_diaria_30",
    "media_diaria_preferida", "media_diaria_ponderada",
    # projeções / consumo / reposições / estoque projetado
    "expectativa_30d", "expectativa_60d",
    "consumo_previsto_7d",
    "reposicao_necessaria_7d", "estoque_projetado_7d",
    "reposicao_necessaria_30d", "reposicao_necessaria_60d",
    # cobertura
    "dias_cobertura",
    # bruto de vendas (útil para depurar)
    "raw",
}
ESTOQUE_KEY = "estoque"  # chave de estoque


def _merge_metrics_inplace(base_loja: dict, metrics_loja: dict, allow_update_estoque: bool) -> None:
    if not isinstance(base_loja, dict) or not isinstance(metrics_loja, dict):
        return
    # Decide o conjunto efetivo de chaves
    metric_keys = set(DEFAULT_METRIC_KEYS)
    if allow_update_estoque:
        metric_keys.add(ESTOQUE_KEY)

    for mlb, new_rec in metrics_loja.items():
        if mlb not in base_loja:
            continue
        old_rec = base_loja.get(mlb)
        if not isinstance(old_rec, dict) or not isinstance(new_rec, dict):
            continue
        for k in metric_keys:
            if k in new_rec:
                old_rec[k] = new_rec[k]

def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Modo padrão: recalcula e ATUALIZA apenas as MÉTRICAS no vendas_7_15_30.json "
            "(preservando gtin/_notes e, por padrão, o estoque).\n"
            "Modo matriz: use --reposicao-matriz para consolidar por GTIN (SP+MG) e gerar reposicao_matriz.json."
        )
    )
    ap.add_argument("--lojas", default=None, help="Ex.: SP,MG. Default: lojas presentes no arquivo.")
    ap.add_argument("--windows", default="7,15,30", help="Ex.: 7,15,30")
    ap.add_argument("--horizonte", type=int, default=7, help="Horizonte para consumo_previsto_7d. Default: 7")
    ap.add_argument("--infile", default=None, help="JSON base. Default: RESULTS_DIR()/vendas_7_15_30.json")
    ap.add_argument("--outfile", default=None, help="P/ modo padrão: sobrescreve o infile. P/ --reposicao-matriz: caminho do reposicao_matriz.json.")
    # --- NOVO: controle de atualização de estoque (default: False) ---
    ap.add_argument("--update-estoque", default=None, help="Se 'true', também atualiza o campo 'estoque'. Default: false.")
    # --- NOVO: modo por GTIN (SP+MG) gerando reposicao_matriz.json ---
    ap.add_argument("--reposicao-matriz", action="store_true",
                    help="Gera results/reposicao_matriz.json consolidando SP+MG por GTIN (usa escrever_reposicao_matriz).")
    ap.add_argument("--arredondar-multiplo", default=None,
                    help="Opcional: arredonda a reposição para múltiplos (ex.: 6).")
    args = ap.parse_args()

    infile = Path(args.infile) if args.infile else (RESULTS_DIR() / "vendas_7_15_30.json")

    # --- NOVO: modo matriz por GTIN ---
    if args.reposicao_matriz:
        # Usa writer dedicado do service; mantém paths centralizados.
        arred = float(args.arredondar_multiplo) if args.arredondar_multiplo else None
        out = escrever_reposicao_matriz(infile=infile, outfile=(Path(args.outfile) if args.outfile else None),
                                        arredondar_para_multiplo=arred)
        print(f"[OK] reposicao_matriz gerado: {out}")
        return

    # Modo antigo (padrão): atualizar métricas por loja/MLB no vendas_7_15_30.json
    payload = carregar_payload(infile)

    results = payload.get("results", {})
    if not isinstance(results, dict):
        print("[WARN] Payload sem 'results' válido; nada a atualizar.")
        return

    lojas = [k for k in results.keys()] if not args.lojas else [x.strip().lower() for x in args.lojas.split(",") if x.strip()]
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    allow_update_estoque = _bool_flag(args.update_estoque)  # False por padrão

    for loja in lojas:
        loja_key = str(loja).lower()
        if loja_key not in results or not isinstance(results[loja_key], dict):
            continue
        metrics_loja = estimativa_por_mlb(loja=loja_key, windows=windows, horizonte=args.horizonte)
        # >>> NÃO atualiza 'estoque' por padrão <<<
        _merge_metrics_inplace(results[loja_key], metrics_loja, allow_update_estoque=allow_update_estoque)

    payload["windows"] = windows
    payload["lojas"] = [str(loja).lower() for loja in lojas]

    dest = Path(args.outfile) if args.outfile else infile
    salvar_json_atomic(payload, dest)
    print(f"[OK] Métricas atualizadas em: {dest}")
    print(f"     Lojas: {', '.join(lojas)} | Janelas: {', '.join(map(str, windows))} | Horizonte: {args.horizonte}d")
    print(f"     Atualizou 'estoque'? {'Sim' if allow_update_estoque else 'Não'}")

if __name__ == "__main__":
    main()