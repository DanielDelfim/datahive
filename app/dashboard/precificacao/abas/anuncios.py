# app/dashboard/precificacao/abas/anuncios.py
import streamlit as st
import pandas as pd

COLS_ORDER = [
    "mlb", "sku", "gtin", "title", "full", "status",
    "preco_venda", "rebate_price", "original_price",
    "mcp_pct", "mcp_sem_custo_pct", "fee_pct", "custo"
]

def _fmt_pct(x):
    return f"{x:.1f}%" if isinstance(x, (int, float)) else "—"

def _to_percent(x):
    """Converte razão→% quando vem em [−1,1]; mantém se já estiver em %."""
    if isinstance(x, (int, float)):
        return x * 100.0 if -1.0 <= x <= 1.0 else x
    return None

def _first_not_none(*vals):
    for v in vals:
        if v is not None:
            return v
    return None

def _extract_custo(rec: dict):
    return _first_not_none(
        rec.get("custo"),
        rec.get("preco_custo"),
        rec.get("cost"),
        rec.get("preco_compra")
    )

def _calc_mcp_pct(preco: float, custo: float | None, fee_pct: float) -> float | None:
    if not isinstance(preco, (int, float)) or preco <= 0:
        return None
    # Receita líquida após taxa ML (sem frete/subsídios adicionais aqui – simulação simples)
    receita_liq = preco * (1 - fee_pct / 100.0)
    if isinstance(custo, (int, float)):
        margem = receita_liq - custo
    else:
        # Sem custo: MCP "sem custo"
        margem = receita_liq
    return (margem / preco) * 100.0

def render(ctx) -> None:
    dados = ctx.linhas_precificacao or []
    if not dados:
        st.info("Nenhum anúncio encontrado.")
        return

    # --- Tabela principal ---
    df = pd.DataFrame(dados)
    cols = [c for c in COLS_ORDER if c in df.columns] + [c for c in df.columns if c not in COLS_ORDER]
    df = df[cols]

    # Exibe a tabela
    st.subheader("Lista de anúncios")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Seletor de anúncio (por MLB — título) ---
    st.divider()
    st.subheader("Selecionar anúncio para simulação")

    # Mapas de seleção
    options = []
    idx_by_key = {}
    for i, r in enumerate(dados):
        mlb = r.get("mlb", "—")
        title = r.get("title", "—")
        label = f"{mlb} — {title}"
        options.append(label)
        idx_by_key[label] = i

    if not options:
        st.info("Sem anúncios para selecionar.")
        return

    sel_label = st.selectbox("Anúncio", options, index=0, key="precif_sel_anuncio")
    rec = dados[idx_by_key[sel_label]]

    # --- Inputs de simulação ---
    preco_base = _first_not_none(rec.get("rebate_price"), rec.get("preco_venda"))
    fee_base = rec.get("fee_pct", 16.0)  # hipótese: 16% se não existir no registro
    custo_prod = _extract_custo(rec)

    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        preco_sim = st.number_input(
            "Preço (simulação)",
            min_value=0.0, step=0.01,
            value=float(preco_base) if isinstance(preco_base, (int, float)) else 0.0,
            help="Altere para testar o impacto no MCP."
        )
    with colB:
        desconto_taxa = st.number_input(
            "Desconto de taxas (%) (simulação)",
            min_value=0.0, max_value=100.0, step=0.1, value=0.0,
            help="Subsidio/desconto concedido pelo ML nas taxas. Ex.: 2,5"
        )
    with colC:
        fee_eff = max(fee_base - desconto_taxa, 0.0)
        st.metric("Taxa efetiva (após desconto)", _fmt_pct(fee_eff))

    # --- Cálculos MCP atual x simulado ---
    # Normaliza valores do service (podem vir como razão)
    mcp_atual = _to_percent(rec.get("mcp_pct"))
    mcp_sem_custo_atual = _to_percent(rec.get("mcp_sem_custo_pct"))
    mcp_sim = _calc_mcp_pct(preco_sim, custo_prod, fee_eff)
    mcp_sim_sem_custo = _calc_mcp_pct(preco_sim, None, fee_eff)

    # --- Cards de métricas ---
    st.subheader("Métricas do anúncio selecionado")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Preço base", f"{preco_base:.2f}" if isinstance(preco_base, (int, float)) else "—")
    c2.metric("Custo do produto", f"{custo_prod:.2f}" if isinstance(custo_prod, (int, float)) else "—")
    c3.metric("MCP atual", _fmt_pct(mcp_atual) if mcp_atual is not None else _fmt_pct(mcp_sem_custo_atual))
    c4.metric("MCP simulado", _fmt_pct(mcp_sim) if mcp_sim is not None else _fmt_pct(mcp_sim_sem_custo))

    # Detalhes adicionais
    with st.expander("Detalhes do anúncio (dados brutos)"):
        st.json(rec, expanded=False)

    st.caption(
        "Notas: a simulação considera apenas variação de **preço** e **taxa ML**. "
        "Fórmula: receita_liq = preço × (1 − taxa_efetiva), margem = receita_liq − custo, "
        "MCP% = (margem ÷ preço) × 100. Outros componentes (frete, logística, subsídios, impostos) "
        "podem afetar o MCP real e não estão inclusos."
    )
