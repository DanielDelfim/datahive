import os, subprocess, sys
import streamlit as st
from app.dashboard.produtos import render_dashboard_produtos
from app.dashboard.produtos.context import make_context
from app.config.paths import Regiao

st.set_page_config(page_title="Produtos — Datahive", layout="wide")
st.title("Produtos (Catálogo PP)")
st.caption("Page casca: sem I/O; leitura via utils/produtos/service.py; atualização via script autor do JSON.")

# --- Ação principal (no topo) ---
colA, colB = st.columns([1, 2])
with colA:
    if st.button("🔁 Atualizar PP a partir do Excel", use_container_width=True):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        with st.spinner("Atualizando PP..."):
            cmd = [sys.executable, "scripts/produtos/gerar_produtos_pp.py",
                   "--to-file", "--stdout", "--keep", "5", "--filename", "produtos.json"]
            res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if res.returncode == 0:
            st.success("PP atualizado com sucesso pelo script.")
            if res.stdout:
                with st.expander("Ver log"):
                    st.code(res.stdout)
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Falha ao atualizar PP pelo script.")
            if res.stderr or res.stdout:
                with st.expander("Detalhes do erro"):
                    st.code(res.stderr or res.stdout)
with colB:
    st.caption("O botão executa o *script autor* (backup atômico + rotação pelo JsonFileSink). A page não escreve em disco.")

st.divider()

# --- Filtros (agora afetam o contexto da tabela) ---
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    regiao_opt = st.selectbox(
        "Região (opcional)",
        options=[None, Regiao.SP, Regiao.MG],
        format_func=lambda v: "Todas" if v is None else v.value.upper(),
        index=0,
    )
with col2:
    busca = st.text_input("Buscar (sku/gtin/título)", placeholder="Ex.: 7908..., GTIN/EAN, 'Cera...'")
with col3:
    somente_com_custo = st.checkbox("Somente com custo", value=False)

# --- Contexto + dashboard ---
ctx = make_context(regiao=regiao_opt, busca=busca, somente_com_custo=somente_com_custo)
render_dashboard_produtos(ctx)
