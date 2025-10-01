from __future__ import annotations
import pandas as pd

def _norm(s: str) -> str:
    # Normaliza espaços duplicados e aparas; mantém acentos
    return " ".join(str(s).split())

MAP_ABA1 = {
    "Nº NF-e": "numero_nfe",
    "Data da tarifa": "data_tarifa",
    "Nº da tarifa": "numero_tarifa",
    "Detalhe": "detalhe",
    "Nº da tarifa estornada": "numero_tarifa_estornada",
    "Valor da tarifa": "valor_tarifa",
    "Unidades armazenadas": "unidades_armazenadas",
    "Tamanho da unidade": "tamanho_unidade",
    "Tarifa por unidade": "tarifa_por_unidade",
}

MAP_ABA2 = {
    "Nº NF-e": "numero_nfe",
    "Data do custo": "data_custo",
    "Nº do custo": "numero_custo",
    "Detalhe": "detalhe",
    "Forma de retirada": "forma_retirada",
    "Nº do custo estornado": "numero_custo_estornado",
    "Valor do custo": "valor_custo",
    "Tarifa por m3": "tarifa_por_m3",
    "Unidades retiradas": "unidades_retiradas",
    "Volume unitário (cm3)": "volume_unitario_cm3",
    "Nº da retirada": "numero_retirada",
    "Código universal": "codigo_universal",
    "SKU": "sku",
    "Código ML": "codigo_ml",
    "Nº do anúncio": "numero_anuncio",
    "Título do anúncio": "titulo_anuncio",
    "Variação": "variacao",
}

MAP_ABA3 = {
    "Nº NF-e": "numero_nfe",
    "Data do custo": "data_custo",
    "Nº do custo": "numero_custo",
    "Detalhe": "detalhe",
    "Nº do custo estornado": "numero_custo_estornado",
    "Valor do custo": "valor_custo",
    "Tarifa por m3": "tarifa_por_m3",
    "Volume total (m3)": "volume_total_m3",
    "Unidades coletadas": "unidades_coletadas",
    "Volume unitário (cm3)": "volume_unitario_cm3",
    "N° do envio": "numero_envio",
    "Código universal": "codigo_universal",
    "SKU": "sku",
    "Código ML": "codigo_ml",
    "Nº do anúncio": "numero_anuncio",
    "Título do anúncio": "titulo_anuncio",
    "Variação": "variacao",
}

MAP_ABA4 = {
    "Nº NF-e": "numero_nfe",
    "Data do custo": "data_custo",
    "Nº do custo": "numero_custo",
    "Detalhe": "detalhe",
    "Nº do custo estornado": "numero_custo_estornado",
    "Valor do custo": "valor_custo",
    "Custo por unidade": "custo_por_unidade",
    "Unidades armazenadas": "unidades_armazenadas",
    "Tamanho da unidade": "tamanho_unidade",
    "Tempo em meses": "tempo_meses",
    "Código universal": "codigo_universal",
    "SKU": "sku",
    "Código ML": "codigo_ml",
    "Nº do anúncio": "numero_anuncio",
    "Título do anúncio": "titulo_anuncio",
    "Variação": "variacao",
    "Unidades disponíveis": "unidades_disponiveis",
    "Unidades não disponíveis": "unidades_nao_disponiveis",
}

def _map(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    # mapeia preservando colunas desconhecidas
    cols_norm = {_norm(c): c for c in df.columns}
    return df.rename(columns={orig: mapping.get(norm, orig) for norm, orig in cols_norm.items()})

def map_aba1(df: pd.DataFrame) -> pd.DataFrame:  # Tarifa de armazenamento
    return _map(df, MAP_ABA1)

def map_aba2(df: pd.DataFrame) -> pd.DataFrame:  # Custo por retirada de estoque
    return _map(df, MAP_ABA2)

def map_aba3(df: pd.DataFrame) -> pd.DataFrame:  # Custo por serviço de coleta
    return _map(df, MAP_ABA3)

def map_aba4(df: pd.DataFrame) -> pd.DataFrame:  # Custo de armazenamento prolonga
    return _map(df, MAP_ABA4)

__all__ = ["map_aba1", "map_aba2", "map_aba3", "map_aba4"]
