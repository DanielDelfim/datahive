from __future__ import annotations
import pandas as pd

# headers exatos informados na planilha
HEADER_MAP = {
    "N° NF-e": "numero_nfe",
    "Data do movimento": "data_movimento",
    "Número da tarifa": "numero_tarifa",
    "Número da movimentação": "numero_movimentacao",
    "Detalhe": "detalhe",
    "Cobrados na operação": "cobrados_na_operacao",
    "Status da tarifa": "status_tarifa",
    "Tarifa estornada": "tarifa_estornada",
    "Valor da tarifa": "valor_tarifa",
    "Tipo de operação": "tipo_operacao",
    "Operação relacionada": "operacao_relacionada",
    "Nome da filial": "nome_filial",
    "Referência externa": "referencia_externa",
    "Cliente": "cliente",
    "Valor del acrescimo": "valor_acrescimo",              # mantém o rótulo como veio
    "Valor total acrescido": "valor_total_acrescido",
    "Valor da operação": "valor_operacao",
    "Seções do Mercado livre e do Mercado Pago": "secoes_ml_mp",
}

def _normalize_col(c: str) -> str:
    # remove espaços duplicados e aparas, sem mexer em acentos
    return " ".join(str(c).split())

def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    # normaliza nomes antes de mapear (protege contra espaços duplos)
    normalized = {_normalize_col(c): c for c in df.columns}
    rename = {}
    for norm, original in normalized.items():
        rename[original] = HEADER_MAP.get(norm, original)
    return df.rename(columns=rename)
