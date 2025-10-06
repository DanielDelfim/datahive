# app/dashboard/tax_documents/tabs/consolidado.py
from __future__ import annotations

import sys
import json
import subprocess
from pathlib import Path

import streamlit as st

from app.dashboard.tax_documents import compositor as C
from app.utils.tax_documents.config import pp_consolidado_somas_json_path

# Mostrar só estas colunas (ordem fixa)
DISPLAY_COLS = ["Natureza", "Valor Nota", "Frete", "Valor Base COFINS"]


# ---- helpers visuais (formato em LINHAS) ----
def brl(x: float) -> str:
    try:
        v = float(x)
    except Exception:
        v = 0.0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _cell(label: str, value: float):
    box = st.container(border=True)
    box.caption(label)
    box.markdown(f"<div style='font-size:1.15rem;margin:0'>{brl(value)}</div>", unsafe_allow_html=True)

def _row_totais(provider_label: str, bloco: dict[str, float]):
    # Uma LINHA: [ Provedor | Venda | Revenda | Total ]
    c0, c1, c2, c3 = st.columns([1.2, 1, 1, 1])
    with c0:
        st.markdown(f"**{provider_label}**")
    with c1:
        _cell("Venda", bloco.get("venda", 0.0))
    with c2:
        _cell("Revenda", bloco.get("revenda", 0.0))
    with c3:
        _cell("Total", bloco.get("total", 0.0))

def _render_totais_rows(totais: dict):
    st.markdown("**Totais por provedor (mês)**")
    # cabeçalho visual
    h0, h1, h2, h3 = st.columns([1.2, 1, 1, 1])
    with h0: st.caption("Provedor")
    with h1: st.caption("Venda")
    with h2: st.caption("Revenda")
    with h3: st.caption("Total")

    # linhas
    _row_totais("Meli",   totais.get("meli",   {}))
    _row_totais("Amazon", totais.get("amazon", {}))
    _row_totais("Bling",  totais.get("bling",  {}))

    st.markdown("")  # espaçamento

    # Geral (uma linha)
    st.subheader("Geral no mês", anchor=False)
    g0, g1, g2, g3 = st.columns([1.2, 1, 1, 1])
    with g0: st.markdown("**Geral**")
    geral = totais.get("geral", {})
    with g1: _cell("Venda",   geral.get("venda",   0.0))
    with g2: _cell("Revenda", geral.get("revenda", 0.0))
    with g3: _cell("Total",   geral.get("total",   0.0))

def _render_filtered_table(rows: list[dict]):
    if not rows:
        st.caption("Sem dados.")
        return
    try:
        import pandas as pd
        cols_present = [c for c in DISPLAY_COLS if c in rows[0].keys()]
        if not cols_present:
            st.caption("Nenhuma das colunas esperadas está presente no JSON.")
            st.dataframe(rows, use_container_width=True, height=280)
            return
        df = pd.DataFrame(rows)
        st.dataframe(df[cols_present], use_container_width=True, height=280)
    except Exception:
        # fallback sem pandas
        filtered = [{k: r.get(k, "") for k in DISPLAY_COLS} for r in rows]
        st.dataframe(filtered, use_container_width=True, height=280)

def _brl(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _script_path() -> Path:
    """
    Resolve robustamente o caminho do script:
    <repo_root>/scripts/tax_documents/somar_vendas_revendas.py
    Mesmo que o cwd varie, sobe diretórios até encontrar /scripts/...
    """
    target_rel = Path("scripts") / "tax_documents" / "somar_vendas_revendas.py"
    here = Path(__file__).resolve()
    # tenta achar subindo até 6 níveis
    for p in [here.parent] + list(here.parents):
        cand = p / target_rel
        if cand.exists():
            return cand
    # fallback: assume estrutura padrão (repo_root é 4 níveis acima de tabs/)
    # tabs -> tax_documents -> dashboard -> app -> repo_root
    repo_root = here.parents[4] if len(here.parents) >= 5 else here.parents[-1]
    return repo_root / target_rel

def render(ano: int, mes: int):
    st.subheader("Consolidado — todos provedores e regiões disponíveis")
    c1, c2 = st.columns(2)
    with c1:
        ano_c = st.number_input("Ano (Consolidado)", 2015, 2100, ano, key="ano_cons")
    with c2:
        mes_c = st.number_input("Mês (Consolidado)", 1, 12, mes, key="mes_cons")

    if st.button("🔎 Listar disponíveis e carregar"):
        disp = C.listar_disponiveis(int(ano_c), int(mes_c))
        if not disp:
            st.warning("Nenhum provedor/região encontrado para o período.")
        else:
            st.info("Disponíveis: " + ", ".join([f"{prov}({', '.join([r or '—' for r in regs])})" for prov, regs in disp.items()]))
            data = C.carregar_resumo_consolidado_all(int(ano_c), int(mes_c))
            for (prov, reg), rows in sorted(data.items(), key=lambda t: (t[0][0], t[0][1] or "")):
                prov_label = str(prov).upper()
                if reg is None or reg == "":
                    reg_label = "(sem região)"
                elif hasattr(reg, "name"):  # Enum Regiao
                    reg_label = str(reg.name).upper()
                else:  # string
                    reg_label = str(reg).upper()

                label = f"{prov_label} · {reg_label}"
                with st.expander(label, expanded=False):
                    if rows:
                        _render_filtered_table(rows)
                    else:
                        st.caption("Sem resumo para este bucket.")

    st.markdown("---")
    st.subheader("Totais de Vendas/Revendas (executar script)")

    col_btn, col_chk = st.columns([2, 1])
    with col_chk:
        only_auth = st.checkbox("Somente autorizadas", value=True, help="Ignora NF canceladas/denegadas")

    with col_btn:
        if st.button("▶️ Recalcular somas (script)"):
            try:
                script = _script_path()
                cmd = [
                    sys.executable,
                    str(script),
                    "--ano", str(int(ano_c)),
                    "--mes", str(int(mes_c)),
                    "--source", "auto",
                    "--refresh-resumos",
                ]
                if only_auth:
                    cmd.append("--somente-autorizadas")


                run = subprocess.run(cmd, capture_output=True, text=True, check=False)

                if run.returncode != 0:
                    st.error(f"Script falhou:\n{run.stderr or run.stdout}")
                else:
                    # tenta pegar o path pelo stdout; se não vier, monta pelo helper
                    out_path = None
                    try:
                        info = json.loads(run.stdout.strip())
                        out_path = info.get("output")
                    except Exception:
                        pass
                    if not out_path:
                        out_path = str(pp_consolidado_somas_json_path(int(ano_c), int(mes_c)))

                    data = json.loads(Path(out_path).read_text(encoding="utf-8"))
                    tot = data["totais"]

                    st.success(f"Arquivo gerado: {out_path}")
                    _render_totais_rows(tot)

            except Exception as e:
                st.error(f"Erro ao executar script: {e}")

    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        if st.button("📥 Gerar Excel completo (todos provedores/regiões do mês)"):
            try:
                path_xlsx = C.acionar_gerar_excel_consolidado(int(ano_c), int(mes_c))
                st.success(f"Excel gerado em: {path_xlsx}")
            except Exception as e:
                st.error(f"Falha ao gerar Excel consolidado: {e}")
    with c4:
        if st.button("📥 Gerar Excel por Nota (1 linha por NF)"):
            try:
                path_xlsx = C.acionar_gerar_excel_consolidado_por_nota(int(ano_c), int(mes_c))
                st.success(f"Excel por nota gerado em: {path_xlsx}")
            except Exception as e:
                st.error(f"Falha ao gerar Excel por nota: {e}")
