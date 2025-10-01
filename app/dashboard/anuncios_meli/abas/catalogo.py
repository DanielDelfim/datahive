# app/dashboard/anuncios_meli/abas/catalogo.py
import streamlit as st
import pandas as pd

COLS = [
    "mlb","sku","gtin","title","price","rebate_price",
    "original_price","status","logistic_type","estoque"
]

def render(ctx) -> None:
    rows = ctx.registros or []
    if not rows:
        st.info("Nenhum anúncio encontrado.")
        return

    st.subheader("Catálogo de anúncios (PP)")
    df = pd.DataFrame(rows)
    cols = [c for c in COLS if c in df.columns] + [c for c in df.columns if c not in COLS]
    st.dataframe(df[cols], hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Selecionar anúncio")

    options, idx = [], {}
    for i, r in enumerate(rows):
        label = f"{r.get('mlb','—')} — {r.get('title','(sem título)')}"
        options.append(label)
        idx[label] = i
    if not options:
        st.info("Sem anúncios para selecionar.")
        return

    sel = st.selectbox("Anúncio", options, index=0)
    rec = rows[idx[sel]]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MLB", rec.get("mlb","—"))
    c2.metric("SKU", rec.get("sku","—"))
    c3.metric("GTIN", rec.get("gtin","—"))
    c4.metric("Status", rec.get("status","—"))

    st.json(rec)
