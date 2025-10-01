# app/dashboard/precificacao/context.py
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import streamlit as st

from app.config.paths import Regiao  # transversal
from app.utils.precificacao.service import listar_anuncios_meli, precificar_meli  # usa config do domínio por trás

@dataclass
class PrecoCtx:
    regiao: Optional[Regiao]
    busca: str
    somente_full: bool
    anuncios_basicos: List[Dict[str, Any]]
    linhas_precificacao: List[Dict[str, Any]]

def _filtrar_busca(regs, txt: str):
    if not txt:
        return regs
    q = txt.strip().lower()
    def ok(r):
        return (
            q in str(r.get("mlb", "")).lower()
            or q in str(r.get("sku", "")).lower()
            or q in str(r.get("title", "")).lower()
        )
    return [r for r in regs if ok(r)]

@st.cache_data(show_spinner=False)
def _load_anuncios(regiao: Optional[Regiao]):
    return listar_anuncios_meli(regiao=regiao)

@st.cache_data(show_spinner=False)
def _load_precos(regiao: Optional[Regiao]):
    return precificar_meli(regiao=regiao)

def make_context(regiao: Optional[Regiao], busca: str, somente_full: bool) -> PrecoCtx:
    anuncios = _load_anuncios(regiao)
    precos = _load_precos(regiao)

    if somente_full:
        anuncios = [a for a in anuncios if a.get("full") is True]
        precos = [p for p in precos if p.get("full") is True]

    if busca:
        anuncios = _filtrar_busca(anuncios, busca)
        precos = _filtrar_busca(precos, busca)

    return PrecoCtx(
        regiao=regiao,
        busca=busca,
        somente_full=somente_full,
        anuncios_basicos=anuncios,
        linhas_precificacao=precos,
    )
