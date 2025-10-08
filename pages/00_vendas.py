# pages/00_vendas.py
from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
import streamlit as st
from app.dashboard.vendas.compositor import (
    tabela_por_mlb, tabela_por_mlb_br,
    tabela_por_gtin, tabela_por_gtin_br,
)

# Ajuste de sys.path (se necessário) para rodar a partir da raiz do projeto
ROOT = Path(__file__).resolve().parents[1]  # <repo>/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Vendas — ML", page_icon="📦", layout="wide")

st.title("📦 Vendas — Mercado Livre")
st.caption("Resumo por MLB e GTIN (janelas de 7/15/30 dias). Fonte: PP consolidado.")

# ================ Botão de atualização ================
def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=env,
        )
        return proc.returncode, proc.stdout
    except Exception as e:
        return 1, f"[ERRO] {e}"

def atualizar_pipeline_vendas():
    """
    Dispara os scripts do pipeline RAW→PP.
    Usa invocação por módulo (-m) e loja posicional (sp|mg).
    """
    py = sys.executable or "python"

    cmds = [
        # 1) RAW (últimos 30 dias)
        [py, "-m", "scripts.vendas.meli_vendas_fetch_range", "sp", "--days", "30"],
        [py, "-m", "scripts.vendas.meli_vendas_fetch_range", "mg", "--days", "30"],

        # 2) PP (aceita sp|mg|all; aqui geramos por loja)
        [py, "-m", "scripts.vendas.gerar_pp", "sp"],
        [py, "-m", "scripts.vendas.gerar_pp", "mg"],
    ]

    logs = []
    ok_all = True
    for c in cmds:
        rc, out = _run(c)
        ok_all &= (rc == 0)
        logs.append(f"$ {' '.join(c)}\n{out}\n---\n")
        if rc != 0:
            break
    return ok_all, "\n".join(logs)


col1, col2 = st.columns([1, 5])
with col1:
    if st.button("🔁 Atualizar vendas", use_container_width=True, type="primary"):
        with st.status("Atualizando RAW → PP...", expanded=True) as s:
            ok, logs = atualizar_pipeline_vendas()
            st.code(logs, language="bash")
            if ok:
                s.update(label="✅ Atualizado com sucesso!", state="complete")
            else:
                s.update(label="❌ Falha na atualização — verifique os logs acima.", state="error")

st.divider()

# ================ Abas MG / SP / BR / Resumo (GTIN) ================
tab_mg, tab_sp, tab_br, tab_resumo = st.tabs(["MG", "SP", "BR (MG+SP)", "Resumo (GTIN)"])

def _render_table(df, file_name: str):
    if df.empty:
        st.info("Nenhuma venda encontrada para o período selecionado.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Baixar CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=file_name,
            mime="text/csv",
            use_container_width=True,
        )

def _render_tab(loja: str, tab):
    with tab:
        st.subheader(f"Loja: {loja.upper()}")
        df = tabela_por_mlb(loja)
        _render_table(df, f"vendas_por_mlb_{loja}.csv")

def _render_tab_br(tab):
    with tab:
        st.subheader("Brasil (MG + SP)")
        df = tabela_por_mlb_br()
        _render_table(df, "vendas_por_mlb_br.csv")

def _render_resumo_gtin(tab):
    with tab:
        st.subheader("Resumo por GTIN")
        sub_mg, sub_sp, sub_br = st.tabs(["MG", "SP", "BR"])
        with sub_mg:
            df = tabela_por_gtin("mg")
            _render_table(df, "resumo_gtin_mg.csv")
        with sub_sp:
            df = tabela_por_gtin("sp")
            _render_table(df, "resumo_gtin_sp.csv")
        with sub_br:
            df = tabela_por_gtin_br()
            _render_table(df, "resumo_gtin_br.csv")

_render_tab("mg", tab_mg)
_render_tab("sp", tab_sp)
_render_tab_br(tab_br)
_render_resumo_gtin(tab_resumo)
