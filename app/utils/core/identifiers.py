# app/utils/core/identifiers.py
from __future__ import annotations
from typing import Optional

# Casos colados/ruins → destino (o seu FIX_MAP)
_FIX_MAP = {
    "78989153800197908883300183": "7908883300183",  # você atualizou para este destino
    "78989153808047898915380927": "7898915380804",
    # redundância só-dígitos
    "78989153800197908883300183".replace(".", "").replace("-", ""): "7908883300183",
    "78989153808047898915380927".replace(".", "").replace("-", ""): "7898915380804",
}

# OVERRIDES PONTUAIS: GTIN “válido porém errado” → GTIN correto
# ATENÇÃO: isso é global; mantenha pequeno e removível.
_OVERRIDE_MAP = {
    "7898915380019": "7908883300183",
    # adicione outros se necessário
}

def _only_digits(s: str) -> str:
    return "".join(ch for ch in s if s and s.isdigit())

def normalize_gtin(gtin: Optional[str]) -> Optional[str]:
    """
    Normaliza GTIN:
      1) Correções de strings problemáticas (_FIX_MAP)
      2) Overrides pontuais (_OVERRIDE_MAP) ANTES e DEPOIS de limpar dígitos
      3) Remove não-dígitos; retorna dígitos (chamador decide validar 13–14)
    """
    if gtin is None:
        return None
    raw = gtin.strip()
    if not raw:
        return None

    # 1) correção direta (colados etc.)
    if raw in _FIX_MAP:
        return _FIX_MAP[raw]

    # 2) override pontual (válido porém errado)
    if raw in _OVERRIDE_MAP:
        return _OVERRIDE_MAP[raw]

    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits in _FIX_MAP:
        return _FIX_MAP[digits]
    if digits in _OVERRIDE_MAP:
        return _OVERRIDE_MAP[digits]

    return digits or None
