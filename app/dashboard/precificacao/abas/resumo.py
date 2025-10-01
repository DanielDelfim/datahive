# app/dashboard/precificacao/abas/resumo.py
import streamlit as st
import math
from statistics import mean
import pandas as pd

def _pct(x):
    try:
        return f"{x:.1f}%"
    except Exception:
        return "—"

def render(ctx) -> None:
    dados = ctx.linhas_precificacao
    if not dados:
        st.info("Nenhum anúncio encontrado com os filtros atuais.")
        return

    # KPIs
    n_total = len(dados)
    mcp_vals = [r.get("mcp_pct") for r in dados if isinstance(r.get("mcp_pct"), (int, float, float))]
    n_com_custo = sum(1 for v in mcp_vals)
    n_full = sum(1 for r in dados if r.get("full") is True)
    mcp_med = mean(mcp_vals) if mcp_vals else None
    mcp_min = min(mcp_vals) if mcp_vals else None
    mcp_max = max(mcp_vals) if mcp_vals else None

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Anúncios (totais)", f"{n_total}")
    c2.metric("Com custo de produto", f"{n_com_custo} ({(n_com_custo/n_total*100):.0f}%)" if n_total else "0")
    c3.metric("FULL", f"{n_full} ({(n_full/n_total*100):.0f}%)" if n_total else "0")
    c4.metric("MCP médio", _pct(mcp_med) if mcp_med is not None else "—")
    c5.metric("MCP (min–max)", f"{_pct(mcp_min)} – {_pct(mcp_max)}" if mcp_min is not None else "—")

    st.divider()
    st.subheader("Distribuição de MCP (com custo)")

    # Bandas de MCP (%)
    bandas = [-math.inf, 0, 5, 10, 15, 20, 30, math.inf]
    labels = ["<0", "0–5", "5–10", "10–15", "15–20", "20–30", "≥30"]
    cont = [0]*7
    for v in mcp_vals:
        for i in range(len(bandas)-1):
            if bandas[i] <= v < bandas[i+1]:
                cont[i] += 1
                break

    df = pd.DataFrame({"Faixa MCP (%)": labels, "Qtd": cont})
    st.bar_chart(df.set_index("Faixa MCP (%)"))
    with st.expander("Ver tabela de distribuição"):
        st.dataframe(df, use_container_width=True)
