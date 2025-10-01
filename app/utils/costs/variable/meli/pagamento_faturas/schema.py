from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import date

# Aba 1: Pagamentos e estornos
@dataclass(frozen=True)
class PagamentoEstornoRow:
    numero_pagamento: Optional[str]
    numero_estorno: Optional[str]
    tipo_pagamento: Optional[str]
    meio_pagamento: Optional[str]
    data_pagamento_ou_estorno: Optional[date]
    status: Optional[str]
    data_cancelamento: Optional[date]
    valor_total: Optional[float]
    valor_aplicado_mes: Optional[float]
    valor_aplicado_outro_mes: Optional[float]
    saldo_positivo_outras_faturas: Optional[float]
    saldo_positivo_devolvido: Optional[float]
    competencia: str  # YYYY-MM

# Aba 2: Detalhe do Pagamentos deste mês
@dataclass(frozen=True)
class DetalhePagamentoRow:
    numero_pagamento: Optional[str]
    data_pagamento: Optional[date]
    parte_pagamento_aplicada_tarifas: Optional[float]
    numero_tarifa: Optional[str]
    detalhe: Optional[str]
    data_tarifa: Optional[date]
    competencia: str  # YYYY-MM
