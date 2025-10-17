#C:\Apps\Datahive\pages\03_replacement.py
import streamlit as st
import pandas as pd
import io

from app.dashboard.replacement.compositor import resumo_sp_mlb, resumo_mg_mlb, resumo_br_gtin
from app.utils.replacement.service import map_mlb_to_gtin
from app.utils.produtos.service import get_por_gtin as produto_por_gtin, get_pack_info_por_gtin

st.set_page_config(page_title="Reposição — Estimativa", layout="wide")
st.title("Reposição — Projeções (SP/MG por MLB • BR por GTIN)")
st.caption("Pesos 45/35/20 sobre janelas 7/15/30; lead time 7 dias com clamp a zero.")

# ---------------------- Filtro global ----------------------
filtro_txt = st.text_input("🔎 Filtro (nome, GTIN ou MLB)", value="", placeholder="Ex.: laranjeira 500g, 789..., MLB...").strip().lower()

def _enriquecer_com_produto(rows, *, key_by: str, mlb_to_gtin: dict[str,str] | None=None):
    out = []
    for r in rows:
        r2 = dict(r)
        gtin_key = r.get("gtin")
        if key_by == "mlb":
            mlb = str(r.get("mlb") or "")
            gtin_key = (mlb_to_gtin or {}).get(mlb)
        if gtin_key:
            p = produto_por_gtin(gtin_key) or {}
            pk = get_pack_info_por_gtin(gtin_key) or {}
            r2["multiplo_compra"] = pk.get("multiplo_compra", p.get("multiplo_compra"))
            r2["preco_compra"] = pk.get("preco_compra", p.get("preco_compra"))
            r2["gtin"] = gtin_key if not r2.get("gtin") else r2.get("gtin")
        out.append(r2)
    return out

def _aplicar_filtro_df(df: pd.DataFrame) -> pd.DataFrame:
    if not filtro_txt:
        return df
    cols_possiveis = [c for c in ["title", "gtin", "mlb"] if c in df.columns]
    if not cols_possiveis:
        return df
    mask = False
    for c in cols_possiveis:
        mask = mask | df[c].astype(str).str.lower().str.contains(filtro_txt, na=False)
    return df[mask]

