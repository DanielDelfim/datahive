# app/services/vendas_service.py
from __future__ import annotations
from typing import Iterable, Dict, Any

from app.config.paths import APP_TIMEZONE, vendas_pp_json
from app.utils.core.io import ler_json
from app.utils.core.filtros import rows_today, today_bounds
from app.utils.vendas.aggregator import summarize, per_mlb, all_windows

def _load_pp(loja: str) -> list[dict]:
    return ler_json(vendas_pp_json(loja))

def get_resumos(loja: str,
                windows: Iterable[int] = (7, 15, 30),
                *, mlb: str | None = None,
                sku: str | None = None,
                title_contains: str | None = None,
                mode: str = "ml",             # <- padrão ML
                date_field: str = "date_approved") -> Dict[str, Any]:
    rows = _load_pp(loja)
    return {
        "loja": loja.lower(),
        "windows": list(windows),
        "filters": {"mlb": mlb, "sku": sku, "title_contains": title_contains},
        "mode": mode,
        "result": all_windows(
            rows, windows=windows, date_field=date_field,
            mlb=mlb, sku=sku, title_contains=title_contains,
            mode=mode
        ),
    }

def get_por_mlb(loja: str,
                windows: Iterable[int] = (7, 15, 30),
                *, mode: str = "ml") -> Dict[str, Any]:
    rows = _load_pp(loja)
    return per_mlb(rows, windows=windows, mode=mode)

def get_resumo_hoje(loja: str) -> Dict[str, Any]:
    rows = _load_pp(loja)
    subset = rows_today(rows, date_field="date_approved", tz_name=APP_TIMEZONE)
    since, until = today_bounds(APP_TIMEZONE)
    return {
        "loja": loja.lower(),
        "date": since.split("T")[0],
        "window": {"from": since, "to": until, "timezone": APP_TIMEZONE},
        "result": summarize(subset),
    }
