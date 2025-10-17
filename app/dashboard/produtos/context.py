# app/dashboard/produtos/context.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import streamlit as st
from app.config.paths import Regiao
from app.utils.produtos import service as produtos_svc  # fachada oficial

@dataclass
class ProdutoCtx:
    regiao: Optional[Regiao]
    busca: str
    somente_com_custo: bool
    produtos: List[Dict[str, Any]]

def _has_cost(r: Dict[str, Any]) -> bool:
    """true se houver custo numérico válido no registro."""
    v = r.get("preco_compra")
    if isinstance(v, (int, float)):
        return True
    v = r.get("custo")
    return isinstance(v, (int, float))

def _filtrar_busca(regs: List[Dict[str, Any]], txt: str) -> List[Dict[str, Any]]:
    if not txt:
        return regs
    q = txt.strip().lower()
    def ok(r: Dict[str, Any]) -> bool:
        return (
            q in str(r.get("sku", "")).lower()
            or q in str(r.get("gtin", "")).lower()
            or q in str(r.get("ean", "")).lower()
            or q in str(r.get("titulo", r.get("title", ""))).lower()
        )
    return [r for r in regs if ok(r)]

def _filtrar_regiao(regs: List[Dict[str, Any]], regiao: Optional[Regiao]) -> List[Dict[str, Any]]:
    """Se o PP expuser 'regiao', filtra; caso contrário, mantém todos (PP transversal)."""
    if not regiao:
        return regs
    alvo = regiao.value.lower()
    def ok(r: Dict[str, Any]) -> bool:
        v = (r.get("regiao") or "").lower()
        return v == alvo if v else True
    return [r for r in regs if ok(r)]

@st.cache_data(show_spinner=False)
def _load_produtos_para_envio(_regiao: Optional[Regiao]) -> List[Dict[str, Any]]:
    """
    Carrega via service no formato canônico para 'Envios':
    titulo, ean/gtin, multiplo_compra, preco_compra,
    caixa_cm{largura,profundidade,altura}, pesos_caixa_g{bruto}, etc.
    """
    return produtos_svc.listar_produtos_para_envio(_regiao)

def make_context(regiao: Optional[Regiao], busca: str, somente_com_custo: bool) -> ProdutoCtx:
    regs = _load_produtos_para_envio(regiao)
    regs = _filtrar_regiao(regs, regiao)
    if somente_com_custo:
        regs = [r for r in regs if _has_cost(r)]
    if busca:
        regs = _filtrar_busca(regs, busca)
    return ProdutoCtx(
        regiao=regiao,
        busca=busca,
        somente_com_custo=somente_com_custo,
        produtos=regs,
    )
