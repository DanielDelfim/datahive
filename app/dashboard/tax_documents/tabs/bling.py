from __future__ import annotations
import streamlit as st
from app.dashboard.tax_documents import compositor as C
from app.dashboard.tax_documents.ui import modo_operacao

def render(ano: int, mes: int):
    st.subheader("Bling — Resumo por Natureza")
    c1, c2 = st.columns(2)
    with c1:
        ano_b = st.number_input("Ano (Bling)", 2015, 2100, ano, key="ano_bling")
    with c2:
        mes_b = st.number_input("Mês (Bling)", 1, 12, mes, key="mes_bling")

    modo = modo_operacao("modo_bling", default="vendas")
    if st.button("Carregar Resumo Bling"):
        C.acionar_resumo_natureza("bling", int(ano_b), int(mes_b), None, modo=modo)
        rows = C.carregar_resumo_json("bling", int(ano_b), int(mes_b), None)
        st.dataframe(rows, use_container_width=True) if rows else st.warning("Resumo não encontrado.")
