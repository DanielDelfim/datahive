from __future__ import annotations
import streamlit as st
from app.dashboard.tax_documents import compositor as C
from app.dashboard.tax_documents.ui import select_regiao, modo_operacao

def render(ano: int, mes: int):
    st.subheader("Meli — Resumo por Natureza")
    c1, c2, c3 = st.columns(3)
    with c1:
        ano_m = st.number_input("Ano (Meli)", 2015, 2100, ano, key="ano_meli")
    with c2:
        mes_m = st.number_input("Mês (Meli)", 1, 12, mes, key="mes_meli")
    with c3:
        reg_m = select_regiao("reg_meli")

    modo = modo_operacao("modo_meli", default="vendas")
    if st.button("Carregar Resumo Meli"):
        # gera/atualiza resumo conforme modo
        C.acionar_resumo_natureza("meli", int(ano_m), int(mes_m), reg_m, modo=modo)
        rows = C.carregar_resumo_json("meli", int(ano_m), int(mes_m), reg_m)
        if not rows:
            st.warning("Resumo não encontrado para o período/região.")
        else:
            st.dataframe(rows, use_container_width=True)
