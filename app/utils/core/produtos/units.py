# app/utils/core/produtos/units.py
from __future__ import annotations

import re
from typing import Optional
import math

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")


def to_bool(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "sim", "s", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "nao", "não", "n", "no"}:
        return False
    return None


def to_int(value) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return None


def to_float(value) -> Optional[float]:
    """Converte para float; trata '', None e NaN (numérico ou string) como None."""
    if value is None:
        return None
    # NaN numérico
    if isinstance(value, float) and math.isnan(value):
        return None
    s = str(value).strip()
    if s == "" or s.lower() in {"nan", "na", "none", "null"}:
        return None
    # 1) tentativa direta (vírgula → ponto)
    try:
        f = float(s.replace(",", "."))
        if math.isnan(f):
            return None
        return f
    except Exception:
        pass
    # 2) extrair primeiro número da string
    match = _NUM_RE.search(s)
    if not match:
        return None
    try:
        f = float(match.group())
        return None if math.isnan(f) else f
    except Exception:
        return None

def cm3_to_m3(cm3: Optional[float]) -> Optional[float]:
    if cm3 is None:
        return None
    return cm3 / 1_000_000.0


def calc_volume_m3(altura_cm, largura_cm, profundidade_cm) -> Optional[float]:
    altura = to_float(altura_cm)
    larg = to_float(largura_cm)  # evitar nome ambíguo "l"
    prof = to_float(profundidade_cm)
    if altura is None or larg is None or prof is None:
        return None
    return cm3_to_m3(altura * larg * prof)


def kg_to_g(kg: Optional[float]) -> Optional[float]:
    if kg is None:
        return None
    return kg * 1000.0


def sanitize_gtin(gtin) -> Optional[str]:
    if gtin is None:
        return None
    digits = re.sub(r"\D", "", str(gtin))
    return digits or None


def sanitize_cnpj(cnpj) -> Optional[str]:
    if cnpj is None:
        return None
    digits = re.sub(r"\D", "", str(cnpj))
    return digits or None
