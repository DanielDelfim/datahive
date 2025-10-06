from __future__ import annotations
import streamlit as st
import pandas as pd

def render(ctx: dict) -> None:
    st.subheader("Resumo geral")

    df = ctx.get("dataset_df")
    if df is not None and not df.empty:
        st.caption("Dataset de precificação consolidado (após scripts).")
        st.dataframe(df.head(500), use_container_width=True)
    else:
        st.info("Ainda não há dataset consolidado. Rode os scripts na parte superior da página.")

        # Fallback: tentar exibir Anúncios + Preço de compra por GTIN
        ads_df = ctx.get("anuncios_df")
        if ads_df is None:
            ads_df = pd.DataFrame()

        buy_df = ctx.get("produtos_df")
        if buy_df is None:
            buy_df = pd.DataFrame()

        if (not ads_df.empty) and (not buy_df.empty):
            if ("gtin" in ads_df.columns) and ("gtin" in buy_df.columns):
                merged = ads_df.merge(
                    buy_df[["gtin", "preco_compra"]],
                    on="gtin",
                    how="left",
                )
                st.dataframe(merged.head(500), use_container_width=True)
            else:
                st.warning("Coluna 'gtin' ausente em anúncios e/ou produtos; não foi possível juntar as bases.")
