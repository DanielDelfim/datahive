# app/utils/reposicao/service.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Iterable, Optional, List
import csv

from app.utils.reposicao.config import RESULTS_DIR
from app.utils.reposicao.aggregator import (
    agregar_por_mlb,
    build_snapshot,
    write_snapshot,
    consolidar_vendas_por_gtin,
)

from app.utils.reposicao.metrics import (
    pick_preferred_daily_rate, blended_daily_rate,
    projections_from_daily, consumo_previsto, reposicao_necessaria,
)
from app.utils.estoques_matriz_filial.service import get_estoque_pp_mg
from app.utils.reposicao.filters import filtrar_payload, flatten_filtrado, only_digits

__all__ = [
    # compat já esperada pelo seu __init__.py
    "estimativa_por_mlb",
    "escrever_latest",
    "escrever_datado",
    # utilidades novas
    "carregar_payload",
    "salvar_json_atomic",
    "exportar_filtrado_json",
    "exportar_filtrado_csv",
]


# -------------------------------------------------
# utilidades de I/O
# -------------------------------------------------

def carregar_payload(path: Path | str | None = None) -> Dict[str, Any]:
    """
    Carrega o JSON principal de reposição (default: RESULTS_DIR()/vendas_7_15_30.json).
    """
    p = Path(path) if path else (RESULTS_DIR() / "vendas_7_15_30.json")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def salvar_json_atomic(payload: Dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(dest)
    return dest


# -------------------------------------------------
# API principal / compatibilidade
# -------------------------------------------------
def estimativa_por_gtin_matriz(
    infile: Path | str | None = None,
    *,
    arredondar_para_multiplo: float | int | None = None
) -> Dict[str, Any]:
    """
    Consolida SP+MG por GTIN, injeta estoque da MATRIZ (PP MG) e calcula
    projeções e reposições (30d/60d) com base na taxa PONDERADA 50/30/20.
    """
    payload = carregar_payload(infile or (RESULTS_DIR() / "vendas_7_15_30.json"))  # :contentReference[oaicite:29]{index=29}
    por_gtin = consolidar_vendas_por_gtin(payload)

    # estoque PP matriz (lista normalizada) -> mapa por EAN
    estoque_rows = get_estoque_pp_mg()  # List[dict] com chaves ean/quantidade  # List[dict] com chaves ean/quantidade :contentReference[oaicite:30]{index=30}
    estoque_por_ean: Dict[str, float] = {}
    for r in estoque_rows:
        ean = only_digits(str(r.get("ean", "")).strip())
        if not ean:
            continue
        try:
            q = float(r.get("quantidade") or 0)
        except Exception:
            q = 0.0
        estoque_por_ean[ean] = estoque_por_ean.get(ean, 0.0) + q

    out: Dict[str, Any] = {}
    for gtin_key, v in por_gtin.items():
        gtin = only_digits(gtin_key)
        estoque = float(estoque_por_ean.get(gtin, 0.0))
        daily_pref  = pick_preferred_daily_rate(v)
        daily_blend = blended_daily_rate(v)  # 50/30/20
        proj        = projections_from_daily(daily_blend)

        # dentro de estimativa_por_gtin_matriz(...), no loop que monta out[gtin]
        out[gtin] = {
            "gtin": gtin,
            "title": v.get("title", ""),   # <<< garantir inclusão
            "sold_7": v["sold_7"], "sold_15": v["sold_15"], "sold_30": v["sold_30"],
            "media_diaria_7": v["media_diaria_7"], "media_diaria_15": v["media_diaria_15"], "media_diaria_30": v["media_diaria_30"],
            "media_diaria_preferida": daily_pref,
            "media_diaria_ponderada": daily_blend,
            "estoque_matriz": estoque,
            "consumo_previsto_30d": consumo_previsto(daily_blend, 30),
            "consumo_previsto_60d": consumo_previsto(daily_blend, 60),
            "reposicao_necessaria_30d": reposicao_necessaria(estoque, daily_blend, 30, arredondar_para_multiplo),
            "reposicao_necessaria_60d": reposicao_necessaria(estoque, daily_blend, 60, arredondar_para_multiplo),
            **proj,
        }


    # GTINs que só existem no estoque
    for gtin, estoque in estoque_por_ean.items():
        if gtin not in out:
            out[gtin] = {
                "gtin": gtin,
                "sold_7": 0.0, "sold_15": 0.0, "sold_30": 0.0,
                "media_diaria_7": 0.0, "media_diaria_15": 0.0, "media_diaria_30": 0.0,
                "media_diaria_preferida": 0.0, "media_diaria_ponderada": 0.0,
                "estoque_matriz": float(estoque),
                "consumo_previsto_30d": 0.0, "consumo_previsto_60d": 0.0,
                "reposicao_necessaria_30d": 0.0, "reposicao_necessaria_60d": 0.0,
                "expectativa_30d": 0.0, "expectativa_60d": 0.0,
            }

    return {
        "fonte_vendas": str(RESULTS_DIR() / "vendas_7_15_30.json"),
        "fonte_estoque_matriz": "pp:estoque_mg.json",
        "items": out,
    }


def estimativa_por_mlb(
    loja: str,
    windows: Iterable[int] = (7, 15, 30),
    *,
    horizonte: int = 7,
    # lote_multiplo: por enquanto desabilitado (quando quiser ativar, repasse ao aggregator)
) -> Dict[str, Any]:
    """
    Agrega métricas por MLB para UMA loja (compatível com chamadas antigas):
      - médias diárias, projeções 30/60d,
      - consumo previsto no 'horizonte' (default 7d),
      - reposição necessária e estoque projetado (com piso não-negativo),
      - estoque e dias de cobertura.
    """
    return agregar_por_mlb(
        loja=loja,
        windows=windows,
        horizonte_reposicao_dias=horizonte,
        # lote_multiplo=None,
    )


def escrever_latest(
    lojas: Iterable[str] = ("sp", "mg"),
    windows: Iterable[int] = (7, 15, 30),
    *,
    horizonte: int = 7,
    outfile: Path | None = None,
) -> Path:
    """
    Gera um snapshot “latest” (sobrescreve o arquivo padrão) com o horizonte informado.
    """
    payload = build_snapshot(
        lojas=lojas,
        windows=windows,
        horizonte_reposicao_dias=horizonte,
        # lote_multiplo=None,
    )
    dest = outfile or (RESULTS_DIR() / "vendas_7_15_30.json")
    return write_snapshot(payload, dest=dest)


def escrever_datado(
    lojas: Iterable[str] = ("sp", "mg"),
    windows: Iterable[int] = (7, 15, 30),
    *,
    horizonte: int = 7,
    prefixo: str = "vendas_7_15_30",
) -> Path:
    """
    Gera um arquivo datado (não sobrescreve o latest).
    Ex.: vendas_7_15_30__2025-09-19T16-02-33Z.json
    """
    payload = build_snapshot(
        lojas=lojas,
        windows=windows,
        horizonte_reposicao_dias=horizonte,
        # lote_multiplo=None,
    )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = RESULTS_DIR() / f"{prefixo}__{ts}.json"
    return write_snapshot(payload, dest=dest)

def escrever_reposicao_matriz(
    infile: Path | str | None = None,
    outfile: Path | None = None,
    *,
    arredondar_para_multiplo: float | int | None = None,
) -> Path:
    """
    Gera e escreve C:\\Apps\\Datahive\\data\\marketplaces\\meli\\reposicao\\results\\reposicao_matriz.json
    (ou caminho custom via outfile).
    """
    payload = estimativa_por_gtin_matriz(infile=infile, arredondar_para_multiplo=arredondar_para_multiplo)
    dest = outfile or (RESULTS_DIR() / "reposicao_matriz.json")  # novo arquivo pedido
    return salvar_json_atomic(payload, dest)  # já existente na service.py :contentReference[oaicite:31]{index=31}

# -------------------------------------------------
# Exportações (recortes por loja/MLB)
# -------------------------------------------------

def exportar_filtrado_json(
    lojas: Optional[Iterable[str]] = None,
    mlbs: Optional[Iterable[str]] = None,
    infile: Path | str | Dict[str, Any] | None = None,
    outfile: Path | str | None = None,
) -> Path:
    src = infile if infile is not None else (RESULTS_DIR() / "vendas_7_15_30.json")
    filtered = filtrar_payload(src, lojas=lojas, mlbs=mlbs)

    if outfile is None:
        suffix_lojas = "-".join([str(loja).lower() for loja in lojas] if lojas else ["all"])
        suffix_mlbs = "-".join(mlbs) if mlbs else "all"
        outfile = (RESULTS_DIR() / f"vendas_7_15_30__{suffix_lojas}__{suffix_mlbs}.json")

    return salvar_json_atomic(filtered, Path(outfile))


def _desired_field_order() -> List[str]:
    """
    Ordem estável para o CSV (inclui novas colunas).
    """
    return [
        "loja", "mlb",
        "sold_7", "sold_15", "sold_30",
        "media_diaria_7", "media_diaria_15", "media_diaria_30",
        "media_diaria_preferida", "media_diaria_ponderada",
        "expectativa_30d", "expectativa_60d",
        "consumo_previsto_7d",
        "reposicao_necessaria_7d", "reposicao_necessaria_30d", "reposicao_necessaria_60d",
        "estoque_projetado_7d", "estoque", "dias_cobertura",
    ]

def exportar_filtrado_csv(
    lojas: Optional[Iterable[str]] = None,
    mlbs: Optional[Iterable[str]] = None,
    infile: Path | str | Dict[str, Any] | None = None,
    outfile: Path | str | None = None,
) -> Path:
    src = infile if infile is not None else (RESULTS_DIR() / "vendas_7_15_30.json")
    rows = flatten_filtrado(src, lojas=lojas, mlbs=mlbs)

    if outfile is None:
        suffix_lojas = "-".join([str(loja).lower() for loja in lojas] if lojas else ["all"])
        suffix_mlbs = "-".join(mlbs) if mlbs else "all"
        outfile = (RESULTS_DIR() / f"vendas_7_15_30__{suffix_lojas}__{suffix_mlbs}.csv")

    out_path = Path(outfile)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ordem estável + inclusão de chaves extras se aparecerem
    desired = _desired_field_order()
    extras = set()
    for r in rows:
        extras.update(set(r.keys()) - set(desired))
    fieldnames = desired + [c for c in sorted(extras) if c not in desired]

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_path)
    return out_path
