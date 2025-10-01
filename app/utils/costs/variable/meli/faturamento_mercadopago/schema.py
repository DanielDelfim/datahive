from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass(frozen=True)
class FaturamentoMercadoPagoRow:
    numero_nfe: Optional[str]
    data_movimento: Optional[date]
    numero_tarifa: Optional[str]
    numero_movimentacao: Optional[str]
    detalhe: Optional[str]
    cobrados_na_operacao: Optional[str]
    status_tarifa: Optional[str]
    tarifa_estornada: Optional[bool]
    valor_tarifa: Optional[float]
    tipo_operacao: Optional[str]
    operacao_relacionada: Optional[str]
    nome_filial: Optional[str]
    referencia_externa: Optional[str]
    cliente: Optional[str]
    valor_acrescimo: Optional[float]
    valor_total_acrescido: Optional[float]
    valor_operacao: Optional[float]
    secoes_ml_mp: Optional[str]
    competencia: str  # "YYYY-MM"
