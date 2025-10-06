from __future__ import annotations
import streamlit as st
from app.dashboard.tax_documents import compositor as C
from app.dashboard.tax_documents.ui import select_regiao, modo_operacao

def render(ano: int, mes: int):
    st.subheader("Amazon — Resumo por Natureza")
    c1, c2, c3 = st.columns(3)
    with c1:
        ano_a = st.number_input("Ano (Amazon)", 2015, 2100, ano, key="ano_amz")
    with c2:
        mes_a = st.number_input("Mês (Amazon)", 1, 12, mes, key="mes_amz")
    with c3:
        reg_a = select_regiao("reg_amz")

    modo = modo_operacao("modo_amz", default="vendas")
    if st.button("Carregar Resumo Amazon"):
        C.acionar_resumo_natureza("amazon", int(ano_a), int(mes_a), reg_a, modo=modo)
        rows = C.carregar_resumo_json("amazon", int(ano_a), int(mes_a), reg_a)
        st.dataframe(rows, use_container_width=True) if rows else st.warning("Resumo não encontrado.")
