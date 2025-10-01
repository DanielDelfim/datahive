from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass(frozen=True)
class FaturamentoMeliRow:
    numero_nfe: Optional[str]
    data_tarifa: Optional[date]
    numero_tarifa: Optional[str]
    detalhe: Optional[str]
    descontado_da_operacao: Optional[str]
    status_tarifa: Optional[str]
    tarifa_estornada: Optional[bool]
    valor_tarifa: Optional[float]
    custo_por_categoria: Optional[float]
    custo_fixo: Optional[float]
    subtotal_sem_desconto: Optional[float]
    desconto_comercial: Optional[float]
    desconto_por_campanha: Optional[float]
    numero_venda: Optional[str]
    pagamento: Optional[str]
    data_venda: Optional[date]
    canal_vendas: Optional[str]
    cliente: Optional[str]
    quantidade_vendida: Optional[float]
    preco_unitario: Optional[float]
    valor_transacao: Optional[float]
    valor_acrescimo_preco: Optional[float]
    preco_produto_com_acrescimo: Optional[float]
    numero_envio: Optional[str]
    numero_embalagem: Optional[str]
    envio_por_conta_do_cliente: Optional[float]
    numero_anuncio: Optional[str]
    numero_kit: Optional[str]
    titulo_anuncio: Optional[str]
    tipo_anuncio: Optional[str]
    categoria_anuncio: Optional[str]
    codigo_ml: Optional[str]
    secoes_ml_mp: Optional[str]
    competencia: str  # YYYY-MM
