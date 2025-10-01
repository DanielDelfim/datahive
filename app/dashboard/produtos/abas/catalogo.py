# app/dashboard/produtos/abas/catalogo.py
import streamlit as st
import pandas as pd

COLS_ORDER = ["sku", "gtin", "titulo", "title", "preco_compra", "custo", "estoque"]

def render(ctx) -> None:
    dados = ctx.produtos or []
    if not dados:
        st.info("Nenhum produto encontrado.")
        return

    st.subheader("Catálogo de produtos (PP)")
    df = pd.DataFrame(dados)
    cols = [c for c in COLS_ORDER if c in df.columns] + [c for c in df.columns if c not in COLS_ORDER]
    df = df[cols]
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Selecionar produto")

    options, idx_map = [], {}
    for i, r in enumerate(dados):
        label = f"{r.get('sku','—')} — {r.get('titulo') or r.get('title') or '(sem título)'}"
        options.append(label)
        idx_map[label] = i

    sel = st.selectbox("Produto", options, index=0, key="prod_sel")
    rec = dados[idx_map[sel]]

    custo = rec.get("preco_compra") if isinstance(rec.get("preco_compra"), (int, float)) else rec.get("custo") or 0.0
    st.number_input("Custo (simulação)", min_value=0.0, step=0.01, value=float(custo))

    c1, c2, c3 = st.columns(3)
    c1.metric("SKU", rec.get("sku", "—"))
    c2.metric("GTIN/EAN", rec.get("gtin", "—"))
    c3.metric("Custo atual", f"{custo:.2f}" if custo else "—")

    st.caption("Observação: a simulação **não grava** alterações; alterações reais devem ser feitas no Excel e atualizadas pelo script.")
