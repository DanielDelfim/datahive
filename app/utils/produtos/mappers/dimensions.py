# app/utils/produtos/mappers/dimensoes.py
from __future__ import annotations
import re
import unicodedata
from typing import Any, Iterable, Mapping

_NUM_RE = re.compile(r"([-+]?\d+(?:[.,]\d+)?)\s*([a-zA-Z]*)")

def _slug_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()

def _coalesce(d: Mapping[str, Any], keys: Iterable[str], default=None):
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}, "nan", "None"):
            return d[k]
    return default

def _parse_num_with_unit(val, *, kind: str) -> float | None:
    # kind: 'weight' -> kg ; 'length' -> cm
    if val in (None, "", "-", "nan", "None"):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    m = _NUM_RE.search(val.strip())
    if not m:
        return None
    num, unit = m.group(1), (m.group(2) or "").lower()
    num = float(num.replace(",", "."))
    if kind == "weight":
        if unit in ("", "kg", "kgs"):
            return num
        if unit in ("g", "grama", "gramas", "grams"):
            return num / 1000.0
        if unit in ("mg",):
            return num / 1_000_000.0
        if unit in ("lb", "lbs"):
            return num * 0.45359237
        return num
    else:
        if unit in ("", "cm"):
            return num
        if unit in ("mm",):
            return num / 10.0
        if unit in ("m", "mt", "mts"):
            return num * 100.0
        if unit in ("in", "inch", "inches"):
            return num * 2.54
        return num

def _flatten_1level(rec: Mapping[str, Any]) -> dict[str, Any]:
    """
    Achata 1 nível e expõe subcampos de blocos comuns.
    Inclui: 'dimensoes_cm', 'caixa_cm', 'pesos_g', 'pesos_caixa_g'
    """
    out = {k: v for k, v in rec.items()}
    for blk in (
        "dimensoes", "dimensions", "package", "pacote",
        "shipping", "shipment", "pack", "embalagem",
        "dimensoes_cm", "caixa_cm", "pesos_g", "pesos_caixa_g"
    ):
        v = rec.get(blk)
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out[f"{blk}.{k2}"] = v2
    return out

def normalize_peso_dimensoes(rec: Mapping[str, Any]) -> dict[str, Any]:
    """
    Retorna dict com:
      peso (kg), altura (cm), largura (cm), profundidade (cm)
    Suporta seu PP: pesos_g.{bruto, liq} e dimensoes_cm.{altura, largura, profundidade}
    + aliases comuns (ML, etc.).
    """
    flat = _flatten_1level(rec)

    peso_raw = _coalesce(flat, [
        "pesos_g.bruto", "pesos_g.liq",      # seu PP
        "package_weight_g", "package.weight", "shipping_weight", "weight_g",
        "peso", "weight", "peso_bruto", "peso_liq"
    ])
    altura_raw = _coalesce(flat, [
        "dimensoes_cm.altura",               # seu PP
        "package_height", "shipping_height", "height", "altura", "altura_cm",
        "dimensions.height", "package.height", "shipping.height"
    ])
    largura_raw = _coalesce(flat, [
        "dimensoes_cm.largura",              # seu PP
        "package_width", "shipping_width", "width", "largura", "largura_cm",
        "dimensions.width", "package.width", "shipping.width"
    ])
    profundidade_raw = _coalesce(flat, [
        "dimensoes_cm.profundidade",         # seu PP
        "package_length", "shipping_length", "length", "profundidade", "comprimento",
        "dimensions.length", "package.length", "shipping.length"
    ])

    return {
        "peso": _parse_num_with_unit(peso_raw, kind="weight"),
        "altura": _parse_num_with_unit(altura_raw, kind="length"),
        "largura": _parse_num_with_unit(largura_raw, kind="length"),
        "profundidade": _parse_num_with_unit(profundidade_raw, kind="length"),
    }
