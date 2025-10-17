#C:\Apps\Datahive\app\utils\replacement\service.py
from __future__ import annotations
from typing import Iterable, Literal
from .aggregator import (
    carregar_por_mlb_regiao,
    carregar_por_gtin_br,
    _map_mlb_to_gtin,
)

Loja = Literal["sp", "mg"]

__all__ = [
    "estimativa_consumo_por_mlb",     # SP/MG por MLB
    "estimativa_consumo_por_gtin_br", # BR por GTIN
    "map_mlb_to_gtin",
]

def estimativa_consumo_por_mlb(loja: Loja, *, windows: Iterable[int] = (7, 15, 30)) -> dict[str, dict]:
    """SP/MG: projeções por MLB (consumo 7/15/30 + estoque por anúncio)."""
    return carregar_por_mlb_regiao(loja, windows=windows)

def estimativa_consumo_por_gtin_br(*, windows: Iterable[int] = (7, 15, 30)) -> dict[str, dict]:
    """BR (SP+MG): projeções por GTIN (consumo agregado + estoque somado)."""
    return carregar_por_gtin_br(windows=windows)

def map_mlb_to_gtin(loja: Loja) -> dict[str, str]:
    """Mapa MLB→GTIN por região (para enriquecer detalhes com dados de produto)."""
    return _map_mlb_to_gtin(loja)
