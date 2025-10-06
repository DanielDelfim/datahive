from __future__ import annotations
import streamlit as st
from app.dashboard.tax_documents.ui import ano_mes_defaults, select_regiao
from app.dashboard.tax_documents import compositor as C
from app.dashboard.tax_documents.tabs import meli as tab_meli
from app.dashboard.tax_documents.tabs import amazon as tab_amz
from app.dashboard.tax_documents.tabs import bling as tab_bling
from app.dashboard.tax_documents.tabs import consolidado as tab_all

st.set_page_config(page_title="04 · Documentos Fiscais", layout="wide")
st.title("📄 Documentos Fiscais")
st.caption("Casca: UI mínima. Toda a lógica está no dashboard.")

ano, mes = ano_mes_defaults()

# Header principal — somente botões/inputs e orquestração
with st.container():
    st.subheader("Principal")
    col1, col2, col3, col4 = st.columns([1,1,1,2], gap="large")
    with col1:
        ano = st.number_input("Ano", 2015, 2100, ano, step=1)
    with col2:
        mes = st.number_input("Mês", 1, 12, mes, step=1)
    with col3:
        prov = st.selectbox("Provedor", options=["meli","amazon","bling"], index=0)
    with col4:
        reg = select_regiao("main_reg") if prov in ("meli","amazon") else None

    c1, c2 = st.columns([1,3])
    with c1:
        if st.button("➡️ Gerar PP (JSON)"):
            try:
                path = C.acionar_geracao_pp_json(prov, int(ano), int(mes), reg)
                st.success(f"Gerado: {path}")
            except Exception as e:
                st.error(f"Falha ao gerar PP: {e}")
    with c2:
        if st.button("📊 Gerar/Atualizar Resumo (from PP)"):
            try:
                path = C.acionar_resumo_natureza(prov, int(ano), int(mes), reg, modo="todos")
                st.success(f"Resumo: {path}")
            except Exception as e:
                st.error(f"Falha ao gerar resumo: {e}")

st.divider()

# Abas — cada uma renderiza seu conteúdo via módulo dedicado
t1, t2, t3, t4 = st.tabs(["Meli","Amazon","Bling","Consolidado"])
with t1:
    tab_meli.render(ano, mes)
with t2:
    tab_amz.render(ano, mes)
with t3:
    tab_bling.render(ano, mes)
with t4:
    tab_all.render(ano, mes)
