from __future__ import annotations
from typing import Optional, Union, List, Dict, Tuple
from pathlib import Path
import json
import re

from app.config.paths import Regiao
from app.utils.tax_documents.config import (
    pp_month_dir, pp_resumo_json_path, pp_json_path,
)
from app.utils.tax_documents.service import (
    gerar_pp_json,
    gerar_resumo_por_natureza_from_pp,
    gerar_excel_consolidado,
    gerar_excel_consolidado_por_nota,
    totais_vendas_por_provedor_cfop,  # ← novo contrato para os cards
)

# ---------- AÇÕES (services) ----------

def calcular_totais_vendas_mes(ano: int, mes: int) -> tuple[dict[str, float], float]:
    """
    Totais por provedor (venda própria, revenda e total) com base em CFOP,
    dedupe por NF e somente autorizadas. Retorna (dict_provedores, total_geral).
    """
    return totais_vendas_por_provedor_cfop(ano, mes, somente_autorizadas=True)

def acionar_geracao_pp_json(provedor: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]]) -> str:
    return gerar_pp_json(provedor, ano, mes, regiao, dry_run=False, debug=True)

def acionar_resumo_natureza(
    provedor: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]], *, modo: str = "todos"
) -> str:
    return gerar_resumo_por_natureza_from_pp(provedor, ano, mes, regiao, modo=modo, dry_run=False, debug=True)

def acionar_gerar_excel_consolidado(ano:int, mes:int) -> str:
    return gerar_excel_consolidado(ano, mes)

def acionar_gerar_excel_consolidado_por_nota(ano:int, mes:int) -> str:
    return gerar_excel_consolidado_por_nota(ano, mes)

# ---------- LEITURA DE ARQUIVOS (sem cálculo) ----------

def carregar_resumo_json(provedor: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]]) -> List[Dict]:
    p = pp_resumo_json_path(provedor, ano, mes, regiao)
    if not Path(p).exists():
        return []
    return (json.loads(Path(p).read_text(encoding="utf-8")).get("rows")) or []

def carregar_pp_json(provedor: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]]) -> List[Dict]:
    p = pp_json_path(provedor, ano, mes, regiao)
    if not Path(p).exists():
        return []
    return (json.loads(Path(p).read_text(encoding="utf-8")).get("rows")) or []

# ---------- DISCOVERY (consolidado) ----------

PROVIDERS = ("meli", "amazon", "bling")
_VALID_REGS = {r.value for r in Regiao}
_BACKUP_PAT = re.compile(r"(^\\.|backup)", re.IGNORECASE)

def _is_valid_region_dir(p: Path) -> bool:
    return p.is_dir() and not _BACKUP_PAT.search(p.name) and p.name.lower() in _VALID_REGS

def listar_disponiveis(ano: int, mes: int) -> Dict[str, List[Optional[str]]]:
    """
    Vasculha .../pp/YYYY/MM[/<regiao>] por provedor e retorna {provider: [regioes|None]}.
    """
    disponiveis: Dict[str, List[Optional[str]]] = {}
    for prov in PROVIDERS:
        month_base = Path(pp_month_dir(prov, ano, mes, regiao=None))
        if not month_base.exists():
            continue
        subdirs = [p for p in month_base.iterdir() if _is_valid_region_dir(p)]
        if subdirs:
            disponiveis[prov] = sorted([p.name.lower() for p in subdirs])
        else:
            # sem subpastas válidas: bling direto na raiz do mês
            if Path(pp_resumo_json_path(prov, ano, mes, regiao=None)).exists():
                disponiveis[prov] = [None]
    return disponiveis

def carregar_resumo_consolidado_all(ano: int, mes: int) -> Dict[Tuple[str, Optional[str]], List[Dict]]:
    """
    Lê todos os resumos por provedor/região disponíveis no mês.
    Retorna { (provider, regiao|None): rows[] }.
    """
    out: Dict[Tuple[str, Optional[str]], List[Dict]] = {}
    disp = listar_disponiveis(ano, mes)
    for prov, regs in disp.items():
        for reg in regs:
            p = Path(pp_resumo_json_path(prov, ano, mes, reg))
            rows: List[Dict] = []
            if p.exists():
                rows = (json.loads(p.read_text(encoding="utf-8")).get("rows")) or []
            out[(prov, reg)] = rows
    return out
