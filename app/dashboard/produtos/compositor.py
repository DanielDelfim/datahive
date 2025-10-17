# app/dashboard/produtos/compositor.py
from __future__ import annotations
import streamlit as st

# Respeita a estrutura atual: resumo.py e catalogo.py no mesmo pacote.
from .abas import envios, resumo, catalogo  # nova aba

def render(ctx) -> None:
    """
    Renderiza o dashboard de Produtos com abas.
    ctx: ProdutoCtx retornado por app/dashboard/produtos/context.make_context
    """
    st.subheader("Produtos — Dashboard")

    # Abas
    tab1, tab2, tab3 = st.tabs(["Resumo", "Catálogo", "Envios"])

    with tab1:
        resumo.render(ctx)

    with tab2:
        catalogo.render(ctx)

    with tab3:
        envios.render(ctx)
