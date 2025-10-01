# app/dashboard/anuncios_meli/abas/resumo.py
import streamlit as st
from collections import Counter
from statistics import mean

def render(ctx) -> None:
    rows = ctx.registros or []
    if not rows:
        st.info("Nenhum anúncio encontrado com os filtros atuais.")
        return

    n = len(rows)
    n_full = sum(1 for r in rows if str(r.get("logistic_type") or "").lower() == "fulfillment")
    prices = [r.get("rebate_price") or r.get("price") for r in rows if isinstance(r.get("rebate_price") or r.get("price"), (int, float))]
    pmed = mean(prices) if prices else None

    c1, c2, c3 = st.columns(3)
    c1.metric("Anúncios (total)", f"{n}")
    c2.metric("FULL", f"{n_full} ({(n_full/n*100):.0f}%)" if n else "0")
    c3.metric("Preço médio", f"{pmed:.2f}" if pmed is not None else "—")

    st.divider()
    st.subheader("Status dos anúncios")
    cnt = Counter([str(r.get("status") or "—") for r in rows])
    st.write({k: cnt[k] for k in sorted(cnt)})
