# app/utils/core/filtros.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Iterable, List, Dict, Any, Tuple, Optional

from app.config.paths import APP_TIMEZONE

import pandas as pd

__all__ = [
    "now_iso",
    "today_bounds",
    "day_bounds",
    "calendar_window_bounds",
    "ml_window_bounds",
    "rows_between",
    "rows_in_calendar_window",
    "rows_in_ml_window",
    "rows_today",
]

# ---------- PARSE ISO ----------
def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Converte ISO (aceita Z e milisseg.) em datetime tz-aware; assume UTC se naive."""
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.fromisoformat(s.split(".")[0] + s[-6:])
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

# ---------- BOUNDS ----------
def dentro_janela(df: pd.DataFrame, col_data: str, inicio: str, fim: str) -> pd.DataFrame:
    """Filtra linhas cuja data (col_data) intersecta [inicio, fim] (YYYY-MM-DD)."""
    if col_data not in df.columns:
        return df.iloc[0:0].copy()
    s = pd.to_datetime(df[col_data], errors="coerce", dayfirst=True)
    # garantir timezone-naive
    try:
        s = s.dt.tz_localize(None)
    except Exception:
        pass
    ini = pd.to_datetime(inicio).date()
    end = pd.to_datetime(fim).date()
    # mantemos linhas com data dentro do intervalo
    m = (s.dt.date >= ini) & (s.dt.date <= end)
    return df.loc[m].copy()

def dentro_competencia(df: pd.DataFrame, col_data: str, ano: int, mes: int) -> pd.DataFrame:
    if col_data not in df.columns:
        return df.iloc[0:0].copy()
    # 1) Parse robusto: tenta com dayfirst=True e False e escolhe o que tiver mais válidos
    s_br = pd.to_datetime(df[col_data], errors="coerce", dayfirst=True)
    s_us = pd.to_datetime(df[col_data], errors="coerce", dayfirst=False)
    # escolhe a série com menos NaT (mais parseada)
    use_br = s_br.notna().sum() >= s_us.notna().sum()
    s = s_br if use_br else s_us
    # 2) Remover timezone (se presente)
    try:
        s = s.dt.tz_localize(None)
    except Exception:
        pass
    # 3) Filtrar competência alvo
    m = (s.dt.year == ano) & (s.dt.month == mes)
    return df.loc[m].copy()

def now_iso(tz_name: str = APP_TIMEZONE) -> str:
    tz = ZoneInfo(tz_name)
    return datetime.now(tz).isoformat(timespec="seconds")

def today_bounds(tz_name: str = APP_TIMEZONE) -> Tuple[str, str]:
    """Dia de HOJE fechado [00:00 .. 23:59:59]."""
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

def day_bounds(date_str: str, tz_name: str = APP_TIMEZONE) -> Tuple[str, str]:
    """Dia fechado para YYYY-MM-DD."""
    tz = ZoneInfo(tz_name)
    y, m, d = (int(x) for x in date_str.split("-"))
    start = datetime(y, m, d, 0, 0, 0, tzinfo=tz)
    end   = datetime(y, m, d, 23, 59, 59, tzinfo=tz)
    return (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

def calendar_window_bounds(days: int, tz_name: str = APP_TIMEZONE, *, include_today: bool = True) -> Tuple[str, str]:
    """
    Janela alinhada a dias cheios:
      include_today=True  -> fim = HOJE 23:59:59; início = hoje-(days-1) 00:00
      include_today=False -> fim = ONTEM 23:59:59; início = ontem-(days-1) 00:00
    """
    if days < 1:
        days = 1
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    end_date = now.date() if include_today else (now.date() - timedelta(days=1))
    start_date = end_date - timedelta(days=days - 1)
    start = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=tz)
    end   = datetime(end_date.year,   end_date.month,   end_date.day,   23, 59, 59, tzinfo=tz)
    return (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

def ml_window_bounds(days: int, tz_name: str = APP_TIMEZONE) -> Tuple[str, str]:
    """
    MODO ML: janela HOJE−days .. HOJE (ambos INCLUSIVOS em dias cheios).
    Ex.: days=7 => início = hoje-7 (00:00), fim = hoje (23:59:59).
    """
    if days < 0:
        days = 0
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    end_date = now.date()
    start_date = end_date - timedelta(days=days)
    start = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=tz)
    end   = datetime(end_date.year,   end_date.month,   end_date.day,   23, 59, 59, tzinfo=tz)
    return (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

# ---------- FILTERS ----------

def rows_between(rows: Iterable[Dict[str, Any]],
                 since_iso: str, until_iso: str,
                 date_field: str = "date_approved") -> List[Dict[str, Any]]:
    """Filtro inclusivo no intervalo [since..until]."""
    dt_from = _parse_iso(since_iso)
    dt_to   = _parse_iso(until_iso)
    out: List[Dict[str, Any]] = []
    for r in rows:
        dt = _parse_iso(r.get(date_field))
        if dt and dt_from <= dt <= dt_to:
            out.append(r)
    return out

def rows_in_calendar_window(rows: Iterable[Dict[str, Any]],
                            days: int,
                            date_field: str = "date_approved",
                            tz_name: str = APP_TIMEZONE,
                            *, include_today: bool = True) -> List[Dict[str, Any]]:
    since_iso, until_iso = calendar_window_bounds(days, tz_name, include_today=include_today)
    return rows_between(rows, since_iso, until_iso, date_field=date_field)

def rows_in_ml_window(rows: Iterable[Dict[str, Any]],
                      days: int,
                      date_field: str = "date_approved",
                      tz_name: str = APP_TIMEZONE) -> List[Dict[str, Any]]:
    since_iso, until_iso = ml_window_bounds(days, tz_name)
    return rows_between(rows, since_iso, until_iso, date_field=date_field)

def rows_today(rows: Iterable[Dict[str, Any]],
               date_field: str = "date_approved",
               tz_name: str = APP_TIMEZONE) -> List[Dict[str, Any]]:
    since_iso, until_iso = today_bounds(tz_name)
    return rows_between(rows, since_iso, until_iso, date_field=date_field)
