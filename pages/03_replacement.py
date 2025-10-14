# pages/03_replacement.py
from __future__ import annotations
import io
import pandas as pd
import streamlit as st

from app.dashboard.replacement.compositor import (
    anuncios_por_mlb,
    resumo_br_gtin_enriquecido,
    filtrar_rows_por_texto,
    colunas_tabela_sugeridas,
)

PAGE_TITLE = "📦 Reposição & Anúncios"

def _to_dataframe(rows, cols=None):
    df = pd.DataFrame(rows or [])
    if cols:
        cols = [c for c in cols if c in df.columns]
        if cols:
            df = df[cols]
    if df.shape[1] == 0:
        return pd.DataFrame({"_vazio": []})
    df = df.loc[:, ~df.columns.duplicated()].reset_index(drop=True)
    df.index.name = None
    return df

def _download_xlsx(df: pd.DataFrame, fname: str, key: str, sheet_name: str = "dados"):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    st.download_button("📥 Baixar Excel (.xlsx)", bio.getvalue(), fname,
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=key)

def _render_aba_anuncios():
    st.subheader("Anúncios SP & MG — por MLB (sem acumular por GTIN)")
    escolha = st.radio("Região", ["SP", "MG", "Ambos"], horizontal=True)

    # compositor faz TODO o enriquecimento
    reg = escolha.lower() if escolha != "Ambos" else "ambos"
    rows, key_by = anuncios_por_mlb(reg)

    filtro = st.text_input("Buscar por GTIN/EAN/Barcode, Título ou SKU (MLB)",
                           placeholder="Ex.: 789..., 'laranjeira', MLB123...").strip()
    rows_f = filtrar_rows_por_texto(rows, filtro)

    cols = colunas_tabela_sugeridas(key_by)
    df = _to_dataframe(rows_f, cols)
    if df.empty or (df.shape[1] == 1 and df.columns.tolist() == ["_vazio"]):
        st.info("Nenhum item para mostrar.")
        return

    _download_xlsx(df, f"anuncios_{reg}.xlsx", f"dl_{reg}", f"anuncios_{reg}")
    st.dataframe(df, use_container_width=True, height=560)

def _render_aba_br():
    st.subheader("Resumo BR (GTIN agregado)")
    rows, key_by = resumo_br_gtin_enriquecido()

    filtro = st.text_input("Buscar por GTIN/EAN/Barcode, Título ou SKU (MLB)",
                           placeholder="Ex.: 789..., 'laranjeira'").strip()
    rows_f = filtrar_rows_por_texto(rows, filtro)

    cols = colunas_tabela_sugeridas(key_by)
    df = _to_dataframe(rows_f, cols)
    if df.empty or (df.shape[1] == 1 and df.columns.tolist() == ["_vazio"]):
        st.info("Nenhum item para mostrar.")
        return

    _download_xlsx(df, "resumo_br_gtin.xlsx", "dl_br", "resumo_br")
    st.dataframe(df, use_container_width=True, height=560)

def main():
    st.title(PAGE_TITLE)
    tab1, tab2 = st.tabs(["Anúncios SP & MG (MLB)", "Resumo BR (GTIN)"])
    with tab1: _render_aba_anuncios()
    with tab2: _render_aba_br()

if __name__ == "__main__":
    main()
