# app/dashboard/anuncios_meli/__init__.py
import streamlit as st
from .abas import resumo, catalogo

def render_dashboard_anuncios(ctx) -> None:
    tabs = st.tabs(["📊 Resumo", "📚 Catálogo"])
    with tabs[0]:
        resumo.render(ctx)
    with tabs[1]:
        catalogo.render(ctx)
