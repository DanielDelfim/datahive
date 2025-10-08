# app/utils/vendas/meli/config.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.config.paths import (
    APP_TIMEZONE,
    vendas_raw_json, vendas_pp_json, vendas_resumo_json, vendas_resumo_hoje_json, vendas_por_mlb_json,
    pp_dir,
)

Loja = Literal["sp", "mg"]

@dataclass(frozen=True)
class VendasMeliPaths:
    loja: Loja
    timezone: str = APP_TIMEZONE

    def raw_json(self) -> Path:
        return vendas_raw_json(self.loja)

    def pp_json(self) -> Path:
        return vendas_pp_json(self.loja)

    def resumo_json(self) -> Path:
        return vendas_resumo_json(self.loja)

    def resumo_hoje_json(self) -> Path:
        return vendas_resumo_hoje_json(self.loja)

    def por_mlb_json(self) -> Path:
        return vendas_por_mlb_json(self.loja)

    def pp_dir(self) -> Path:
        return pp_dir(self.loja)
