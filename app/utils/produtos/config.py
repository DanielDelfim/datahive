# app/utils/produtos/config.py
"""
Config do módulo de Produtos.

UNIDADES DE ENTRADA (OFICIAL):
- Dimensões: centímetros (cm) → altura_cm, largura_cm, profundidade_cm
- Pesos: gramas (g) → peso_liq_g, peso_bruto_g e pesos_caixa_g.{liq, bruto}
Observação: conversões para outras unidades devem ocorrer internamente em utils/core,
mantendo o JSON PP no padrão acima (cm e g; volume em m3).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Set
from pathlib import Path

# Itens transversais (fonte única em app/config/paths.py)
from app.config.paths import DATA_DIR, Camada

# ===== PATHS DO MÓDULO (AQUI) =====
def cadastro_produtos_excel() -> Path:
    """
    Excel oficial de cadastro de produtos.
    Mantemos o caminho derivado de DATA_DIR para seguir a diretriz de paths centralizados:
    data/produtos/excel/cadastro_produtos_template.xlsx
    """
    return Path(DATA_DIR) / "produtos" / "excel" / "cadastro_produtos_template.xlsx"

def produtos_dir(camada: Camada = Camada.PP) -> Path:
    return Path(DATA_DIR) / "produtos" / camada.value

def produtos_json(camada: Camada = Camada.PP) -> Path:
    d = produtos_dir(camada)
    d.mkdir(parents=True, exist_ok=True)
    return d / "produtos.json"

# ===== PARÂMETROS (schema/domínios/defaults) =====
COLUMNS_EXCEL: List[str] = [
    "sku","gtin","bling_id","titulo","e_kit","Unidades_no_kit","marca","ncm","cest",
    "origem_mercadoria","unidade_medida","peso_liq_g","peso_bruto_g","altura_cm","largura_cm",
    "profundidade_cm","volume_m3","preco_compra","fornecedor_nome","fornecedor_cnpj","fornecedor_codigo",
    "lead_time_dias","dum_14","multiplo_compra","peso_bruto_caixa","peso_liq_caixa","largura_caixa",
    "altura_caixa","profundidade_caixa","regime_fiscal","csosn_default","atrib_conteudo_liquido",
    "atrib_tipo_embalagem","atrib_validade_meses","ativo","categoria_interna","observacoes"
]
UNIDADES_MEDIDA: Set[str] = {"UN","KG","G","ML","L"}
ORIGEM_MERCADORIA: Set[str] = {str(i) for i in range(0, 10)}
REGIME_FISCAL: Set[str] = {"SN","LR","LP"}
REQUIRED_MIN: List[str] = ["sku", "titulo", "preco_compra"]
DEFAULTS: Dict[str, object] = {"e_kit": False, "Unidades_no_kit": None, "ativo": True, "multiplo_compra": 1}

# ===== GETTERS AGREGADOS =====
@dataclass(frozen=True)
class ProdutosPaths:
    excel: str
    pp_json: str

def get_paths() -> ProdutosPaths:
    return ProdutosPaths(
        excel=str(cadastro_produtos_excel()),
        pp_json=str(produtos_json(Camada.PP)),
    )
