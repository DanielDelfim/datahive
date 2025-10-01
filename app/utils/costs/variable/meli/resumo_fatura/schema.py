from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass(frozen=True)
class LinhaResumo:
    key: str          # ex.: "outras_tarifas"
    label: str        # ex.: "Outras tarifas"
    valor: float      # sinal contábil (negativo onde aplicável)
    fontes: Dict[str, float]  # que json/sinal contribuíram (para auditoria)

@dataclass(frozen=True)
class ResumoFatura:
    meta: Dict[str, Any]
    sua_fatura_inclui: List[LinhaResumo]
    ja_cobramos: List[LinhaResumo]
    total_fatura: float
    total_recebido: float
    falta_pagar: float
