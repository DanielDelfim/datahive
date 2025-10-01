# pages/4_anuncios_meli.py
import os
import sys
import subprocess
import streamlit as st

from pathlib import Path

from app.dashboard.anuncios_meli import render_dashboard_anuncios
from app.dashboard.anuncios_meli.context import make_context
from app.config.paths import Regiao  # transversal

st.set_page_config(page_title="Anúncios Meli — Datahive", layout="wide")

st.title("Anúncios — Mercado Livre")
st.caption("Page casca: leitura via utils/anuncios/service.py; atualização via scripts (RAW → PP).")

# ---------------- Filtros UI ----------------
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    regiao_opt = st.selectbox(
        "Região",
        options=[None, Regiao.SP, Regiao.MG],
        format_func=lambda v: "Todas" if v is None else v.value.upper(),
        index=0,
    )
with col2:
    busca = st.text_input("Buscar (mlb/sku/título)", placeholder="Ex.: MLB..., 7908..., 'Melbras'")
with col3:
    somente_full = st.checkbox("Somente FULL", value=False)

st.divider()
st.subheader("Atualização de anúncios (RAW → PP)")
st.caption("Roda: atualizar_raw.py e depois gerar_pp.py para **SP** e **MG**. O dashboard recarrega ao final.")

def _run(cmd: list[str], env: dict, cwd: str | None = None) -> tuple[int, str, str]:
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)
    return res.returncode, res.stdout, res.stderr

colA, colB = st.columns([1, 2])
with colA:
    if st.button("🔁 Atualizar anúncios (SP + MG)", use_container_width=True):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        # raiz do projeto (…/Datahive) para estabilizar imports em -m
        ROOT_DIR = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = ROOT_DIR + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")


        # garante que o projeto (raiz) está no PYTHONPATH
        ROOT_DIR = str(Path(__file__).resolve().parents[1])  # .../Datahive
        env["PYTHONPATH"] = ROOT_DIR + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
 

        regions = ["SP", "MG"]
        logs = []

        with st.spinner("Atualizando RAW e PP de anúncios..."):
            for r in regions:
                # 1) RAW
                cmd_raw = [sys.executable, "-m", "scripts.anuncios.meli.atualizar_raw", "--regiao", r.lower()]
                rc1, out1, err1 = _run(cmd_raw, env, cwd=ROOT_DIR)
                logs.append((f"RAW {r}", rc1, out1, err1))
                if rc1 != 0:
                    st.error(f"Falha ao atualizar RAW ({r}).")
                    if err1 or out1:
                        with st.expander(f"Log RAW {r}"):
                            st.code(err1 or out1)
                    st.stop()

                # 2) PP
                cmd_pp = [sys.executable, "-m", "scripts.anuncios.meli.gerar_pp", "--regiao", r.lower()]
                rc2, out2, err2 = _run(cmd_pp, env, cwd=ROOT_DIR)
                logs.append((f"PP {r}", rc2, out2, err2))
                if rc2 != 0:
                    st.error(f"Falha ao gerar PP ({r}).")
                    if err2 or out2:
                        with st.expander(f"Log PP {r}"):
                            st.code(err2 or out2)
                    st.stop()

        st.success("Anúncios atualizados com sucesso para SP e MG.")
        with st.expander("Ver logs"):
            for name, rc, out, err in logs:
                st.write(f"### {name} (rc={rc})")
                if out:
                    st.code(out)
                if err:
                    st.code(err)

        # Limpa cache e recarrega para ler os PP recém-gerados
        st.cache_data.clear()
        st.rerun()

with colB:
    st.caption("A page não escreve em disco; quem persiste RAW/PP são os scripts com escrita atômica e backups.")

# ---------------- Contexto + Dashboard ----------------
ctx = make_context(regiao=regiao_opt, busca=busca, somente_full=somente_full)
render_dashboard_anuncios(ctx)
