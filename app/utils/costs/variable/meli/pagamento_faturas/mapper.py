from __future__ import annotations
import pandas as pd

# Normaliza espaços duplicados
def _norm(s: str) -> str:
    return " ".join(str(s).split())

MAP_ABA1 = {
    "Número do pagamento": "numero_pagamento",
    "Número do estorno": "numero_estorno",
    "Tipo de pagamento": "tipo_pagamento",
    "Meio de pagamento": "meio_pagamento",
    "Data do pagamento/emissão de estorno": "data_pagamento_ou_estorno",
    "Status": "status",
    "Data de cancelamento": "data_cancelamento",
    "Valor total": "valor_total",
    "Valor aplicado a este mês": "valor_aplicado_mes",
    "Valor aplicado a outro mês": "valor_aplicado_outro_mes",
    "Saldo positivo para outras faturas": "saldo_positivo_outras_faturas",
    "Saldo positivo devolvido": "saldo_positivo_devolvido",
}

MAP_ABA2 = {
    "Número do pagamento": "numero_pagamento",
    "Data do pagamento": "data_pagamento",
    "Parte do pagamento aplicado a tarifas": "parte_pagamento_aplicada_tarifas",
    "Número da tarifa": "numero_tarifa",
    "Detalhe": "detalhe",
    "Data da tarifa": "data_tarifa",
}

def map_columns_aba1(df: pd.DataFrame) -> pd.DataFrame:
    cols = {_norm(c): c for c in df.columns}
    return df.rename(columns={orig: MAP_ABA1.get(nc, orig) for nc, orig in cols.items()})

def map_columns_aba2(df: pd.DataFrame) -> pd.DataFrame:
    cols = {_norm(c): c for c in df.columns}
    return df.rename(columns={orig: MAP_ABA2.get(nc, orig) for nc, orig in cols.items()})
