# Home.py
import streamlit as st

st.set_page_config(page_title="Datahive — Home", layout="wide")

st.title("Datahive — Home")
st.caption("Bem-vindo! Esta é a página principal. Use a barra lateral para navegar entre os módulos.")

st.markdown("""
### O que você encontra aqui
- **🧾 Vendas (00):** visão por períodos (7/15/30), SP/MG e BR, cruzamentos e resumos.
- **📣 Anúncios ML (01):** catálogo por MLB, GTIN, preços, rebate e disponibilidade.
- **📦 Produtos (02):** catálogo PP, atributos, custos e simulações.
- **🔁 Replacement (03):** consumo previsto, múltiplo de compra e preço de compra.
- **💸 Precificação (04):** KPIs, lista de anúncios e simulador de MCP por anúncio.
- **📑 Documentos fiscais (05):** consolidações, consultas e conferências por período.
""")

st.divider()
st.subheader("Acesso rápido")

# Grade de atalhos (3 colunas, 2 linhas)
cols = st.columns(3)
with cols[0]:
    st.page_link("pages/00_vendas.py", label="🧾 Ir para Vendas", icon="↗")
with cols[1]:
    st.page_link("pages/01_anuncios_meli.py", label="📣 Ir para Anúncios ML", icon="↗")
with cols[2]:
    st.page_link("pages/02_produtos.py", label="📦 Ir para Produtos", icon="↗")

cols = st.columns(3)
with cols[0]:
    st.page_link("pages/03_replacement.py", label="🔁 Ir para Replacement", icon="↗")
with cols[1]:
    st.page_link("pages/04_precificar.py", label="💸 Ir para Precificar", icon="↗")
with cols[2]:
    st.page_link("pages/05_documentos_fiscais.py", label="📑 Ir para Documentos Fiscais", icon="↗")

# Sidebar com navegação fixa
with st.sidebar:
    st.header("Navegação")
    st.page_link("Home.py", label="🏠 Início")
    st.page_link("pages/00_vendas.py", label="🧾 Vendas")
    st.page_link("pages/01_anuncios_meli.py", label="📣 Anúncios ML")
    st.page_link("pages/02_produtos.py", label="📦 Produtos")
    st.page_link("pages/03_replacement.py", label="🔁 Replacement")
    st.page_link("pages/04_precificar.py", label="💸 Precificar")
    st.page_link("pages/05_documentos_fiscais.py", label="📑 Documentos Fiscais")

st.info(
    "Dica: o Streamlit já cria um menu lateral automático para arquivos dentro de `pages/`. "
    "Os atalhos acima usam `st.page_link` para navegação direta."
)
