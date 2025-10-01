# pages/2_precificacao.py
import streamlit as st

from app.dashboard.precificacao import render_dashboard_precificacao
from app.dashboard.precificacao.context import make_context
from app.config.paths import Regiao  # somente transversal aqui

st.set_page_config(page_title="Precificação — Datahive", layout="wide")

st.title("Precificação (Mercado Livre)")
st.caption("Page casca: sem I/O e sem regra de negócio. Dados vêm de utils/precificacao/service.py")

# --- Filtros de UI ---
col1, col2 = st.columns([1, 3])
with col1:
    regiao_opt = st.selectbox(
        "Região",
        options=[None, Regiao.SP, Regiao.MG],
        format_func=lambda v: "Todas" if v is None else v.value.upper(),
        index=0,
    )
with col2:
    busca = st.text_input("Buscar (mlb/sku/título)", placeholder="Ex.: MLB4100..., 7908..., 'Cera...'")

somente_full = st.checkbox("Somente anúncios FULL", value=False)

# --- Contexto para o dashboard ---
ctx = make_context(regiao=regiao_opt, busca=busca, somente_full=somente_full)

# --- Render das abas ---
render_dashboard_precificacao(ctx)
