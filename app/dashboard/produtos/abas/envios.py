from __future__ import annotations
import io
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st

from app.utils.produtos.metrics import calcular_lotes  # cálculo de múltiplos/lotes

COLS_EXPORT = [
    "título",
    "EAN",
    "GTIN",
    "multiplo de compra",
    "preço de compra",
    "quantidade",
    "lotes_down",
    "lotes_up",
    "qtd_ajustada_down",
    "qtd_ajustada_up",
    "largura",               # CAIXA (cm)
    "profundidade",          # CAIXA (cm)
    "altura",                # CAIXA (cm)
    "peso bruto da caixa",   # CAIXA (g)
]

def _safe_get(d: Optional[Dict], *path, default=None):
    try:
        x = d or {}
        for p in path:
            x = x.get(p) if isinstance(x, dict) else None
        return default if x is None else x
    except Exception:
        return default

def _match_produto_por_titulo(produtos: List[Dict[str, Any]], titulo: str) -> Optional[Dict[str, Any]]:
    if not titulo:
        return None
    for r in produtos:
        t = r.get("titulo") or r.get("title")
        if isinstance(t, str) and t.strip().lower() == titulo.strip().lower():
            return r
    for r in produtos:
        t = r.get("titulo") or r.get("title")
        if isinstance(t, str) and t.strip().lower().startswith(titulo.strip().lower()):
            return r
    return None

def _ensure_table_schema(df: pd.DataFrame) -> pd.DataFrame:
    cols = {
        "Selecionar": pd.Series([], dtype="bool"),
        "Título": pd.Series([], dtype="object"),
        "Quantidade": pd.Series([], dtype="float"),
    }
    base = pd.DataFrame(cols)
    if df is None or df.empty:
        return base
    out = base.copy()
    for c in ["Selecionar", "Título", "Quantidade"]:
        if c in df.columns:
            out[c] = df[c]
    out["Selecionar"] = out["Selecionar"].fillna(False).astype(bool)
    out["Título"] = out["Título"].astype("string").fillna("")
    out["Quantidade"] = pd.to_numeric(out["Quantidade"], errors="coerce")
    return out