def _render_table_select(rows, titulo: str, *, key_ns: str, key_by: str, mlb_to_gtin: dict[str,str] | None=None):
    if not rows:
        st.info("Sem dados.")
        return

    st.markdown(f"**{titulo}**")
    rows = _enriquecer_com_produto(rows, key_by=key_by, mlb_to_gtin=mlb_to_gtin)
    df = pd.DataFrame(rows)

    # colunas por contexto
    if key_by == "mlb":
        cols = [
            "mlb","title","gtin","multiplo_compra","preco_compra",
            "sold_7","sold_15","sold_30",
            "venda_prevista_30","venda_prevista_60",         
            "reposicao_sugerida_30","reposicao_sugerida_60",  
            "estoque_atual","estoque_pos_delay_7",
        ]

    else:  # gtin
        cols = [
            "gtin","title","multiplo_compra","preco_compra",
            "sold_7","sold_15","sold_30",
            "venda_prevista_30","venda_prevista_60",          
            "reposicao_sugerida_30","reposicao_sugerida_60",  
            "estoque_atual","estoque_pos_delay_7",
        ]

    cols = [c for c in cols if c in df.columns]
    shown = df[cols] if cols else df

    # ---- aplicar filtro de texto ----
    shown = _aplicar_filtro_df(shown)

    if shown.empty:
        st.warning("Nenhum item encontrado para o filtro informado.")
        return

    # ---- coluna de seleção (checkbox) ----
    if "Selecionar" not in shown.columns:
        shown = shown.copy()
        shown.insert(0, "Selecionar", False)

    # Editor com seleção por checkbox (impomos single-select depois)
    edited = st.data_editor(
        shown,
        use_container_width=True,
        height=520,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Selecionar", help="Marque 1 item para detalhar"),
        },
        disabled=[c for c in shown.columns if c != "Selecionar"],  # evita edição acidental
        key=f"editor_{key_ns}",
    )

    # garantir single-select
    sel_rows = edited.index[edited["Selecionar"]].tolist()
    if len(sel_rows) > 1:
        # mantém somente o último marcado visualmente
        keep = sel_rows[-1]
        edited.loc[edited.index != keep, "Selecionar"] = False
        sel_rows = [keep]

    # ---- botão de download (sem a coluna Selecionar) ----
    export_df = edited.drop(columns=["Selecionar"], errors="ignore")
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="reposicao")
    st.download_button(
        label="📥 Baixar Excel (.xlsx)",
        data=bio.getvalue(),
        file_name=f"reposicao_{key_ns}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_xlsx_{key_ns}",
    )

    # ---- detalhe do item selecionado ----
    if not sel_rows:
        st.info("Selecione um item na coluna **Selecionar** para ver o detalhe.")
        return

    # pega a linha (primeira/única) selecionada
    linha = edited.loc[sel_rows[0]].drop(labels=["Selecionar"], errors="ignore").to_dict()

    # chave principal e GTIN resolvido
    sel_key = linha.get(key_by)
    gtin_lookup = linha.get("gtin") if key_by == "gtin" else (mlb_to_gtin or {}).get(sel_key)

    # produto vinculado (enriquece mais detalhes, se existir)
    produto = produto_por_gtin(gtin_lookup) if gtin_lookup else {}
    pack_info = get_pack_info_por_gtin(gtin_lookup) if gtin_lookup else {}

    st.markdown("### 📊 Detalhes do selecionado")
    # ... onde renderiza os KPIs do item selecionado:
    # KPIs (detalhe do item selecionado)
    prev30 = linha.get("venda_prevista_30", linha.get("estimado_30", 0))
    prev60 = linha.get("venda_prevista_60", linha.get("estimado_60", 0))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Vendas 7d", f'{linha.get("sold_7", 0):,.0f}')
    c2.metric("Vendas 15d", f'{linha.get("sold_15", 0):,.0f}')
    c3.metric("Vendas 30d", f'{linha.get("sold_30", 0):,.0f}')
    c4.metric("Venda prevista 30d", f'{prev30:,.0f}')
    c5.metric("Venda prevista 60d", f'{prev60:,.0f}')

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Estoque atual", f'{linha.get("estoque_atual", 0):,.0f}')
    c7.metric("Estoque pós lead (7d)", f'{linha.get("estoque_pos_delay_7", 0):,.0f}')
    c8.metric("Reposição sugerida 30d", f'{linha.get("reposicao_sugerida_30", linha.get("compra_sugerida_30", 0)):,.0f}')
    c9.metric("Reposição sugerida 60d", f'{linha.get("reposicao_sugerida_60", linha.get("compra_sugerida_60", 0)):,.0f}')



    with st.expander("Ver JSON bruto (linha + produto)"):
        st.json({
            key_by: sel_key,
            "gtin_resolvido": gtin_lookup,
            "replacement_row": linha or {},
            "produto": produto or {},
            "produto_pack_info": pack_info or {},
        })

# ---------------------- ABAS ----------------------
tabs = st.tabs(["SP (por MLB)", "MG (por MLB)", "BR (GTIN)"])

with tabs[0]:
    st.subheader("São Paulo — MLB")
    mapa_sp = map_mlb_to_gtin("sp")  # para enriquecer produto
    _render_table_select(resumo_sp_mlb(), "Tabela — SP por MLB", key_ns="sp", key_by="mlb", mlb_to_gtin=mapa_sp)

with tabs[1]:
    st.subheader("Minas Gerais — MLB")
    mapa_mg = map_mlb_to_gtin("mg")
    _render_table_select(resumo_mg_mlb(), "Tabela — MG por MLB", key_ns="mg", key_by="mlb", mlb_to_gtin=mapa_mg)

with tabs[2]:
    st.subheader("Brasil — GTIN (SP+MG)")
    _render_table_select(resumo_br_gtin(), "Tabela — BR (GTIN)", key_ns="br", key_by="gtin")
