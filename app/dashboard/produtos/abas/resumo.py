# app/dashboard/produtos/abas/resumo.py
import streamlit as st
import pandas as pd
from statistics import mean

def render(ctx) -> None:
    dados = ctx.produtos or []
    if not dados:
        st.info("Nenhum produto encontrado com os filtros atuais.")
        return

    n_total = len(dados)
    def _custo(r):
        return r.get("preco_compra") if isinstance(r.get("preco_compra"), (int, float)) else r.get("custo")
    custo_vals = [ _custo(r) for r in dados if isinstance(_custo(r), (int, float)) ]
    n_com_custo = len(custo_vals)
    n_com_gtin = sum(1 for r in dados if str(r.get("gtin") or "").strip() != "")
    custo_med = mean(custo_vals) if custo_vals else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SKUs (total)", f"{n_total}")
    c2.metric("Com custo", f"{n_com_custo} ({(n_com_custo/n_total*100):.0f}%)" if n_total else "0")
    c3.metric("Com GTIN/EAN", f"{n_com_gtin} ({(n_com_gtin/n_total*100):.0f}%)" if n_total else "0")
    c4.metric("Custo médio", f"{custo_med:.2f}" if custo_med is not None else "—")

    st.divider()
    st.subheader("Distribuição de custo (faixas)")
    bins = [0, 5, 10, 20, 50, 100, float("inf")]
    labels = ["0–5", "5–10", "10–20", "20–50", "50–100", "≥100"]
    cont = [0]*(len(bins)-1)
    for v in custo_vals:
        for i in range(len(bins)-1):
            if bins[i] <= v < bins[i+1]:
                cont[i] += 1
                break
    df = pd.DataFrame({"Faixa de custo": labels, "Qtd": cont})
    st.bar_chart(df.set_index("Faixa de custo"))
    with st.expander("Ver tabela"):
        st.dataframe(df, use_container_width=True)
