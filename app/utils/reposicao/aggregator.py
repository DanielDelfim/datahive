# app/utils/reposicao/aggregator.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Iterable, Optional

from app.services.vendas_service import get_por_mlb
from app.utils.anuncios.service import obter_anuncio_por_mlb
from app.utils.reposicao.config import RESULTS_DIR

from app.utils.reposicao.metrics import (
    daily_rates_from_windows,
    pick_preferred_daily_rate,
    coverage_days,
    pacote_metricas_reposicao,
    daily_rate_ponderada_50_30_20,
    reposicoes_para_cobertura_30_60,
)

__all__ = [
    "agregar_por_mlb",
    "build_snapshot",
    "write_snapshot",
]


# --------------------------------
# utilidades internas
# --------------------------------

def _sold_in_window(rec: Dict[str, Any], window: int) -> float:
    """
    Extrai 'quantidade vendida' da estrutura por janela do serviço de vendas.
    Tenta várias chaves comuns de forma tolerante.
    """
    v = None
    windows = rec.get("windows") if isinstance(rec, dict) else None
    node = None
    if isinstance(windows, dict):
        node = windows.get(window, windows.get(str(window)))
    if node is None:
        node = rec.get(str(window), rec.get(f"qtd_{window}", None))
    if isinstance(node, dict):
        for k in ("qtd_vendida", "qty_total", "qtd", "total_qty"):
            if k in node and node[k] is not None:
                v = node[k]
                break
    elif node is not None:
        v = node
    try:
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0


def _build_mlb_record(
    loja: str,
    mlb: str,
    rec_vendas: Dict[str, Any],
    *,
    horizonte_reposicao_dias: int = 7,
    lote_multiplo: Optional[int | float] = None,
) -> Dict[str, Any]:
    """
    Monta o registro consolidado por MLB com métricas e estoque.
    - médias diárias por janela
    - taxa diária preferida (7 -> 15 -> 30)
    - taxa diária PONDERADA (50/30/20)
    - projeções 30/60d base ponderada
    - reposições necessárias 7d (horizonte), 30d e 60d
    - estoque projetado 7d (piso: <1 => 0) e dias de cobertura
    """
    sold_by_window = {
        7: _sold_in_window(rec_vendas, 7),
        15: _sold_in_window(rec_vendas, 15),
        30: _sold_in_window(rec_vendas, 30),
    }

    # médias diárias por janela
    rates = daily_rates_from_windows(sold_by_window)
    daily_pref = pick_preferred_daily_rate(rates)
    daily_rate_ponderada_50_30_20(rates)

    # Estoque via anúncios
    estoque_val = None
    try:
        anuncio = obter_anuncio_por_mlb(loja, mlb)
        if isinstance(anuncio, dict):
            estoque_val = anuncio.get("estoque", anuncio.get("available_quantity"))
    except Exception:
        pass

    # cobertura baseada na taxa preferida (mantemos como estava)
    cobertura = coverage_days(estoque_val, daily_pref)

    # pacote de horizonte (ex.: 7d) com base na taxa preferida (mantém compatibilidade)
    pack_h = pacote_metricas_reposicao(
        estoque_atual=estoque_val,
        daily_preferida=daily_pref,
        horizonte_reposicao_dias=horizonte_reposicao_dias,
        arredondar_para_multiplo=lote_multiplo,
    )

    # reposições para 30/60d (com base na taxa PONDERADA 50/30/20)
    pack_cov = reposicoes_para_cobertura_30_60(
        estoque_atual=estoque_val,
        rates=rates,
        arredondar_para_multiplo=lote_multiplo,
    )

    out = {
        "mlb": mlb,

        # vendas brutas por janela
        "sold_7": sold_by_window[7],
        "sold_15": sold_by_window[15],
        "sold_30": sold_by_window[30],

        # médias diárias por janela + preferida + ponderada (50/30/20)
        **rates,
        "media_diaria_preferida": daily_pref,
        "media_diaria_ponderada": pack_cov["media_diaria_ponderada"],

        # Projeções 30/60d: usamos a PONDERADA (como pedido)
        "expectativa_30d": pack_cov["consumo_previsto_30d_ponderado"],
        "expectativa_60d": pack_cov["consumo_previsto_60d_ponderado"],

        # Horizonte curto (ex.: 7d) — mantém compat com preferida
        "consumo_previsto_7d": pack_h["consumo_previsto_7d"],
        "reposicao_necessaria_7d": pack_h["reposicao_necessaria_7d"],
        "estoque_projetado_7d": pack_h["estoque_projetado_7d"],  # nunca negativo

        # Reposições para garantir cobertura de 30/60d (base taxa ponderada)
        "reposicao_necessaria_30d": pack_cov["reposicao_necessaria_30d"],
        "reposicao_necessaria_60d": pack_cov["reposicao_necessaria_60d"],

        # Estoque e cobertura (cobertura segue preferida)
        "estoque": estoque_val,
        "dias_cobertura": cobertura,

        # bruto do serviço de vendas (útil para depurar)
        "raw": rec_vendas,
    }
    return out


# --------------------------------
# API utilizada por service.py
# --------------------------------

def agregar_por_mlb(
    loja: str,
    windows: Iterable[int] = (7, 15, 30),
    *,
    horizonte_reposicao_dias: int = 7,
    lote_multiplo: Optional[int | float] = None,
) -> Dict[str, Any]:
    """
    Agrega métricas por MLB para UMA loja, incluindo:
      - médias diárias por janela,
      - taxa diária preferida e ponderada (50/30/20),
      - projeções 30/60d (ponderadas),
      - reposições 7d (horizonte), 30d e 60d,
      - estoque projetado 7d (não negativo; <1 => 0),
      - estoque e dias de cobertura (base preferida).
    """
    loja_norm = str(loja).lower()
    windows_list = [int(w) for w in windows]
    per_mlb_raw = get_por_mlb(loja=loja_norm, windows=windows_list, mode="ml")

    out: Dict[str, Any] = {}
    if isinstance(per_mlb_raw, dict):
        for mlb, rec in per_mlb_raw.items():
            try:
                out[mlb] = _build_mlb_record(
                    loja_norm,
                    mlb,
                    rec,
                    horizonte_reposicao_dias=horizonte_reposicao_dias,
                    lote_multiplo=lote_multiplo,
                )
            except Exception:
                out[mlb] = {"mlb": mlb, "erro": True, "raw": rec}
    return out


# --------------------------------
# snapshot multi-lojas
# --------------------------------

def build_snapshot(
    lojas: Iterable[str] = ("sp", "mg"),
    windows: Iterable[int] = (7, 15, 30),
    *,
    horizonte_reposicao_dias: int = 7,
    lote_multiplo: Optional[int | float] = None,
) -> Dict[str, Any]:
    """
    Orquestra:
      - agrega por loja via agregar_por_mlb
      - compõe payload final
    """
    lojas_norm = [loja_item.lower() for loja_item in lojas]
    payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lojas": lojas_norm,
        "windows": [int(w) for w in windows],
        "results": {},   # results[loja][mlb] = registro consolidado
    }

    for loja in lojas_norm:
        payload["results"][loja] = agregar_por_mlb(
            loja,
            windows,
            horizonte_reposicao_dias=horizonte_reposicao_dias,
            lote_multiplo=lote_multiplo,
        )

    return payload


def write_snapshot(
    payload: Dict[str, Any],
    dest: Path | None = None,
    overwrite: bool = True
) -> Path:
    """
    Salva o payload no JSON padrão (sobrescreve por padrão).
    """
    dest = dest or (RESULTS_DIR() / "vendas_7_15_30.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(dest)
    return dest
