from __future__ import annotations
import math
import streamlit as st
import pandas as pd
from app.utils.precificacao.validators import validar_insumos_mcp

def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x))

def _fmt_money(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "—"

def _fmt_pct(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    try:
        return f"{100.0*float(x):.1f}%"
    except Exception:
        return ""

def render(ctx: dict) -> None:
    st.subheader("Anúncios — SP + MG")

    df_all = ctx.get("dataset_df_all")
    if not isinstance(df_all, pd.DataFrame) or df_all.empty:
        st.warning("Nenhum anúncio encontrado em SP/MG. Rode os scripts e/ou confirme as regiões.")
        return

    # ---------- Filtros ----------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_vals = sorted(df_all["status"].dropna().unique().tolist()) if "status" in df_all.columns else []
        status = st.multiselect("Status", status_vals, default=[])
    with col2:
        logistic_vals = sorted(df_all["logistic_type"].dropna().unique().tolist()) if "logistic_type" in df_all.columns else []
        default_log = ["fulfillment"] if "fulfillment" in logistic_vals else []
        logistic = st.multiselect("Logística", logistic_vals, default=default_log)
    with col3:
        reg_vals_all = ["sp", "mg"]  # sempre disponíveis
        present_regs = sorted(df_all["regiao"].dropna().unique().tolist()) if "regiao" in df_all.columns else []
        default_regs = present_regs if present_regs else reg_vals_all
        regs = st.multiselect("Região", reg_vals_all, default=default_regs)
    with col4:
        if "price" in df_all.columns and df_all["price"].notna().any():
            pmin = float(df_all["price"].dropna().min())
            pmax = float(df_all["price"].dropna().max())
            price_min, price_max = st.slider("Faixa de preço", pmin, pmax, value=(pmin, pmax))
        else:
            st.caption("Sem coluna/valores de preço; filtro desativado.")
            price_min, price_max = None, None

    q = st.text_input("Filtro textual (título/MLB/SKU/GTIN)")

    # ---------- Aplicação de filtros ----------
    f = df_all.copy()
    if status and "status" in f.columns:
        f = f[f["status"].isin(status)]
    if logistic and "logistic_type" in f.columns:
        f = f[f["logistic_type"].isin(logistic)]
    if regs and "regiao" in f.columns:
        f = f[f["regiao"].isin(regs)]
    if price_min is not None and price_max is not None and "price" in f.columns:
        f = f[f["price"].between(price_min, price_max, inclusive="both")]
    if q:
        ql = q.lower()
        cols_busca = [c for c in ["title","titulo_anuncio","mlb","seller_sku","sku","gtin"] if c in f.columns]
        if cols_busca:
            f = f[f[cols_busca].astype(str).apply(lambda r: any(ql in str(v).lower() for v in r.values), axis=1)]

    # ---------- Tabela principal com seleção direta ----------
    cols_show = [c for c in ["regiao","mlb","sku","gtin","title","price","rebate_price_discounted","status","logistic_type"] if c in f.columns]
    df_view = f[cols_show].copy() if cols_show else f.copy()

    # coalesce de rebate para exibir uma coluna amigável
    if "rebate_price_discounted" in df_view.columns:
        df_view = df_view.rename(columns={"rebate_price_discounted": "rebate_price"})
    elif "rebate_price_all_methods" in df_view.columns:
        df_view = df_view.rename(columns={"rebate_price_all_methods": "rebate_price"})
    else:
        df_view["rebate_price"] = None

    df_view = df_view.reset_index(drop=True)
    df_view.insert(0, "Selecionar", False)

    edited = st.data_editor(
        df_view,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(help="Marque uma linha para selecionar o anúncio."),
            "price": st.column_config.NumberColumn(format="%.2f"),
            "rebate_price": st.column_config.NumberColumn(format="%.2f"),
        },
        key="tabela_principal_editor",
    )

    # se exatamente 1 linha marcada, usamos o MLB daquela linha
    selecionados = edited.index[edited["Selecionar"]].tolist()
    sel_mlb = None
    if len(selecionados) == 1:
        try:
            sel_mlb = str(edited.loc[selecionados[0], "mlb"])
        except Exception:
            sel_mlb = None

    # fallback para selectbox se nada (ou >1) selecionado na tabela
    if not sel_mlb:
        mlbs = f["mlb"].dropna().astype(str).unique().tolist() if "mlb" in f.columns else []
        if not mlbs:
            st.info("Nenhum MLB disponível após os filtros aplicados.")
            return
        sel_mlb = st.selectbox("Selecionar anúncio (MLB)", options=mlbs, index=0)

    sel_rows = f[f["mlb"].astype(str) == str(sel_mlb)]
    if sel_rows.empty:
        st.info("Nenhuma linha encontrada para o anúncio selecionado.")
        return
    row = sel_rows.iloc[0].to_dict()

    # === Tabela: anúncios com o mesmo GTIN ===
    st.markdown("#### Anúncios com o mesmo GTIN")
    gtin_sel = str(row.get("gtin") or "").strip()
    if gtin_sel and isinstance(df_all, pd.DataFrame) and not df_all.empty:
        df_same = df_all[df_all["gtin"].astype(str) == gtin_sel].copy()
        if not df_same.empty:
            for col in ("rebate_price_discounted","rebate_price_all_methods","deal_price","sale_price"):
                if col not in df_same.columns:
                    df_same[col] = None
            df_same["rebate_price"] = (
                df_same["rebate_price_discounted"]
                .fillna(df_same["rebate_price_all_methods"])
                .fillna(df_same["deal_price"])
                .fillna(df_same["sale_price"])
            )
            cols = [c for c in ["mlb","title","regiao","price","rebate_price"] if (c in df_same.columns or c=="rebate_price")]
            if "regiao" in df_same.columns:
                df_same["regiao"] = df_same["regiao"].astype(str).str.lower()
                df_same = df_same.sort_values(["regiao","price"], ascending=[True, False])
            else:
                df_same = df_same.sort_values(["mlb"])
            df_show = df_same[cols].copy()
            for col in ("price","rebate_price"):
                if col in df_show.columns:
                    df_show[col] = pd.to_numeric(df_show[col], errors="coerce").map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")

            # tabela clicável para trocar o anúncio em foco
            df_same_view = df_show.rename(columns={
                "mlb":"MLB","title":"Título","regiao":"Região","price":"Preço (R$)","rebate_price":"Preço com rebate (R$)"
            }).copy()
            df_same_view.insert(0, "Selecionar", False)
            edited_same = st.data_editor(
                df_same_view, use_container_width=True, hide_index=True, num_rows="fixed",
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn(help="Marque uma linha para focar o anúncio."),
                    "Preço (R$)": st.column_config.NumberColumn(format="%.2f"),
                    "Preço com rebate (R$)": st.column_config.NumberColumn(format="%.2f"),
                },
                key="tabela_mesmo_gtin_editor",
            )
            sel_same = edited_same.index[edited_same["Selecionar"]].tolist()
            if len(sel_same) == 1:
                try:
                    novo_mlb = str(edited_same.loc[sel_same[0], "MLB"])
                    if novo_mlb:
                        sel_mlb = novo_mlb
                        sel_rows = f[f["mlb"].astype(str) == sel_mlb]
                        if not sel_rows.empty:
                            row = sel_rows.iloc[0].to_dict()
                except Exception:
                    pass
        else:
            st.info("Nenhum outro anúncio encontrado com o mesmo GTIN.")
    else:
        st.caption("GTIN ausente neste item — tabela não aplicável.")

    # ---------- Avisos do validator ----------
    warns = row.get("warnings")
    if not warns:
        faltas = validar_insumos_mcp(row)
        if faltas:
            warns = [f"MCP: insumos ausentes: {', '.join(faltas)}"]
    if warns:
        if isinstance(warns, list):
            for w in warns:
                st.warning(str(w))
        else:
            st.warning(str(warns))

    # ---------- Cards (apenas valores do dataset) ----------
    st.markdown("---")
    st.subheader("Métricas & Preços-alvo")
    title = row.get("title") or row.get("titulo_anuncio") or "—"
    st.markdown(f"**Título:** {title}")

    # Simulador logo após o título
    st.markdown("#### Simulador de MCP (preço + subsídio)")
    col_sim1, col_sim2, col_sim3, col_sim4 = st.columns([1,1,1,1])
    with col_sim1:
        sim_preco = st.number_input("Preço simulado (R$)", min_value=0.0, value=float(row.get("price") or 0.0), step=0.01, format="%.2f")
    with col_sim2:
        sim_sub = st.number_input("Subsídio ML (R$)", min_value=0.0, value=float(row.get("subsidio_ml_valor") or 0.0), step=0.01, format="%.2f")
    with col_sim3:
        go = st.button("Calcular MCP simulado", use_container_width=True)
    with col_sim4:
        st.caption("Usa percentuais do YAML por logística e custo fixo por faixa.")

    if go:
        from app.utils.precificacao.simulator import simular_mcp_item
        sim = simular_mcp_item(row, preco_venda=sim_preco, subsidio_valor=sim_sub)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("MCP simulado (R$)", f"{(sim.get('mcp_abs') or 0):.2f}")
        with c2:
            mcpp = sim.get("mcp_pct")
            st.metric("MCP simulado (%)", f"{(100*mcpp):.1f}%" if isinstance(mcpp,(int,float)) else "—")
        with c3:
            st.metric("Fixo ML (R$)", f"{(sim.get('custo_fixo_full') or 0):.2f}")
        with c4:
            st.metric("Frete (R$)", f"{(sim.get('frete') or 0):.2f}")
        with st.expander("Detalhe da composição (simulada)", expanded=False):
            st.json({
                "preço": sim.get("preco_venda"),
                "preço de custo": sim.get("preco_compra"),
                "frete (R$)": sim.get("frete"),
                "custo fixo ML (R$)": sim.get("custo_fixo_full"),
                "comissão (R$)": sim.get("comissao_brl"),
                "imposto (R$)": sim.get("imposto_brl"),
                "marketing (R$)": sim.get("marketing_brl"),
                "subsídio (R$)": sim.get("subsidio_valor"),
                "alocação do subsídio": sim.get("subsidio_alocado"),
                "MCP (R$)": sim.get("mcp_abs"),
                "MCP (%)": sim.get("mcp_pct"),
            })

    price = row.get("price")
    rebate = row.get("rebate_price_discounted")
    preco_efetivo = row.get("preco_efetivo") or price

    mcp_frac = row.get("mcp")
    mcp_brl = (float(mcp_frac) * float(preco_efetivo)) if (_is_num(mcp_frac) and _is_num(preco_efetivo)) else None

    pmin = row.get("preco_min") or row.get("preco_minimo")
    pmax = row.get("preco_max") or row.get("preco_maximo")

    comissao = row.get("comissao")
    imposto = row.get("imposto")
    marketing = row.get("marketing")
    custo_fixo = row.get("custo_fixo_full")
    preco_compra = row.get("preco_compra")

    colA, colB, colC, colD = st.columns(4)
    with colA:
        st.metric("Preço atual", _fmt_money(price))
    with colB:
        st.metric("MCP (R$ / %)", _fmt_money(mcp_brl), _fmt_pct(mcp_frac))
    with colC:
        st.metric("Comissão ML (R$)", _fmt_money(comissao))
    with colD:
        st.metric("Custo fixo ML (R$)", _fmt_money(custo_fixo))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Preço mínimo (MCP min)", _fmt_money(pmin))
    with col2:
        st.metric("Preço máximo (MCP max)", _fmt_money(pmax))
    with col3:
        st.metric("Preço com rebate", _fmt_money(rebate if rebate else price))
    with col4:
        st.metric("Subsídio ML (R$)", _fmt_money(row.get("subsidio_ml_valor")))

    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("Preço de custo (R$)", _fmt_money(preco_compra))
    with col6:
        st.metric("Imposto (R$)", _fmt_money(imposto))
    with col7:
        st.metric("Marketing (R$)", _fmt_money(marketing))
