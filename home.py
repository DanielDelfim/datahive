# Home.py
import streamlit as st

st.set_page_config(page_title="Datahive — Home", layout="wide")

st.title("Datahive — Home")
st.caption("Bem-vindo! Esta é a página principal. Use a barra lateral para navegar entre os módulos.")

st.markdown("""
### O que você encontra aqui
- **💸 Precificação (Mercado Livre):** KPIs, lista de anúncios e simulação de MCP por anúncio.
- **📦 Produtos (Catálogo PP):** visão geral do PP, tabela do catálogo, seleção e simulação de custo.
""")

st.divider()
st.subheader("Acesso rápido")
st.write("Você também pode usar os atalhos abaixo:")

# Atalhos na área principal (opcional)
col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/2_precificacao.py", label="💸 Ir para Precificação", icon="↗")
with col2:
    st.page_link("pages/3_produtos.py", label="📦 Ir para Produtos", icon="↗")

# Sidebar com navegação (fica fixo à esquerda)
with st.sidebar:
    st.header("Navegação")
    st.page_link("Home.py", label="🏠 Início")
    st.page_link("pages/2_precificacao.py", label="💸 Precificação")
    st.page_link("pages/3_produtos.py", label="📦 Produtos")

st.info("Dica: o Streamlit já oferece menu lateral automático para arquivos na pasta `pages/`. "
        "Os botões acima usam `st.page_link` para ir direto aos módulos.")
