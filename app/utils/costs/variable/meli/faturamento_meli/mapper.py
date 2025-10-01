from __future__ import annotations
import pandas as pd

HEADER_MAP = {
    "N° NF-e": "numero_nfe",
    "Data da tarifa": "data_tarifa",
    "Número da tarifa": "numero_tarifa",
    "Detalhe": "detalhe",
    "Descontado da operação": "descontado_da_operacao",
    "Status da tarifa": "status_tarifa",
    "Tarifa estornada": "tarifa_estornada",
    "Valor da tarifa": "valor_tarifa",
    "Custo por categoria": "custo_por_categoria",
    "Custo fixo": "custo_fixo",
    "Subtotal sem desconto": "subtotal_sem_desconto",
    "Desconto comercial": "desconto_comercial",
    "Desconto por campanha": "desconto_por_campanha",
    "Número da venda": "numero_venda",
    "Pagamento": "pagamento",
    "Data de venda": "data_venda",
    "Canal de vendas": "canal_vendas",
    "Cliente": "cliente",
    "Quantidade vendida": "quantidade_vendida",
    "Preço unitário": "preco_unitario",
    "Valor da transação": "valor_transacao",
    "Valor do acréscimo no preço (pago pelo comprador)": "valor_acrescimo_preco",
    "Preço do produto com acréscimo": "preco_produto_com_acrescimo",
    "Número da envío": "numero_envio",
    "Número da embalagem": "numero_embalagem",
    "Envio por conta do cliente": "envio_por_conta_do_cliente",
    "Número do anúncio": "numero_anuncio",
    "Número do kit": "numero_kit",
    "Título do anúncio": "titulo_anuncio",
    "Tipo do anúncio": "tipo_anuncio",
    "Categoria do anúncio": "categoria_anuncio",
    "Código ML": "codigo_ml",
    "Seções do Mercado livre e do Mercado Pago": "secoes_ml_mp",
}

def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: HEADER_MAP.get(c, c) for c in df.columns})
