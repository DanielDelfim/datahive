#C:\Apps\Datahive\app\dashboard\precificar_woo\compositor.py
import io
import streamlit as st
import pandas as pd
from app.utils.precificar_woo.service import construir_dataset

def _fmt(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return "—"
    
def _fmt2(v):
    try:
        return round(float(v), 2)
    except Exception:
        return None

def render():
    st.title("Precificação — Site (WooCommerce)")

    doc = construir_dataset()
    itens = doc.get("itens", [])

    # === filtro texto ===
    q = st.text_input("Buscar por GTIN ou nome do produto", "", placeholder="ex.: 789... ou 'eucalipto'")
    if q:
        ql = q.lower().strip()
        itens = [it for it in itens if ql in str(it.get("gtin","")).lower() or ql in str(it.get("title","")).lower()]

    # === dataframe base ===
    cols = ["gtin","title","preco_compra","preco_minimo","preco_maximo",
            "imposto","marketing","frete_sobre_custo","taxa_gateway"]
    df = pd.DataFrame([{c: it.get(c) for c in cols} for it in itens]).rename(columns={
        "gtin":"GTIN","title":"Produto","preco_compra":"Custo (R$)",
        "preco_minimo":"Preço min (R$)","preco_maximo":"Preço máx (R$)",
        "imposto":"Imposto (R$)","marketing":"Marketing (R$)",
        "frete_sobre_custo":"Frete (R$)","taxa_gateway":"Gateway (R$)",
    })
    for c in ["Custo (R$)","Preço min (R$)","Preço máx (R$)","Imposto (R$)","Marketing (R$)","Frete (R$)","Gateway (R$)"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # === data_editor com coluna selecionável ===
    if not df.empty:
        df.insert(0, "Selecionar", False)
        edited = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Selecionar": st.column_config.CheckboxColumn(required=False),
                "Custo (R$)": st.column_config.NumberColumn(format="%.2f"),
                "Preço min (R$)": st.column_config.NumberColumn(format="%.2f"),
                "Preço máx (R$)": st.column_config.NumberColumn(format="%.2f"),
                "Imposto (R$)": st.column_config.NumberColumn(format="%.2f"),
                "Marketing (R$)": st.column_config.NumberColumn(format="%.2f"),
                "Frete (R$)": st.column_config.NumberColumn(format="%.2f"),
                "Gateway (R$)": st.column_config.NumberColumn(format="%.2f"),
            },
            disabled=["GTIN","Produto","Custo (R$)","Preço min (R$)","Preço máx (R$)",
                      "Imposto (R$)","Marketing (R$)","Frete (R$)","Gateway (R$)"],
            key="precificar_woo_editor",
        )
        selected_rows = edited[edited["Selecionar"]]

        # === escolha do "Preço final" a exportar ===

        st.markdown("#### Exportar Excel")

        # base = selecionados (se houver) senão todos visíveis
        base = selected_rows if not selected_rows.empty else edited

        # monta dataframe exatamente com as 4 colunas pedidas
        export_cols = ["Produto", "Custo (R$)", "Preço min (R$)", "Preço máx (R$)"]
        df_exp = base[export_cols].copy()


        # monta dataframe para exportação (selecionados ou todos)
        base = selected_rows if not selected_rows.empty else edited
        export_cols = ["Produto", "Custo (R$)", "Preço min (R$)", "Preço máx (R$)"]
        df_exp = base[export_cols].copy()

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df_exp.to_excel(writer, index=False, sheet_name="Precos")
            wb = writer.book
            ws = writer.sheets["Precos"]
            money = wb.add_format({"num_format": "#,##0.00"})
            ws.set_column("A:A", 40)      # Produto
            ws.set_column("B:D", 14, money)  # Custo / Preço min / Preço máx

        st.download_button(
            label="⬇️ Baixar Excel (Produto, Custo, Preço mín e máx)",
            data=buf.getvalue(),
            file_name="precificacao_site.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # detalhe dos selecionados (opcional, mantém)
        if not selected_rows.empty:
            st.markdown("### Detalhes selecionados")
            for _, row in selected_rows.iterrows():
                st.markdown(f"**{row['Produto'] or row['GTIN']}** — GTIN: `{row['GTIN']}`")
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Custo (R$)", f"{_fmt2(row['Custo (R$)']):.2f}" if pd.notnull(row['Custo (R$)']) else "—")
                c2.metric("Preço mín (R$)", f"{_fmt2(row['Preço min (R$)']):.2f}" if pd.notnull(row['Preço min (R$)']) else "—")
                c3.metric("Preço máx (R$)", f"{_fmt2(row['Preço máx (R$)']):.2f}" if pd.notnull(row['Preço máx (R$)']) else "—")
                c4.metric("Gateway (R$)", f"{_fmt2(row['Gateway (R$)']):.2f}" if pd.notnull(row['Gateway (R$)']) else "—")
                st.divider()
    else:
        st.info("Nenhum item para exibir com o filtro atual.")
