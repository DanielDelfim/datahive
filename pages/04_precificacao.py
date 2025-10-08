# C:\Apps\Datahive\app\dashboard\precificacao\2_precificacao.py
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
import streamlit as st

from app.dashboard.precificacao import render_dashboard_precificacao
from app.dashboard.precificacao.context import load_context

st.set_page_config(page_title="Precificação", page_icon="💸", layout="wide")
st.title("💸 Precificação — Mercado Livre")

st.caption("Os scripts abaixo **escrevem** os JSONs PP. As abas apenas **leem** e exibem.")

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🔁 Carregar scripts (Resumo)", use_container_width=True):
        # dentro do handler do botão "🔁 Carregar scripts (Resumo)"
        base = Path("C:/Apps/Datahive/scripts/precificacao/meli")
        regiao = st.session_state.get("prec_regiao", "sp").lower()

        cmds = [
            [sys.executable, str(base / "carregar_anuncios.py"),        "--regiao", regiao],
            [sys.executable, str(base / "carregar_preco_compra.py"),    "--regiao", regiao],
            [sys.executable, str(base / "recalcular_metricas.py"),      "--regiao", regiao],
            # 👇 NOVO: agrega preços min/max + warnings no dataset da região
            [sys.executable, str(base / "agregar_precos_min_max.py"),   "--regiao", regiao],
        ]
        logs = []
        for cmd in cmds:
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logs.append(f"$ {' '.join(cmd)}\n{res.stdout}")
            except subprocess.CalledProcessError as e:
                logs.append(f"$ {' '.join(cmd)}\n[stderr]\n{e.stderr}\n[returncode] {e.returncode}")

        st.session_state["precificacao_logs"] = "\n\n".join(logs)
        st.success("Scripts executados. Role a página para ver logs e as abas atualizadas.")

with col2:
    st.selectbox(
        "Região",
        options=["sp", "mg"],
        key="prec_regiao",
        index=(["sp","mg"].index(st.session_state.get("prec_regiao","sp"))
               if st.session_state.get("prec_regiao") in ["sp","mg"] else 0),
    )

if "precificacao_logs" in st.session_state:
    with st.expander("📜 Logs de execução", expanded=False):
        st.code(st.session_state["precificacao_logs"], language="bash")

regiao = st.session_state.get("prec_regiao", "sp").lower()
ctx = load_context(regiao=regiao)
render_dashboard_precificacao(ctx)
