# app/dashboard/produtos/context.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import streamlit as st
from app.config.paths import Regiao
from app.utils.produtos.service import get_itens  # leitura do PP (somente leitura)

@dataclass
class ProdutoCtx:
    regiao: Optional[Regiao]
    busca: str
    somente_com_custo: bool
    produtos: List[Dict[str, Any]]

def _filtrar_busca(regs: List[Dict[str, Any]], txt: str):
    if not txt:
        return regs
    q = txt.strip().lower()
    def ok(r):
        return (
            q in str(r.get("sku", "")).lower()
            or q in str(r.get("gtin", "")).lower()
            or q in str(r.get("title", r.get("titulo",""))).lower()
        )
    return [r for r in regs if ok(r)]

def _filtrar_regiao(regs: List[Dict[str, Any]], regiao: Optional[Regiao]):
    if not regiao:
        return regs
    # se o PP tiver campo 'regiao', filtra; senão, mantém (PP transversal)
    alvo = regiao.value.lower()
    def ok(r):
        v = (r.get("regiao") or "").lower()
        return v == alvo if v else True
    return [r for r in regs if ok(r)]

@st.cache_data(show_spinner=False)
def _load_produtos(_regiao: Optional[Regiao]):
    items = get_itens()  # dict {sku: {...}}
    return [{**v, "sku": k} for k, v in items.items()]

def make_context(regiao: Optional[Regiao], busca: str, somente_com_custo: bool) -> ProdutoCtx:
    regs = _load_produtos(regiao)
    regs = _filtrar_regiao(regs, regiao)
    if somente_com_custo:
        regs = [r for r in regs if isinstance(r.get("preco_compra") or r.get("custo"), (int, float))]
    if busca:
        regs = _filtrar_busca(regs, busca)
    return ProdutoCtx(regiao=regiao, busca=busca, somente_com_custo=somente_com_custo, produtos=regs)
