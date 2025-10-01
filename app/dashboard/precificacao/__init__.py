# app/dashboard/precificacao/__init__.py
import streamlit as st
from .abas import resumo, anuncios

def render_dashboard_precificacao(ctx) -> None:
    tabs = st.tabs(["📊 Resumo", "🧾 Anúncios"])
    with tabs[0]:
        resumo.render(ctx)
    with tabs[1]:
        anuncios.render(ctx)