def render(ctx) -> None:
    st.title("Planejar Envios (Amazon / Mercado Livre)")
    itens = list(ctx.produtos or [])
    if not itens:
        st.info("Nenhum produto encontrado no PP de Produtos.")
        return

    # autocomplete por títulos
    titulos = sorted({(r.get("titulo") or r.get("title") or "").strip()
                      for r in itens if (r.get("titulo") or r.get("title"))})
    if not titulos:
        st.warning("Os itens do PP não possuem campo 'titulo'.")
        return

    st.caption("Preencha **Título** (autocomplete) e **Quantidade**; veja múltiplos/lotes; gere o Excel. Medidas e peso sempre da **CAIXA**.")

    # estado inicial com schema 100% compatível
    if "envios_table" not in st.session_state:
        st.session_state.envios_table = _ensure_table_schema(pd.DataFrame())

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("➕ Adicionar linha"):
            nova = pd.DataFrame([{"Selecionar": False, "Título": "", "Quantidade": 0.0}])
            st.session_state.envios_table = _ensure_table_schema(
                pd.concat([st.session_state.envios_table, nova], ignore_index=True)
            )
    with c2:
        if st.button("🗑️ Limpar todas"):
            st.session_state.envios_table = _ensure_table_schema(pd.DataFrame())
    with c3:
        if st.button("🧹 Remover selecionadas"):
            base_atual = _ensure_table_schema(st.session_state.envios_table.copy())
            sel = base_atual["Selecionar"].fillna(False).astype(bool)
            base_atual = base_atual[~sel].reset_index(drop=True)
            st.session_state.envios_table = _ensure_table_schema(base_atual)

    # helpers
    def _rec_por_titulo(t):
        return _match_produto_por_titulo(itens, str(t or "")) or {}

    base = _ensure_table_schema(st.session_state.envios_table.copy())

    # ===== colunas derivadas (múltiplos) + conferência de CAIXA (sem fallback) =====
    deriv = {
        "MultiploCompra": [],
        "Lotes↓": [],
        "Lotes↑": [],
        "Qtd Ajustada↓": [],
        "Qtd Ajustada↑": [],
        "Caixa L (cm)": [],
        "Caixa P (cm)": [],
        "Caixa A (cm)": [],
        "Caixa Peso Bruto (g)": [],
    }
    for _, row in base.iterrows():
        rec = _rec_por_titulo(row.get("Título"))
        multiplo = rec.get("multiplo_compra") or rec.get("multiplo_de_compra") or rec.get("multiplo")
        lotes = calcular_lotes(row.get("Quantidade"), multiplo)
        deriv["MultiploCompra"].append(lotes.get("multiplo_norm"))
        deriv["Lotes↓"].append(lotes.get("lotes_down"))
        deriv["Lotes↑"].append(lotes.get("lotes_up"))
        deriv["Qtd Ajustada↓"].append(lotes.get("qtd_ajustada_down"))
        deriv["Qtd Ajustada↑"].append(lotes.get("qtd_ajustada_up"))

        # CAIXA apenas (sem fallback)
        deriv["Caixa L (cm)"].append(_safe_get(rec, "caixa_cm", "largura"))
        deriv["Caixa P (cm)"].append(_safe_get(rec, "caixa_cm", "profundidade"))
        deriv["Caixa A (cm)"].append(_safe_get(rec, "caixa_cm", "altura"))
        deriv["Caixa Peso Bruto (g)"].append(_safe_get(rec, "pesos_caixa_g", "bruto"))

    df_view = pd.concat([base, pd.DataFrame(deriv)], axis=1)

    edited = st.data_editor(
        df_view,
        key="envios_editor",
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Sel.",
                help="Marque e use 'Remover selecionadas' para excluir linhas.",
            ),
            "Título": st.column_config.SelectboxColumn(
                "Título",
                options=titulos,
                help="Selecione um título (autocomplete) ou digite para filtrar.",
            ),
            "Quantidade": st.column_config.NumberColumn(
                "Quantidade",
                min_value=0,
                step=1,
                help="Quantidade a enviar.",
            ),
            "MultiploCompra": st.column_config.NumberColumn("Múltiplo", disabled=True),
            "Lotes↓": st.column_config.NumberColumn("Lotes ↓", disabled=True),
            "Lotes↑": st.column_config.NumberColumn("Lotes ↑", disabled=True),
            "Qtd Ajustada↓": st.column_config.NumberColumn("Qtd Ajustada ↓", disabled=True),
            "Qtd Ajustada↑": st.column_config.NumberColumn("Qtd Ajustada ↑", disabled=True),
            "Caixa L (cm)": st.column_config.NumberColumn("Caixa L (cm)", disabled=True),
            "Caixa P (cm)": st.column_config.NumberColumn("Caixa P (cm)", disabled=True),
            "Caixa A (cm)": st.column_config.NumberColumn("Caixa A (cm)", disabled=True),
            "Caixa Peso Bruto (g)": st.column_config.NumberColumn("Caixa Peso Bruto (g)", disabled=True),
        },
    )

    # Persiste apenas colunas editáveis + seleção
    cols_persist = [c for c in ["Selecionar", "Título", "Quantidade"] if c in edited.columns]
    st.session_state.envios_table = _ensure_table_schema(edited[cols_persist].copy())

    st.divider()
    st.subheader("Gerar Excel de Envios")

    linhas_validas = edited[
        (edited["Título"].astype(str).str.strip() != "") &
        (edited["Quantidade"].fillna(0) > 0)
    ]
    qtd_itens = len(linhas_validas)
    st.write(f"Linhas válidas: **{qtd_itens}**")

    def _linha_export(titulo_escolhido: str, qtd: float) -> Dict[str, Any]:
        rec = _rec_por_titulo(titulo_escolhido) or {}
        gtin = rec.get("gtin") or rec.get("ean") or ""
        ean = rec.get("ean") or gtin
        preco_compra = rec.get("preco_compra") if isinstance(rec.get("preco_compra"), (int, float)) else rec.get("custo")
        multiplo = rec.get("multiplo_de_compra") or rec.get("multiplo_compra") or rec.get("multiplo") or ""

        # === CAIXA apenas (sem fallback para produto) ===
        largura = _safe_get(rec, "caixa_cm", "largura")
        profundidade = _safe_get(rec, "caixa_cm", "profundidade")
        altura = _safe_get(rec, "caixa_cm", "altura")
        peso_bruto = _safe_get(rec, "pesos_caixa_g", "bruto")

        # === Lotes (com base na quantidade lançada e no múltiplo) ===
        lotes = calcular_lotes(qtd, multiplo)
        lotes_down = lotes.get("lotes_down")
        lotes_up = lotes.get("lotes_up")
        qtd_down = lotes.get("qtd_ajustada_down")
        qtd_up = lotes.get("qtd_ajustada_up")

        return {
            "título": titulo_escolhido,
            "EAN": ean,
            "GTIN": gtin,
            "multiplo de compra": multiplo,
            "preço de compra": preco_compra,
            "quantidade": qtd,
            "lotes_down": lotes_down,
            "lotes_up": lotes_up,
            "qtd_ajustada_down": qtd_down,
            "qtd_ajustada_up": qtd_up,
            "largura": largura,
            "profundidade": profundidade,
            "altura": altura,
            "peso bruto da caixa": peso_bruto,
        }

    if st.button("📦 Gerar Excel"):
        if qtd_itens == 0:
            st.warning("Preencha ao menos uma linha com título e quantidade > 0.")
            return
        linhas = [
            _linha_export(row["Título"], row["Quantidade"])
            for _, row in linhas_validas.iterrows()
        ]
        df_out = pd.DataFrame(linhas, columns=COLS_EXPORT)

        # writer com fallback (xlsxwriter → openpyxl → CSV)
        def _to_excel_bytes(df: pd.DataFrame, sheet_name: str = "envios") -> bytes:
            buf = io.BytesIO()
            try:
                import xlsxwriter  # noqa
                engine = "xlsxwriter"
            except Exception:
                try:
                    import openpyxl  # noqa
                    engine = "openpyxl"
                except Exception:
                    return df.to_csv(index=False).encode("utf-8")
            with pd.ExcelWriter(buf, engine=engine) as xw:
                df.to_excel(xw, index=False, sheet_name=sheet_name)
                try:
                    ws = xw.sheets[sheet_name]
                    for i, col in enumerate(df.columns, start=1):
                        avg = int(df[col].astype(str).str.len().mean() + 4) if len(df) else 12
                        ws.set_column(i-1, i-1, max(12, min(40, avg)))
                except Exception:
                    pass
            return buf.getvalue()

        payload = _to_excel_bytes(df_out)
        is_xlsx = payload[:2] == b"PK"  # zip header
        fname = "envios.xlsx" if is_xlsx else "envios.csv"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if is_xlsx else "text/csv"

        st.success("Arquivo de envios gerado!")
        st.download_button("⬇️ Baixar", data=payload, file_name=fname, mime=mime)
