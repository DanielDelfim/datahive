# app/utils/vendas/meli/service.py
from __future__ import annotations

from typing import Iterable, Dict, Any, List, Optional, Literal

from app.config.paths import APP_TIMEZONE, vendas_pp_json
from app.utils.core.io import ler_json
from app.utils.core.filtros import rows_today, today_bounds
from app.utils.anuncios.service import listar_anuncios_pp  # consumo cross-domínio (service→service)
from .aggregator import summarize, per_mlb, all_windows, per_gtin
import re

from .filters import (
    by_mlb as _by_mlb,
    by_sku as _by_sku,
    by_gtin as _by_gtin,
    by_order_id as _by_order_id,
)

Loja = Literal["sp", "mg"]

__all__ = [
    "listar_vendas",
    "get_resumos",
    "get_por_mlb",
    "get_resumo_hoje",
    "filtrar_por_mlb",
    "filtrar_por_sku",
    "filtrar_por_gtin",
    "filtrar_por_venda",
    "resumo_total",
    "listar_vendas_br", 
    "get_resumos_br", 
    "get_por_mlb_br",
    "get_por_gtin",
    "get_por_gtin_br",
]

# ----------------------------
# Helpers internos (sem I/O externo além de leitura PP)
# ----------------------------

def get_por_gtin(
    loja: Loja,
    windows: Iterable[int] = (7, 15, 30),
    *,
    mode: str = "ml",
    gtin_getter=None,
) -> Dict[str, Any]:
    rows = _load_pp(loja)
    gtin_getter = gtin_getter or _gtin_getter_factory(loja)
    return per_gtin(rows, windows=windows, mode=mode, gtin_getter=gtin_getter)

def get_por_gtin_br(
    windows: Iterable[int] = (7, 15, 30),
    *,
    mode: str = "ml",
    gtin_getter=None,
) -> Dict[str, Any]:
    rows = listar_vendas_br()
    gtin_getter = gtin_getter or _gtin_getter_factory(None)  # None => SP+MG
    return per_gtin(rows, windows=windows, mode=mode, gtin_getter=gtin_getter)



def listar_vendas_br() -> list[dict]:
    """
    Linha única de leitura para consolidar MG+SP.
    """
    rows_sp = _load_pp("sp")
    rows_mg = _load_pp("mg")
    # determinismo: concatena e não altera campos
    return [*rows_sp, *rows_mg]

def get_resumos_br(
    windows: Iterable[int] = (7, 15, 30),
    *,
    title_contains: str | None = None,
    mode: str = "ml",
    date_field: str = "date_approved",
) -> dict:
    """
    Resumo de janelas no total BR (MG+SP).
    """
    rows = listar_vendas_br()
    return {
        "loja": "br",
        "windows": list(windows),
        "filters": {"title_contains": title_contains},
        "mode": mode,
        "result": all_windows(
            rows,
            windows=windows,
            date_field=date_field,
            mlb=None, sku=None,
            title_contains=title_contains,
            mode=mode,
        ),
    }

def get_por_mlb_br(
    windows: Iterable[int] = (7, 15, 30),
    *,
    mode: str = "ml",
) -> dict:
    """
    Agregado por MLB somando MG+SP nas janelas informadas.
    """
    rows = listar_vendas_br()
    return per_mlb(rows, windows=windows, mode=mode)

def filtrar_por_venda(
    loja: Loja,
    order_id_or_ids,  # str|int|Iterable[str|int]
) -> List[Dict[str, Any]]:
    """
    Filtra linhas do PP por número de venda (order_id).
    Aceita único id ou coleção de ids.
    """
    return _by_order_id(_load_pp(loja), order_id_or_ids)

def _load_pp(loja: Loja) -> List[Dict[str, Any]]:
    """
    Lê o JSON PP (determinístico) de vendas para a loja (sp|mg).
    Não grava nada — service é somente leitura.
    """
    return ler_json(vendas_pp_json(loja))

_DIGITS = re.compile(r"\d+")

def _normalize_ean_like(s: str | None) -> str | None:
    if not s:
        return None
    # extrai apenas dígitos e aceita comprimentos comuns de GTIN/EAN
    digits = "".join(_DIGITS.findall(str(s)))
    return digits if len(digits) in (8, 12, 13, 14) else None

