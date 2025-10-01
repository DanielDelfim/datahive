from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import date

# Aba 1: Tarifa de armazenamento
@dataclass(frozen=True)
class TarifaArmazenamentoRow:
    numero_nfe: Optional[str]
    data_tarifa: Optional[date]
    numero_tarifa: Optional[str]
    detalhe: Optional[str]
    numero_tarifa_estornada: Optional[str]
    valor_tarifa: Optional[float]
    unidades_armazenadas: Optional[float]
    tamanho_unidade: Optional[str]
    tarifa_por_unidade: Optional[float]
    competencia: str

# Aba 2: Custo por retirada de estoque
@dataclass(frozen=True)
class CustoRetiradaEstoqueRow:
    numero_nfe: Optional[str]
    data_custo: Optional[date]
    numero_custo: Optional[str]
    detalhe: Optional[str]
    forma_retirada: Optional[str]
    numero_custo_estornado: Optional[str]
    valor_custo: Optional[float]
    tarifa_por_m3: Optional[float]
    unidades_retiradas: Optional[float]
    volume_unitario_cm3: Optional[float]
    numero_retirada: Optional[str]
    codigo_universal: Optional[str]
    sku: Optional[str]
    codigo_ml: Optional[str]
    numero_anuncio: Optional[str]
    titulo_anuncio: Optional[str]
    variacao: Optional[str]
    competencia: str

# Aba 3: Custo por serviço de coleta
@dataclass(frozen=True)
class CustoServicoColetaRow:
    numero_nfe: Optional[str]
    data_custo: Optional[date]
    numero_custo: Optional[str]
    detalhe: Optional[str]
    numero_custo_estornado: Optional[str]
    valor_custo: Optional[float]
    tarifa_por_m3: Optional[float]
    volume_total_m3: Optional[float]
    unidades_coletadas: Optional[float]
    volume_unitario_cm3: Optional[float]
    numero_envio: Optional[str]
    codigo_universal: Optional[str]
    sku: Optional[str]
    codigo_ml: Optional[str]
    numero_anuncio: Optional[str]
    titulo_anuncio: Optional[str]
    variacao: Optional[str]
    competencia: str

# Aba 4: Custo de armazenamento prolongado
@dataclass(frozen=True)
class CustoArmazenamentoProlongadoRow:
    numero_nfe: Optional[str]
    data_custo: Optional[date]
    numero_custo: Optional[str]
    detalhe: Optional[str]
    numero_custo_estornado: Optional[str]
    valor_custo: Optional[float]
    custo_por_unidade: Optional[float]
    unidades_armazenadas: Optional[float]
    tamanho_unidade: Optional[str]
    tempo_meses: Optional[float]
    codigo_universal: Optional[str]
    sku: Optional[str]
    codigo_ml: Optional[str]
    numero_anuncio: Optional[str]
    titulo_anuncio: Optional[str]
    variacao: Optional[str]
    unidades_disponiveis: Optional[float]
    unidades_nao_disponiveis: Optional[float]
    competencia: str
