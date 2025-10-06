import streamlit as st
import pandas as pd
import json
from datetime import datetime

# consome APENAS service
from app.utils.anuncios import service as anuncios_svc

VISIBLE_COLS = ["mlb", "title", "price", "rebate_price", "logistic_type"]

def render(ctx) -> None:
    rows = ctx.registros or []
    if not rows:
        st.info("Nenhum anúncio encontrado.")
        return

    st.subheader("Catálogo de anúncios (PP)")

    df = pd.DataFrame(rows)
    for c in VISIBLE_COLS:
        if c not in df.columns:
            df[c] = None

    df = df[VISIBLE_COLS].copy()
    df.insert(0, "_sel", False)            # checkbox na 1ª coluna
    df["_sel"] = df["_sel"].astype("bool")

    data_editor = getattr(st, "data_editor", None) or getattr(st, "experimental_data_editor")

    st.caption("Marque um anúncio (apenas um):")
    edited = data_editor(
        df,
        column_config={
            "_sel": st.column_config.CheckboxColumn("Selecionar", help="Escolher este anúncio"),
            "mlb": st.column_config.TextColumn("MLB"),
            "title": st.column_config.TextColumn("Título"),
            "price": st.column_config.NumberColumn("Preço"),
            "rebate_price": st.column_config.NumberColumn("Preço com rebate"),
            "logistic_type": st.column_config.TextColumn("Logística"),
        },
        disabled=[c for c in df.columns if c != "_sel"],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="catalogo_editor",
    )

    # single-select
    selected_idx = edited.index[edited["_sel"]].tolist()
    if len(selected_idx) > 1:
        keep = selected_idx[0]
        edited.loc[edited.index.difference([keep]), "_sel"] = False
        st.warning("Apenas um anúncio pode ser selecionado. Mantive o primeiro marcado.")

    st.divider()
    st.subheader("Selecionar anúncio")

    if edited["_sel"].any():
        i = edited.index[edited["_sel"]].tolist()[0]
        rec = edited.loc[i].drop(labels=["_sel"]).to_dict()
        mlb_sel = rec.get("mlb")

        c1, c2, c3 = st.columns(3)
        c1.metric("MLB", str(mlb_sel or "—"))
        c2.metric("Preço", rec.get("price", "—"))
        c3.metric("Rebate", rec.get("rebate_price", "—"))
        st.write(f"**Título:** {rec.get('title', '—')}")
        st.write(f"**Logística:** {rec.get('logistic_type', '—')}")

        # ------- BOTÃO: exportar TXT RAW -------
        if mlb_sel:
            raw_item = anuncios_svc.obter_raw_por_mlb(str(mlb_sel), ctx.regiao)


            if raw_item is None:
                st.error("RAW não encontrado para este MLB na região selecionada.")
            else:
                now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                linhas = [
                    "=== RAW do Anúncio (Mercado Livre) ===",
                    f"Gerado em (UTC): {now}",
                    f"MLB: {mlb_sel}",
                    "",
                    "--- JSON RAW ---",
                    json.dumps(raw_item, ensure_ascii=False, indent=2),
                    ""
                ]
                payload = "\n".join(linhas).encode("utf-8")
                st.download_button(
                    "⬇️ Baixar TXT RAW do anúncio",
                    data=payload,
                    file_name=f"anuncio_raw_{mlb_sel}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
        # ---------------------------------------

        if st.button("Limpar seleção"):
            edited["_sel"] = False
            st.session_state["catalogo_editor"] = edited
            st.rerun()
    else:
        st.info("Marque a caixa na primeira coluna para selecionar.")