def _build_mlb_to_gtin_map(loja: Loja | None) -> dict[str, str]:
    """
    Monta um dicionário {mlb -> gtin} a partir do PP de anúncios.
    Se loja=None, agrega SP+MG.
    """
    mapa: dict[str, str] = {}
    # listar_anuncios_pp aceita Regiao opcional; None => SP+MG (ver service de anúncios)
    # retornos têm campos como mlb/sku/gtin/ean/barcode/titulo etc.
    anuncios = listar_anuncios_pp(None if loja is None else (  # type: ignore
        # o service de anúncios usa Regiao Enum internamente; aqui passamos string e ele resolve
        # (ele também injeta 'regiao' quando ausente)
        loja.upper()
    ))
    for a in anuncios:
        mlb = str(a.get("mlb") or a.get("id") or "").strip()
        if not mlb:
            continue
        gtin = a.get("gtin") or a.get("ean") or a.get("barcode")
        gtin = _normalize_ean_like(gtin)
        if gtin:
            mapa[mlb] = gtin
    return mapa

def _gtin_getter_factory(loja: Loja | None):
    """
    Retorna uma função getter(row) -> gtin normalizado.
    Estratégia:
      1) mapa MLB->GTIN vindo do PP de anúncios (fonte canônica do GTIN).
      2) fallback heurístico no seller_sku (se for claramente EAN/GTIN).
    """
    mlb_to_gtin = _build_mlb_to_gtin_map(loja)

    def _getter(row: dict) -> str | None:
        mlb = str(row.get("item_id") or "").strip()
        if mlb and mlb in mlb_to_gtin:
            return mlb_to_gtin[mlb]
        # fallback: tentar seller_sku do próprio PP de vendas
        sku = row.get("seller_sku")
        return _normalize_ean_like(sku)

    return _getter

# ----------------------------
# Fachada pública (contratos)
# ----------------------------

def listar_vendas(loja: Loja) -> List[Dict[str, Any]]:
    """
    Retorna as linhas normalizadas (PP) já consolidadas.
    """
    return _load_pp(loja)

def get_resumos(
    loja: Loja,
    windows: Iterable[int] = (7, 15, 30),
    *,
    mlb: Optional[str] = None,
    sku: Optional[str] = None,
    title_contains: Optional[str] = None,
    mode: str = "ml",
    date_field: str = "date_approved",
) -> Dict[str, Any]:
    """
    Resumo por janelas (ex.: 7/15/30 dias), com filtros opcionais.
    """
    rows = _load_pp(loja)
    return {
        "loja": loja,
        "windows": list(windows),
        "filters": {"mlb": mlb, "sku": sku, "title_contains": title_contains},
        "mode": mode,
        "result": all_windows(
            rows,
            windows=windows,
            date_field=date_field,
            mlb=mlb,
            sku=sku,
            title_contains=title_contains,
            mode=mode,
        ),
    }

def get_por_mlb(
    loja: Loja,
    windows: Iterable[int] = (7, 15, 30),
    *,
    mode: str = "ml",
) -> Dict[str, Any]:
    """
    Agregado por MLB (mantém compatibilidade com dashboards).
    """
    rows = _load_pp(loja)
    return per_mlb(rows, windows=windows, mode=mode)

def get_resumo_hoje(loja: Loja) -> Dict[str, Any]:
    """
    Resumo apenas de hoje (fronteiras segundo APP_TIMEZONE).
    """
    rows = _load_pp(loja)
    subset = rows_today(rows, date_field="date_approved", tz_name=APP_TIMEZONE)
    since, until = today_bounds(APP_TIMEZONE)
    return {
        "loja": loja,
        "date": since.split("T")[0],
        "window": {"from": since, "to": until, "timezone": APP_TIMEZONE},
        "result": summarize(subset),
    }

def filtrar_por_mlb(loja: Loja, mlb: str) -> List[Dict[str, Any]]:
    """
    Filtra linhas do PP por MLB.
    """
    return _by_mlb(_load_pp(loja), mlb)

def filtrar_por_sku(loja: Loja, sku: str) -> List[Dict[str, Any]]:
    """
    Filtra linhas do PP por SKU.
    """
    return _by_sku(_load_pp(loja), sku)

def filtrar_por_gtin(
    loja: Loja,
    gtin: str,
    *,
    getter=None,
) -> List[Dict[str, Any]]:
    """
    Filtra por GTIN/EAN. Se o PP não tiver GTIN no payload, passe um
    getter opcional (ex.: lambda r: mapa_mlb_gtin.get(r["item_id"])).
    """
    return _by_gtin(_load_pp(loja), gtin, getter=getter)

def resumo_total(loja: Loja) -> Dict[str, Any]:
    """
    Resumo total (sem janelas).
    """
    rows = _load_pp(loja)
    return summarize(rows)
