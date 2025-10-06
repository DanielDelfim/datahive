from __future__ import annotations
from pathlib import Path
from typing import Optional, Union
from app.config.paths import DATA_DIR, Camada, Regiao

ART_NAME = "tax_documents"
DOMINIO = "fiscal"

# cStat sets (podem ser ajustados conforme manual SEFAZ)
CSTAT_AUTORIZADA = {"100", "150"}
CSTAT_CANCELADA  = {"101", "151"}
CSTAT_DENEGADA   = {"110", "301", "302", "303"}

# eventos
EVT_CANCELAMENTO = "110111"
EVT_CCE          = "110110"
EVT_EPEC         = "110140"

# CFOPs que consideraremos "devolução" (ajuste com seu contador)
CFOPS_DEVOLUCAO = {
    "1202","1203","1209",
    "2202","2203","2209",
    "5202","5203","5209",
    "6202","6203","6209",
}

# classes de CFOP (ajuste com seu contador)
CFOPS_VENDA = {"5101","5102","5405","6101","6102","6405"}
CFOPS_TRANSFER = {"5152","6152"}  # coloque outras se usar
CFOPS_OUTROS = {"5949","6949"}

# 👇 novos (para os cards e somatórios)
CFOPS_VENDA_PROPRIA = {"5101","6101"}                # produção do estabelecimento
CFOPS_REVENDA       = {"5102","5405","6102","6405"} 


DOMINIO = "fiscal"
ART_NAME = "tax_documents"

def pp_consolidado_dir(ano:int, mes:int) -> Path:
    # .../data/fiscal/tax_documents/_consolidado/pp/YYYY/MM/
    return (Path(DATA_DIR) / DOMINIO / ART_NAME / "_consolidado" / Camada.PP.value /
            f"{ano:04d}" / f"{mes:02d}")

def pp_consolidado_somas_json_path(ano:int, mes:int) -> Path:
    return pp_consolidado_dir(ano, mes) / "somas_vendas_revendas.json"

def _append_regiao(base: Path, regiao: Optional[Union[Regiao, str]]) -> Path:
    if regiao is None or str(regiao).strip() == "":
        return base
    if isinstance(regiao, Regiao):
        return base / regiao.value
    return base / str(regiao).lower()

def raw_zip_dir(provider: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]] = None) -> Path:
    """
    .../data/fiscal/tax_documents/<provider>/raw/YYYY/MM[/<regiao>]
    """
    base = Path(DATA_DIR) / DOMINIO / ART_NAME / provider.lower() / Camada.RAW.value / f"{ano:04d}" / f"{mes:02d}"
    return _append_regiao(base, regiao)

def pp_month_dir(provider: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]] = None) -> Path:
    """
    .../data/fiscal/tax_documents/<provider>/pp/YYYY/MM[/<regiao>]
    """
    base = Path(DATA_DIR) / DOMINIO / ART_NAME / provider.lower() / Camada.PP.value / f"{ano:04d}" / f"{mes:02d}"
    return _append_regiao(base, regiao)

def pp_json_path(provider: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]] = None) -> Path:
    return pp_month_dir(provider, ano, mes, regiao) / f"{ART_NAME}_pp.json"

def pp_resumo_json_path(provider: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]] = None) -> Path:
    return pp_month_dir(provider, ano, mes, regiao) / "tax_documents_resumo_natureza_pp.json"

def pp_consolidado_excel_path(ano: int, mes: int) -> Path:
    # .../data/fiscal/tax_documents/_consolidado/pp/YYYY/MM/tax_documents_consolidado.xlsx
    base = Path(DATA_DIR) / DOMINIO / ART_NAME / "_consolidado" / Camada.PP.value / f"{ano:04d}" / f"{mes:02d}"
    base.mkdir(parents=True, exist_ok=True)
    return base / "tax_documents_consolidado.xlsx"

# colunas finais (sem mudanças)
COLUMNS = [
    "ID Nota","Serie","Numero Nota","Data emissao","Data saída","Regime Tributario","Natureza",
    "Base ICMS","Valor ICMS","Base ICMS Subst","Valor ICMS Subst","Valor Servicos","Valor Produtos",
    "Frete","Seguro","Outras Despesas","Valor IPI","Valor Nota","Desconto","Valor Funrural",
    "Total Faturado","Contato","Fantasia","CPF / CNPJ","Municipio","UF","Cep","Endereco","Nro",
    "Bairro","Complemento","E-mail","Fone","Item Descricao","Item Codigo","Item Quantidade",
    "Item UN","Item Valor","Item Total","Item Frete","Item Seguro","Item Outras Despesas",
    "Item Desconto","Item CFOP","Item NCM","ST / CSOSN","Valor Base Simples / ICMS",
    "Valor Imposto Simples / ICMS","Valor Base Calculo Simples / ICMS","Valor Imposto ST / ICMS",
    "Alíquota Crédito Simples","Valor Crédito Simples","Valor Base COFINS","Valor Imposto COFINS",
    "Valor Base PIS","Valor Imposto PIS","Valor Base IPI","Valor Imposto IPI","Valor Base II",
    "Valor Imposto II","Frete por conta","Observacoes","Chave de acesso","Peso líquido",
    "Peso bruto","Item Origem", "CNPJ Emissor","Situacao NFe","Eh Devolucao","Possui CC-e","Em Contingencia",
    "Cancelada em","Prot Cancel","Justificativa Cancel"
]
