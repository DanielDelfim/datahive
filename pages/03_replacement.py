import streamlit as st
import pandas as pd
import io
from app.dashboard.replacement.compositor import resumo_sp_mlb, resumo_mg_mlb, resumo_br_gtin
from app.utils.replacement.service import map_mlb_to_gtin
from app.utils.produtos.service import get_por_gtin as produto_por_gtin, get_pack_info_por_gtin

st.set_page_config(page_title="Reposição — Estimativa", layout="wide")
st.title("Reposição — Projeções (SP/MG por MLB • BR por GTIN)")
st.caption("Pesos 45/35/20 sobre janelas 7/15/30; lead time 7 dias com clamp a zero.")

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
        out.append(r2)
    return out

def _render_table_select(rows, titulo: str, *, key_ns: str, key_by: str, mlb_to_gtin: dict[str,str] | None=None):
    if not rows:
        st.info("Sem dados.")
        return
    st.markdown(f"**{titulo}**")

    rows = _enriquecer_com_produto(rows, key_by=key_by, mlb_to_gtin=mlb_to_gtin)
    df = pd.DataFrame(rows)

    # colunas por contexto
    if key_by == "mlb":
        cols = ["mlb","title","multiplo_compra","preco_compra","estimado_30","estimado_60",
                "consumo_previsto_7d_lead","estoque_atual","estoque_pos_delay_7"]
    else:  # gtin
        cols = ["gtin","title","multiplo_compra","preco_compra","estimado_30","estimado_60",
                "consumo_previsto_7d_lead","estoque_atual","estoque_pos_delay_7"]
    cols = [c for c in cols if c in df.columns]
    shown = df[cols] if cols else df

    # download Excel/CSV
    # ----- Download apenas XLSX -----

    bio = io.BytesIO()

    # Nota: use "xlsxwriter" (recomendado) ou "openpyxl" se preferir.
    # Se nenhum engine estiver instalado, o pandas vai lançar exceção.
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        shown.to_excel(writer, index=False, sheet_name="reposicao")               
               

    st.download_button(                                                                                      
        label="📥 Baixar Excel (.xlsx)",
        data=bio.getvalue(),
        file_name=f"reposicao_{key_ns}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_xlsx_{key_ns}",
    )
    
    st.dataframe(shown, use_container_width=True, height=520)

    # seleção (usa chave principal)
    options = []
    for r in rows:
        key = str(r.get(key_by) or "").strip()
        if not key:
            continue
        label = f"{key} — {r.get('title','')}"
        options.append((label, key))
    if not options:
        st.info("Sem itens selecionáveis.")
        return
    _, sel_key = st.selectbox("Selecione um item", options, index=0, key=f"sel_{key_ns}",
                              format_func=lambda t: t[0])

    # detalhe (linha + produto via GTIN)
    linha = next((r for r in rows if str(r.get(key_by) or "") == sel_key), None)
    gtin_lookup = None
    if key_by == "mlb":
        gtin_lookup = (mlb_to_gtin or {}).get(sel_key)
    else:
        gtin_lookup = linha.get("gtin") if linha else None
    produto = produto_por_gtin(gtin_lookup) if gtin_lookup else {}
    pack_info = get_pack_info_por_gtin(gtin_lookup) if gtin_lookup else {}

    st.markdown("**Detalhes selecionados**")
    st.json({
        key_by: sel_key,
        "replacement_row": linha or {},
        "gtin_resolvido": gtin_lookup,
        "produto": produto or {},
        "produto_pack_info": pack_info or {},
    })

# ---- ABAS ----
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
