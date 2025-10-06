from __future__ import annotations
import streamlit as st
from .tabs import resumo, anuncios

TABS = {
    "Resumo": resumo.render,
    "Anúncios": anuncios.render,
}

def render_dashboard_precificacao(ctx: dict) -> None:
    tab_labels = list(TABS.keys())
    tab_objects = st.tabs(tab_labels)
    for tab, label in zip(tab_objects, tab_labels):
        with tab:
            TABS[label](ctx)
