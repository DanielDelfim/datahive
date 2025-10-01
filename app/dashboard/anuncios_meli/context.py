# app/dashboard/anuncios_meli/context.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import streamlit as st

from app.config.paths import Regiao
from app.utils.anuncios.service import listar_anuncios_pp  # função de leitura (PP) do módulo anúncios

@dataclass
class AnunciosCtx:
    regiao: Optional[Regiao]
    busca: str
    somente_full: bool
    registros: List[Dict[str, Any]]

def _filtrar_busca(rows: List[Dict[str, Any]], q: str):
    if not q:
        return rows
    ql = q.strip().lower()
    def ok(r):
        return (
            ql in str(r.get("mlb","")).lower() or
            ql in str(r.get("sku","")).lower() or
            ql in str(r.get("gtin","")).lower() or
            ql in str(r.get("title","")).lower()
        )
    return [r for r in rows if ok(r)]

@st.cache_data(show_spinner=False)
def _load(regiao: Optional[Regiao]) -> List[Dict[str, Any]]:
    # Se regiao=None, o service pode retornar união SP+MG
    return listar_anuncios_pp(regiao=regiao)

def make_context(regiao: Optional[Regiao], busca: str, somente_full: bool) -> AnunciosCtx:
    regs = _load(regiao)
    if somente_full:
        regs = [r for r in regs if str(r.get("logistic_type") or "").lower() == "fulfillment"]
    if busca:
        regs = _filtrar_busca(regs, busca)
    return AnunciosCtx(regiao=regiao, busca=busca, somente_full=somente_full, registros=regs)
