# app/dashboard/produtos/abas/catalogo.py
from __future__ import annotations

import json
import pandas as pd
import streamlit as st

# Dashboard consome APENAS service:
from app.utils.produtos.service import listar_produtos_normalizado

def _pretty_money(x):
    try:
        return f"R$ {float(x):.2f}"
    except Exception:
        return "-"

def _pretty_dim(x, unit):
    try:
        return f"{float(x):.2f} {unit}"
    except Exception:
        return "-"

def render(*_args, **_kwargs):
    st.title("Catálogo de Produtos")

    itens = listar_produtos_normalizado()  # dict[sku] -> {campos... enrique-cidos}
    if not itens:
        st.info("Nenhum produto encontrado no PP de Produtos.")
        return

    # DataFrame base sem duplicar sku
    df_full = pd.DataFrame.from_dict(itens, orient="index")
    if "sku" in df_full.columns:
        df_full = df_full.drop(columns=["sku"])
    df_full.index.name = "sku"
    df_full = df_full.reset_index()
    df_full = df_full.loc[:, ~df_full.columns.duplicated()].copy()

    # Colunas na grade
    cols_view = ["gtin", "titulo", "preco_compra", "ncm", "cest", "peso", "altura", "largura", "profundidade"]
    for c in cols_view:
        if c not in df_full.columns:
            df_full[c] = None

    df_view = df_full[cols_view].copy()
    df_view.insert(0, "Selecionar", False)

    col_cfg = {
        "Selecionar": st.column_config.CheckboxColumn("Selecionar", help="Marque para selecionar o produto.", default=False),
        "gtin": st.column_config.TextColumn("GTIN"),
        "titulo": st.column_config.TextColumn("Título"),
        "preco_compra": st.column_config.NumberColumn("Preço compra", step=0.01, format="R$ %.2f"),
        "ncm": st.column_config.TextColumn("NCM"),
        "cest": st.column_config.TextColumn("CEST"),
        "peso": st.column_config.NumberColumn("Peso (kg)", step=0.001),
        "altura": st.column_config.NumberColumn("Altura (cm)", step=0.1),
        "largura": st.column_config.NumberColumn("Largura (cm)", step=0.1),
        "profundidade": st.column_config.NumberColumn("Profundidade (cm)", step=0.1),
    }

    # (2) ---- ler selecionados usando o índice e buscar no df_full ----
    edited = st.data_editor(
        df_view,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config=col_cfg,
    )

    # índices (posições) das linhas marcadas
    selected_idx = edited.index[edited["Selecionar"]].tolist()

    st.divider()
    st.write(f"Selecionados: **{len(selected_idx)}**")

    if selected_idx:
        # pega os registros completos a partir do df_full (que ainda tem 'sku')
        detalhes_df = df_full.iloc[selected_idx]
        detalhes = detalhes_df.to_dict(orient="records")

        for rec in detalhes:
            st.subheader(f"SKU {rec.get('sku','')} — {rec.get('titulo','(sem título)')}")
            resumo = {
                "GTIN": rec.get("gtin", ""),
                "Preço de compra": _pretty_money(rec.get("preco_compra")),
                "NCM": rec.get("ncm", ""),
                "CEST": rec.get("cest", ""),
                "Peso": _pretty_dim(rec.get("peso"), "kg"),
                "Altura": _pretty_dim(rec.get("altura"), "cm"),
                "Largura": _pretty_dim(rec.get("largura"), "cm"),
                "Profundidade": _pretty_dim(rec.get("profundidade"), "cm"),
            }
            st.table(pd.DataFrame([resumo]))
            with st.expander("Ver JSON completo"):
                st.code(json.dumps(rec, ensure_ascii=False, indent=2), language="json")

        texto_json = json.dumps(detalhes, ensure_ascii=False, indent=2)
        st.download_button("⬇️ Baixar JSON", data=texto_json.encode("utf-8"),
                        file_name="produtos_selecionados.json", mime="application/json")
        st.download_button("📝 Baixar TXT", data=texto_json,
                        file_name="produtos_selecionados.txt", mime="text/plain; charset=utf-8")
    else:
        st.info("Selecione um ou mais produtos para ver os detalhes abaixo.")

