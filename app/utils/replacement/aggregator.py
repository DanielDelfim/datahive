#C:\Apps\Datahive\app\utils\replacement\aggregator.py
from __future__ import annotations
from typing import Any, Iterable, Optional, Literal
from collections import defaultdict
from collections.abc import Mapping, Sequence

from app.config.paths import Regiao
from app.utils.replacement.config import DEFAULT_PARAMS
from app.utils.replacement.metrics import estimate_30_60, estoque_pos_delay

# VENDAS: SP/MG por MLB; BR por GTIN
from app.utils.vendas.meli.service import get_por_mlb, get_por_gtin_br

# ANÚNCIOS: estoque por MLB/GTIN
from app.utils.anuncios.service import listar_anuncios_pp

Loja = Literal["sp", "mg"]

# ----------------- Helpers: unwrap/normalize -----------------
def _unwrap_result(resp: Any) -> dict[str, dict]:
    # {"result": {...}}
    if isinstance(resp, Mapping) and "result" in resp and isinstance(resp["result"], Mapping):
        return dict(resp["result"])
    # {"per_gtin": {...}} / {"per_mlb": {...}} / {"data": {...}} / {"payload": {...}}
    for k in ("per_gtin", "per_mlb", "data", "payload"):
        if isinstance(resp, Mapping) and k in resp and isinstance(resp[k], Mapping):
            return dict(resp[k])
    # mapa direto {chave: row}
    if isinstance(resp, Mapping):
        return {str(k): (dict(v) if isinstance(v, Mapping) else v) for k, v in resp.items()}
    # lista de linhas
    if isinstance(resp, Sequence) and not isinstance(resp, (str, bytes)):
        out: dict[str, dict] = {}
        for item in resp:
            if not isinstance(item, Mapping):
                continue
            key = (item.get("mlb") or item.get("gtin") or item.get("ean")
                   or item.get("barcode") or item.get("key") or "").strip()
            if key:
                out[key] = dict(item)
        if out:
            return out
    raise ValueError(f"Formato inesperado do service de vendas (amostra: {str(resp)[:300]})")

def _pick_window_from_any(row_like: Mapping, win: int | str) -> float:
    """Retorna qty na janela 7/15/30, aceitando formatos aninhados e aliases."""
    win = str(win)
    aliases = {
        "7":  ["7","sold_7","qty_7","qtd_7","w7","7d","last_7","last7","d7"],
        "15": ["15","sold_15","qty_15","qtd_15","w15","15d","last_15","last15","d15"],
        "30": ["30","sold_30","qty_30","qtd_30","w30","30d","last_30","last30","d30"],
    }[win]

    # plano
    for k in aliases:
        if k in row_like and row_like[k] is not None and not isinstance(row_like[k], Mapping):
            try:
                return float(row_like[k])
            except Exception:
                pass

    # aninhado
    for nest in ("windows","qty","qtd","sold","sum","totals","values"):
        v = row_like.get(nest)
        if not isinstance(v, Mapping):
            continue
        for k in aliases:
            if k in v and isinstance(v[k], Mapping):
                sub = v[k]
                for leaf in ("qty_total","items_count","orders_count"):
                    if leaf in sub and sub[leaf] is not None:
                        try:
                            return float(sub[leaf])
                        except Exception:
                            pass
            elif k in v and v[k] is not None and not isinstance(v[k], Mapping):
                try:
                    return float(v[k])
                except Exception:
                    pass

        # alguns retornos usam "w7"/"w15"/"w30"
        alt = f"w{win}"
        if alt in v and isinstance(v[alt], Mapping):
            sub = v[alt]
            for leaf in ("qty_total","items_count","orders_count"):
                if leaf in sub and sub[leaf] is not None:
                    try:
                        return float(sub[leaf])
                    except Exception:
                        pass
    return 0.0

def _normalize_row(row: Mapping) -> dict:
    s7  = _pick_window_from_any(row, 7)
    s15 = _pick_window_from_any(row, 15)
    s30 = _pick_window_from_any(row, 30)
    return {"sold_7": s7, "sold_15": s15, "sold_30": s30}

# ----------------- Estoque (anúncios) -----------------
def _estoque_por_mlb_regiao(loja: Loja) -> dict[str, float]:
    reg = Regiao.SP if loja == "sp" else Regiao.MG
    acc: dict[str, float] = defaultdict(float)
    for ad in listar_anuncios_pp(regiao=reg):
        mlb = (ad.get("mlb") or ad.get("id") or "").strip()
        if not mlb:
            continue
        raw = ad.get("estoque", ad.get("available_quantity", 0))
        try:
            acc[mlb] += float(raw or 0)
        except Exception:
            pass
    return dict(acc)

