#C:\Apps\Datahive\app\utils\produtos\mappers\dimensions.py
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
    PRODUTO: Retorna dict com
      peso (kg), altura (cm), largura (cm), profundidade (cm).
    Lê pesos_g.{bruto,liq} e dimensoes_cm.{altura,largura,profundidade} + aliases.
    """
    flat = _flatten_1level(rec)
    peso_raw = _coalesce(flat, [
        "pesos_g.bruto", "pesos_g.liq",
        "package_weight_g", "package.weight", "shipping_weight", "weight_g",
        "peso", "weight", "peso_bruto", "peso_liq"
    ])
    altura_raw = _coalesce(flat, [
        "dimensoes_cm.altura",
        "package_height", "shipping_height", "height", "altura", "altura_cm",
        "dimensions.height", "package.height", "shipping.height"
    ])
    largura_raw = _coalesce(flat, [
        "dimensoes_cm.largura",
        "package_width", "shipping_width", "width", "largura", "largura_cm",
        "dimensions.width", "package.width", "shipping.width"
    ])
    profundidade_raw = _coalesce(flat, [
        "dimensoes_cm.profundidade",
        "package_length", "shipping_length", "length", "profundidade", "comprimento",
        "dimensions.length", "package.length", "shipping.length"
    ])
    return {
        "peso": _parse_num_with_unit(peso_raw, kind="weight"),
        "altura": _parse_num_with_unit(altura_raw, kind="length"),
        "largura": _parse_num_with_unit(largura_raw, kind="length"),
        "profundidade": _parse_num_with_unit(profundidade_raw, kind="length"),
    }

def normalize_peso_dimensoes_caixa(rec: Mapping[str, Any]) -> dict[str, Any]:
    """
    CAIXA: Retorna dict com
      peso_caixa (kg), caixa_altura (cm), caixa_largura (cm), caixa_profundidade (cm).
    Lê pesos_caixa_g.bruto e caixa_cm.{altura,largura,profundidade} + alguns aliases.
    Não faz fallback para os campos do produto.
    """
    flat = _flatten_1level(rec)
    peso_raw = _coalesce(flat, [
        "pesos_caixa_g.bruto",  # seu PP de caixa (g)
        "box_weight_g", "box.weight_g", "outer_pack.weight_g",
    ])
    altura_raw = _coalesce(flat, [
        "caixa_cm.altura",      # seu PP de caixa (cm)
        "box_height", "outer_pack.height_cm", "box.height",
    ])
    largura_raw = _coalesce(flat, [
        "caixa_cm.largura",
        "box_width", "outer_pack.width_cm", "box.width",
    ])
    profundidade_raw = _coalesce(flat, [
        "caixa_cm.profundidade",
        "box_length", "outer_pack.length_cm", "box.length",
    ])
    return {
        "peso_caixa": _parse_num_with_unit(peso_raw, kind="weight"),
        "caixa_altura": _parse_num_with_unit(altura_raw, kind="length"),
        "caixa_largura": _parse_num_with_unit(largura_raw, kind="length"),
        "caixa_profundidade": _parse_num_with_unit(profundidade_raw, kind="length"),
    }

def attach_dims_blocks(rec: Mapping[str, Any]) -> dict[str, Any]:
    """
    Retorna um dict unificado com os dois blocos:
      - produto_*  (peso/altura/largura/profundidade)
      - caixa_*    (peso_caixa/caixa_altura/caixa_largura/caixa_profundidade)
    Não aplica fallback entre blocos; cada um usa sua própria fonte.
    """
    prod = normalize_peso_dimensoes(rec)
    box  = normalize_peso_dimensoes_caixa(rec)
    out = {
        "produto_peso": prod["peso"],
        "produto_altura": prod["altura"],
        "produto_largura": prod["largura"],
        "produto_profundidade": prod["profundidade"],
        "peso_caixa": box["peso_caixa"],
        "caixa_altura": box["caixa_altura"],
        "caixa_largura": box["caixa_largura"],
        "caixa_profundidade": box["caixa_profundidade"],
    }
    return out

