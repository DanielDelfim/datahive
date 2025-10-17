# app/dashboard/produtos/abas/catalogo.py
from __future__ import annotations
import json
import pandas as pd
import streamlit as st

def render(ctx):
    """
    Aba Catálogo — consome ctx.produtos (já filtrado por região/busca/custo).
    - Faz flatten dos campos aninhados: pesos_g.{liq,bruto}, dimensoes_cm.{altura,largura,profundidade}
    - Exibe grade com seleção e detalhes dos itens marcados.
    """
    st.title("Catálogo de Produtos")

    itens = ctx.produtos or []
    if not itens:
        st.info("Nenhum produto encontrado no PP de Produtos.")
        return

    # ------- DataFrame base -------
    df_full = pd.DataFrame(itens)
    if "sku" not in df_full.columns:
        df_full["sku"] = None
    # remove colunas duplicadas (Streamlit Data Editor exige nomes únicos)
    df_full = df_full.loc[:, ~df_full.columns.duplicated()].copy()

    # ------- Garantir/normalizar colunas de visualização -------
    cols_view = ["gtin", "titulo", "preco_compra", "ncm", "cest",
                 "peso", "altura", "largura", "profundidade"]
    for c in cols_view:
        if c not in df_full.columns:
            df_full[c] = None

    # helper p/ buscar chave aninhada com segurança
    def _get(d, *path, default=None):
        try:
            x = d or {}
            for p in path:
                x = x.get(p) if isinstance(x, dict) else None
            return default if x is None else x
        except Exception:
            return default

    # ---- FLATTEN: preencher peso/dimensões a partir de campos aninhados ----
    if "pesos_g" in df_full.columns:
        # prioriza peso já existente; se None, usa líquido (ou bruto, se preferir)
        df_full["peso"] = df_full["peso"].where(
            df_full["peso"].notna(),
            df_full["pesos_g"].apply(lambda d: _get(d, "liq"))
        )
        # exemplo se quiser cair para bruto quando liq estiver ausente:
        df_full["peso"] = df_full["peso"].where(
            df_full["peso"].notna(),
            df_full["pesos_g"].apply(lambda d: _get(d, "bruto"))
        )

    if "dimensoes_cm" in df_full.columns:
        for campo in ["altura", "largura", "profundidade"]:
            df_full[campo] = df_full[campo].where(
                df_full[campo].notna(),
                df_full["dimensoes_cm"].apply(lambda d: _get(d, campo))
            )

    # ------- View da grade -------
    df_view = df_full[cols_view].copy()
    df_view.insert(0, "Selecionar", False)

    col_cfg = {
        "Selecionar": st.column_config.CheckboxColumn(
            "Selecionar", help="Marque para selecionar o produto.", default=False
        ),
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

    edited = st.data_editor(
        df_view,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config=col_cfg,
    )

    # ------- Seleção e detalhes -------
    selected_idx = edited.index[edited["Selecionar"]].tolist()
    st.divider()
    st.write(f"Selecionados: **{len(selected_idx)}**")

    if not selected_idx:
        st.info("Selecione um ou mais produtos para ver os detalhes abaixo.")
        return

    detalhes_df = df_full.iloc[selected_idx]
    detalhes = detalhes_df.to_dict(orient="records")

    def _fmt_money(x):
        try:
            return f"R$ {float(x):.2f}"
        except Exception:
            return "-"

    def _fmt_num(x, unit=""):
        try:
            v = float(x)
            return f"{v:.3f} {unit}".strip()
        except Exception:
            return "-"

    for rec in detalhes:
        st.subheader(f"{rec.get('titulo','(sem título)')}")
        resumo = {
            "GTIN": rec.get("gtin", ""),
            "Preço de compra": _fmt_money(rec.get("preco_compra")),
            "NCM": rec.get("ncm", ""),
            "CEST": rec.get("cest", ""),
            "Peso": _fmt_num(rec.get("peso"), "kg"),
            "Altura": _fmt_num(rec.get("altura"), "cm"),
            "Largura": _fmt_num(rec.get("largura"), "cm"),
            "Profundidade": _fmt_num(rec.get("profundidade"), "cm"),
        }
        st.table(pd.DataFrame([resumo]))

        with st.expander("Ver JSON completo"):
            st.code(json.dumps(rec, ensure_ascii=False, indent=2), language="json")

    # downloads dos selecionados
    texto_json = json.dumps(detalhes, ensure_ascii=False, indent=2)
    st.download_button("⬇️ Baixar JSON", data=texto_json.encode("utf-8"),
                       file_name="produtos_selecionados.json", mime="application/json")
    st.download_button("📝 Baixar TXT", data=texto_json,
                       file_name="produtos_selecionados.txt", mime="text/plain; charset=utf-8")