def _estoque_por_gtin_regiao(loja: Loja) -> dict[str, float]:
    reg = Regiao.SP if loja == "sp" else Regiao.MG
    acc: dict[str, float] = defaultdict(float)
    for ad in listar_anuncios_pp(regiao=reg):
        gtin = (ad.get("gtin") or ad.get("ean") or ad.get("barcode") or "").strip()
        if not gtin:
            continue
        raw = ad.get("estoque", ad.get("available_quantity", 0))
        try:
            acc[gtin] += float(raw or 0)
        except Exception:
            pass
    return dict(acc)

def _estoque_por_gtin_br() -> dict[str, float]:
    acc: dict[str, float] = defaultdict(float)
    for loja in ("sp", "mg"):
        for k, v in _estoque_por_gtin_regiao(loja).items():
            acc[k] += float(v or 0)
    return dict(acc)

# ----------------- MLB→GTIN (para enriquecer detalhe) -----------------
def _map_mlb_to_gtin(loja: Loja) -> dict[str, str]:
    reg = Regiao.SP if loja == "sp" else Regiao.MG
    m: dict[str, str] = {}
    for ad in listar_anuncios_pp(regiao=reg):
        mlb = (ad.get("mlb") or ad.get("id") or "").strip()
        gtin = (ad.get("gtin") or ad.get("ean") or ad.get("barcode") or "").strip()
        if mlb and gtin:
            m[mlb] = gtin
    return m

# ----------------- Projeções: SP/MG por MLB -----------------
def _map_estimativas_mlb(por_mlb: dict[str, dict], *, estoque_map: Optional[dict[str, float]] = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for mlb, payload in por_mlb.items():
        base = _normalize_row(payload)
        est  = estimate_30_60(base["sold_7"], base["sold_15"], base["sold_30"], DEFAULT_PARAMS.weights)
        estoque_atual = None if estoque_map is None else estoque_map.get(mlb)
        pos_delay = estoque_pos_delay(estoque_atual, est["taxa_diaria"], DEFAULT_PARAMS.lead_time_days)
        title = payload.get("title") if isinstance(payload, Mapping) else None
        out[mlb] = {
            "mlb": mlb,
            "title": title,
            **base,
            **est,
            "consumo_previsto_7d_lead": est["taxa_diaria"] * DEFAULT_PARAMS.lead_time_days,
            "estoque_atual": estoque_atual,
            "estoque_pos_delay_7": pos_delay,
        }
    return out

def carregar_por_mlb_regiao(loja: Loja, windows: Iterable[int] = (7, 15, 30)) -> dict[str, dict]:
    reg = Regiao.SP if loja == "sp" else Regiao.MG
    resp = get_por_mlb(reg, windows=windows, mode="qty")
    data = _unwrap_result(resp)
    estoque_map = _estoque_por_mlb_regiao(loja)
    return _map_estimativas_mlb(data, estoque_map=estoque_map)

# ----------------- Projeções: BR (SP+MG) por GTIN -----------------
def _map_estimativas_gtin(por_gtin: dict[str, dict], *, estoque_map: Optional[dict[str, float]] = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for gtin, payload in por_gtin.items():
        base = _normalize_row(payload)
        est  = estimate_30_60(base["sold_7"], base["sold_15"], base["sold_30"], DEFAULT_PARAMS.weights)
        estoque_atual = None if estoque_map is None else estoque_map.get(gtin)
        pos_delay = estoque_pos_delay(estoque_atual, est["taxa_diaria"], DEFAULT_PARAMS.lead_time_days)
        title = payload.get("title") if isinstance(payload, Mapping) else None
        out[gtin] = {
            "gtin": gtin,
            "title": title,
            **base,
            **est,
            "consumo_previsto_7d_lead": est["taxa_diaria"] * DEFAULT_PARAMS.lead_time_days,
            "estoque_atual": estoque_atual,
            "estoque_pos_delay_7": pos_delay,
        }
    return out

def carregar_por_gtin_br(windows: Iterable[int] = (7, 15, 30)) -> dict[str, dict]:
    resp = get_por_gtin_br(windows=windows, mode="qty")
    data = _unwrap_result(resp)
    estoque_map = _estoque_por_gtin_br()
    return _map_estimativas_gtin(data, estoque_map=estoque_map)

# ----------------- Exports internos úteis ao service -----------------
__all__ = [
    "carregar_por_mlb_regiao",
    "carregar_por_gtin_br",
    "_map_mlb_to_gtin",
]
