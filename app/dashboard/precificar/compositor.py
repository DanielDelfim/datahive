# C:\Apps\Datahive\app\dashboard\precificar\compositor.py
from __future__ import annotations

from typing import List
import streamlit as st
from app.utils.anuncios.service import obter_anuncio_por_mlb_pp  # estoque por MLB/região (PP)

from app.utils.vendas.meli.service import get_por_mlb, get_por_mlb_br

from app.config.paths import Regiao
from app.utils.precificacao.service import (
    construir_dataset_base,    # monta itens (price, rebate, logística, etc.)
    enriquecer_preco_compra, 
    aplicar_overrides_no_documento, 
    aplicar_metricas_no_documento,  # calcula MCP, custos e percentuais
)
from app.utils.precificacao.simulator import simular_mcp_item
from app.utils.precificacao.precos_min_max import precos_min_max
from app.utils.precificacao.metrics import carregar_regras_ml

from app.utils.precificacao.metrics_estoque import calcular_cobertura_estoque


def _dataset_memoria_unit(regiao: Regiao) -> dict:
    # versão unitária (sem mudanças nas suas regras)
    doc = construir_dataset_base(regiao)
    doc = enriquecer_preco_compra(doc)
    doc = aplicar_overrides_no_documento(doc) 
    doc = aplicar_metricas_no_documento(doc)

    # anexar faixa de preços alvo (se você já tinha essa lógica)
    regras = carregar_regras_ml()
    itens2 = []
    for it in doc.get("itens", []):
        it2 = dict(it)
        faixas = precos_min_max(it2, regras)
        if faixas.get("preco_minimo") is not None:
            it2["preco_minimo"] = faixas["preco_minimo"]
        if faixas.get("preco_maximo") is not None:
            it2["preco_maximo"] = faixas["preco_maximo"]
        itens2.append(it2)
    doc["itens"] = itens2
    return doc


def _dataset_memoria_multi(regioes: list[Regiao]) -> dict:
    """
    Carrega 1..n regiões e concatena itens num único documento.
    Mantém o campo `regiao` em cada item para distinguir no grid.
    """
    itens_all: list[dict] = []
    metas = []
    for r in regioes:
        d = _dataset_memoria_unit(r)
        for it in d.get("itens", []):
            it2 = dict(it)
            it2["regiao"] = r  # garante o campo
            itens_all.append(it2)
        metas.append(d.get("_meta"))
    return {"itens": itens_all, "_meta_origens": metas}

def _filtrar_por_logistica(items: List[dict], modo: str) -> List[dict]:
    if modo == "Todos":
        return items
    if modo == "Fulfillment":
        return [x for x in items if str(x.get("logistic_type") or "").lower().startswith("fulfillment") or x.get("is_full")]
    # Seller
    return [x for x in items if not str(x.get("logistic_type") or "").lower().startswith("fulfillment") and not x.get("is_full")]


def _aplicar_filtro_busca(items: List[dict], query: str) -> List[dict]:
    """
    Filtro textual por MLB, GTIN ou título (case-insensitive; aceita partes).
    """
    q = (query or "").strip().lower()
    if not q:
        return items
    def match(it: dict) -> bool:
        mlb   = str(it.get("mlb")   or "").lower()
        gtin  = str(it.get("gtin")  or "").lower()
        title = str(it.get("title") or "").lower()
        return (q in mlb) or (q in gtin) or (q in title)
    return [it for it in items if match(it)]

def _dataset_memoria(regiao):
    doc = construir_dataset_base(regiao)
    doc = enriquecer_preco_compra(doc)
    doc = aplicar_overrides_no_documento(doc)
    doc = aplicar_metricas_no_documento(doc)

    # anexar preco_minimo/preco_maximo por item (somente FULL quando aplicável)
    regras = carregar_regras_ml()
    itens2 = []
    for it in doc.get("itens", []):
        faixas = precos_min_max(it, regras)
        it2 = dict(it)
        if faixas.get("preco_minimo") is not None:
            it2["preco_minimo"] = faixas["preco_minimo"]
        if faixas.get("preco_maximo") is not None:
            it2["preco_maximo"] = faixas["preco_maximo"]
        itens2.append(it2)
    doc["itens"] = itens2
    return doc


def _tabela_principal(items: list[dict]) -> list[int]:
    """
    Renderiza a tabela principal com os insumos do MCP e retorna
    os índices selecionados via coluna de checkbox.
    """
    import pandas as pd
    def fmt_pct(x):
        try:
            return round(float(x) * 100, 2)
        except Exception:
            return None

    cols = [
        "mlb", "title", "gtin", "regiao", "logistic_type",
        "preco_efetivo", "price", "rebate_price_discounted",
        "preco_compra", "frete_sobre_custo", "custo_fixo_full",
        "comissao", "comissao_pct", "marketing", "marketing_pct",
        "imposto", "imposto_pct", "subsidio_ml_valor",
        "mcp_abs", "mcp_pct",
    ]
    df = pd.DataFrame([{c: it.get(c) for c in cols} for it in items])

    for c in ("comissao_pct", "marketing_pct", "imposto_pct", "mcp_pct"):
        if c in df.columns:
            df[c] = df[c].map(fmt_pct)

    rename = {
        "title": "Título", "logistic_type": "Logística", "regiao": "Região",
        "preco_efetivo": "Preço efetivo (R$)", "price": "Preço (R$)",
        "rebate_price_discounted": "Preço com rebate (R$)",
        "preco_compra": "Preço de custo (R$)", "frete_sobre_custo": "Frete (R$)",
        "custo_fixo_full": "Custo fixo FULL (R$)",
        "comissao": "Comissão (R$)", "comissao_pct": "Comissão (%)",
        "marketing": "Marketing (R$)", "marketing_pct": "Marketing (%)",
        "imposto": "Imposto (R$)", "imposto_pct": "Imposto (%)",
        "subsidio_ml_valor": "Subsídio ML (R$)",
        "mcp_abs": "MCP (R$)", "mcp_pct": "MCP (%)",
    }
    df = df.rename(columns=rename)

    df.insert(0, "Selecionar", False)

    st.caption("Marque uma ou mais linhas e desça para ver os anúncios com o mesmo GTIN e a simulação de MCP.")
    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(required=False, help="Marque para detalhar/simular")
        },
        num_rows="fixed",
        disabled=[c for c in df.columns if c != "Selecionar"],
        key="prec_tabela_principal",
    )

    sel_rows = edited.index[edited["Selecionar"]].tolist()
    return sel_rows


def _tabela_mesmo_gtin(items_universo: list[dict], gtin: str):
    import pandas as pd
    rel = [x for x in items_universo if (x.get("gtin") or "").strip() == (gtin or "").strip()]
    if not rel:
        st.info("Nenhum outro anúncio encontrado com o mesmo GTIN no universo completo (SP+MG).")
        return
    cols = ["mlb", "title", "regiao", "logistic_type", "price", "rebate_price_discounted", "preco_efetivo"]
    df = pd.DataFrame([{c: r.get(c) for c in cols} for r in rel]).rename(columns={
        "title": "Título", "regiao": "Região", "logistic_type": "Logística",
        "price": "Preço (R$)", "rebate_price_discounted": "Preço com rebate (R$)",
        "preco_efetivo": "Preço efetivo (R$)",
    })
    st.subheader("Anúncios com o mesmo GTIN (sem filtros de Região/Logística/Buscar)")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _simulador(item: dict):
    st.markdown("---")
    st.subheader("Simulador de MCP (preço + subsídio)")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        preco_sim = st.number_input("Preço simulado (R$)", min_value=0.0, value=float(item.get("preco_efetivo") or item.get("price") or 0.0), step=0.1)
    with c2:
        subsidio = st.number_input("Subsídio ML (R$)", min_value=0.0, value=float(item.get("subsidio_ml_valor") or 0.0), step=0.1)
    with c3:
        st.write("")
        disparar = st.button("Calcular MCP simulado", use_container_width=True)

    if disparar:
        res = simular_mcp_item(item, preco_venda=preco_sim, subsidio_valor=subsidio)
        if res.get("error"):
            st.error(f"Erro na simulação: {res['error']}")
            return
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("MCP simulado (R$)", f"{res['mcp_abs']:.2f}")
        k2.metric("MCP simulado (%)", f"{(res['mcp_pct'] or 0)*100:.2f}%")
        k3.metric("Comissão (R$)", f"{res['comissao_brl']:.2f}")
        k4.metric("Custo fixo FULL (R$)", f"{res['custo_fixo_full']:.2f}")
        with st.expander("Decomposição completa"):
            st.json(res, expanded=False)

def _norm_windows(payload: dict) -> dict:
    """
    Aceita o dicionário retornado por get_resumos(...) e tenta extrair contagens
    das janelas 7/15/30, tolerando variações de shape.
    Retorna um dict padronizado: {"w7": int, "w15": int, "w30": int}
    """
    if not isinstance(payload, dict):
        return {"w7": 0, "w15": 0, "w30": 0}

    data = payload.get("result", payload)

    def _take(x):
        if isinstance(x, dict):
            for k in ("qtd", "count", "total", "value", "sum"):
                if k in x and isinstance(x[k], (int, float)):
                    return int(x[k])
            # último recurso: tenta converter diretamente
            try:
                return int(x.get("qty") or 0)
            except Exception:
                return 0
        try:
            return int(x)
        except Exception:
            return 0

    # tenta várias chaves usuais
    w7  = _take(data.get("w7",  data.get("7",  0)))
    w15 = _take(data.get("w15", data.get("15", 0)))
    w30 = _take(data.get("w30", data.get("30", 0)))

    # fallback: quando as chaves vêm como strings variadas
    if (w7, w15, w30) == (0, 0, 0):
        acc = {}
        for k, v in (data.items() if isinstance(data, dict) else []):
            ks = str(k).lower().replace("days", "").replace("day", "").replace(" ", "")
            ks = ks.replace("janela", "").replace("window", "").replace("w", "")
            try:
                d = int(ks)
                if d in (7, 15, 30):
                    acc[f"w{d}"] = _take(v)
            except Exception:
                pass
        w7, w15, w30 = acc.get("w7", 0), acc.get("w15", 0), acc.get("w30", 0)

    return {"w7": w7, "w15": w15, "w30": w30}


def _coletar_vendas_mlb_por_janelas(mlb: str, reg_label: str) -> dict:
    """
    Lê o agregado do service de vendas no mesmo formato do dashboard de vendas.
    Retorna {"w7": int, "w15": int, "w30": int} para o MLB selecionado.
    """
    mlb = (mlb or "").strip()
    if not mlb:
        return {"w7": 0, "w15": 0, "w30": 0}

    # escolhe a fonte conforme Região na UI
    if reg_label.strip().upper().startswith("SP"):
        agg = get_por_mlb("sp", windows=(7, 15, 30))
    elif reg_label.strip().upper().startswith("MG"):
        agg = get_por_mlb("mg", windows=(7, 15, 30))
    else:
        # SP + MG (Brasil)
        agg = get_por_mlb_br(windows=(7, 15, 30))

    payload = (agg or {}).get(mlb, {})
    windows = payload.get("windows", {})

    def _q(win: int) -> int:
        w = windows.get(str(win)) or {}
        try:
            return int(w.get("qty_total") or 0)
        except Exception:
            return 0

    return {"w7": _q(7), "w15": _q(15), "w30": _q(30)}

def _render_secao_vendas_mlb(mlb: str, reg_label: str):
    st.markdown("---")
    st.subheader("Vendas do anúncio (MLB) nos últimos 7/15/30 dias")

    win = _coletar_vendas_mlb_por_janelas(mlb, reg_label)
    c1, c2, c3 = st.columns(3)
    c1.metric("7 dias",  f"{win['w7']}")
    c2.metric("15 dias", f"{win['w15']}")
    c3.metric("30 dias", f"{win['w30']}")

def _lojas_from_reg_label(reg_label: str) -> list[str]:
    s = (reg_label or "").strip().upper()
    if s.startswith("SP"):
        return ["sp"]
    if s.startswith("MG"):
        return ["mg"]
    # "SP + MG" ou qualquer visão Brasil
    return ["sp", "mg"]


def _coletar_estoque_por_mlb(mlb: str, reg_label: str) -> dict:
    """
    Lê o estoque (PP) do anúncio por MLB para as lojas derivadas da região da UI.
    Retorno:
      {
        "por_loja": {"sp": float|int, "mg": float|int},
        "total": float|int
      }
    """
    mlb = (mlb or "").strip()
    if not mlb:
        return {"por_loja": {}, "total": 0}

    por_loja = {}
    for loja in _lojas_from_reg_label(reg_label):
        try:
            rec = obter_anuncio_por_mlb_pp(loja, mlb)  # retorna dict PP ou None
            est = rec.get("estoque") if isinstance(rec, dict) else 0
            # normaliza para número
            try:
                est = float(est) if est is not None else 0.0
            except Exception:
                est = 0.0
            por_loja[loja] = est
        except Exception:
            por_loja[loja] = 0.0

    total = sum(por_loja.values()) if por_loja else 0.0
    return {"por_loja": por_loja, "total": total}


def _render_secao_estoque_mlb(mlb: str, reg_label: str):
    st.markdown("---")
    st.subheader("Estoque do anúncio no Mercado Livre (PP)")

    info = _coletar_estoque_por_mlb(mlb, reg_label)
    sp = info["por_loja"].get("sp", 0)
    mg = info["por_loja"].get("mg", 0)
    total = info["total"]

    lojas = _lojas_from_reg_label(reg_label)
    if lojas == ["sp"]:
        st.metric("Estoque (SP)", f"{int(sp) if float(sp).is_integer() else sp}")
    elif lojas == ["mg"]:
        st.metric("Estoque (MG)", f"{int(mg) if float(mg).is_integer() else mg}")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("SP", f"{int(sp) if float(sp).is_integer() else sp}")
        c2.metric("MG", f"{int(mg) if float(mg).is_integer() else mg}")
        c3.metric("Total SP+MG", f"{int(total) if float(total).is_integer() else total}")

    # === NOVO: card de cobertura 40/35/25 ===
    # Lê janelas no mesmo formato do dashboard de vendas
    if lojas == ["sp"]:
        agg = get_por_mlb("sp", windows=(7, 15, 30))
    elif lojas == ["mg"]:
        agg = get_por_mlb("mg", windows=(7, 15, 30))
    else:
        agg = get_por_mlb_br(windows=(7, 15, 30))

    windows = (agg or {}).get(mlb, {}).get("windows", {})

    cov = calcular_cobertura_estoque(total, windows)
    st.metric("Cobertura estimada (40/35/25)", cov["dias_cobertura_str"],
              help=f"Consumo/dia (pond.): {cov['consumo_dia_pond']:.2f}")

def render():
    st.title("Precificação — Dashboard")

    # Filtros (casca)
    col1, col2 = st.columns(2)
    with col1:
        reg_label = st.selectbox(
            "Região",
            options=["SP", "MG", "SP + MG"],
            index=0,
            help="Escolha SP, MG ou as duas regiões juntas."
        )
    with col2:
        modo = st.selectbox("Logística", options=["Todos", "Fulfillment", "Seller"])

    filtro_texto = st.text_input(
        "Buscar (MLB/GTIN/Título)",
        placeholder="Digite parte do título, MLB ou GTIN…",
        help="Correspondência parcial, sem diferenciar maiúsculas/minúsculas."
    )

    # --- Montagem dos datasets ---
    # Universo completo (sempre SP+MG, sem filtros) para a seção "mesmo GTIN"
    doc_universo = _dataset_memoria_multi([Regiao.SP, Regiao.MG])
    itens_universo = doc_universo.get("itens", [])

    # Visão da grade principal (respeita Região selecionada + filtros)
    if reg_label == "SP + MG":
        doc_view = doc_universo  # reaproveita, evita recomputar
    else:
        reg = Regiao.SP if reg_label == "SP" else Regiao.MG
        doc_view = _dataset_memoria_multi([reg])

        # Coleta statuses existentes no dataset (normaliza para lower)
    status_all = sorted({(it.get("status") or "unknown").lower() for it in doc_view.get("itens", [])})
    # Sugerir padrão “tudo selecionado”
    status_sel = st.multiselect(
        "Status dos anúncios",
        options=status_all,
        default=status_all,
        help="Escolha quais status quer ver na tabela principal (ex.: active, paused, under_review)."
    )

    def _filtrar_por_status(items, status_allowed):
        ok = {s.lower() for s in (status_allowed or [])}
        if not ok:
            return []  # nada selecionado → lista vazia
        return [x for x in items if (x.get("status") or "unknown").lower() in ok]

    # aplica à visão principal, junto com Logística e Busca
    itens_view = _filtrar_por_logistica(doc_view.get("itens", []), modo)
    itens_view = _aplicar_filtro_busca(itens_view, filtro_texto)
    itens_view = _filtrar_por_status(itens_view, status_sel)

    # --- Renderização ---
    st.markdown("### Itens para Precificação")
    st.caption(f"{len(itens_view)} itens após filtros (região: {reg_label}).")
    sel_rows = _tabela_principal(itens_view)

    if sel_rows:
        idx = sel_rows[0]
        if 0 <= idx < len(itens_view):
            item = itens_view[idx]
            gtin = (item.get("gtin") or "").strip()
            # ATENÇÃO: passa o UNIVERSO (sem filtros) para a tabela “mesmo GTIN”
            _tabela_mesmo_gtin(itens_universo, gtin=gtin)
            _simulador(item)
            _render_cards_metricas(item)
            _render_secao_vendas_mlb(item.get("mlb") or "", reg_label)
            _render_secao_estoque_mlb(item.get("mlb") or "", reg_label)
        else:
            st.info("Marque pelo menos uma linha ...")
def _render_cards_metricas(item: dict):
    st.markdown("### Métricas & Preços-alvo")

    def m(v):
        try:
            return f"{float(v):.2f}"
        except Exception:
            return "—"

    def pct(v):
        try:
            x = float(v) * 100.0
            return f"{x:.2f}%"
        except Exception:
            return "—"

    pe   = item.get("preco_efetivo") or item.get("rebate_price_discounted") or item.get("price")
    pmin = item.get("preco_min") or item.get("preco_minimo")
    pmax = item.get("preco_max") or item.get("preco_maximo")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Preço atual (R$)", m(pe))
    c2.metric("MCP (R$ / %)",
              f"{m(item.get('mcp_abs'))}",
              pct(item.get('mcp_pct')))
    c3.metric("Comissão ML (R$ / %)",
              f"{m(item.get('comissao'))}",
              pct(item.get('comissao_pct')))
    c4.metric("Custo fixo ML (R$)", m(item.get("custo_fixo_full")))

    c5, c6, c7, c8 = st.columns(4)
    faixa = (m(pmin) if pmin is not None else "—") + "  →  " + (m(pmax) if pmax is not None else "—")
    c5.metric("Faixa alvo (min → máx)", faixa)
    c6.metric("Preço de custo (R$)", m(item.get("preco_compra")))
    c7.metric("Imposto (R$ / %)",
              f"{m(item.get('imposto'))}",
              pct(item.get('imposto_pct')))
    c8.metric("Marketing (R$ / %)",
              f"{m(item.get('marketing'))}",
              pct(item.get('marketing_pct')))

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Frete (R$)", m(item.get("frete_sobre_custo") or item.get("frete_full")))
    c10.metric("Subsídio ML (R$ / taxa)", m(item.get("subsidio_ml_valor")), pct(item.get("subsidio_ml_taxa")))
    c11.metric("Logística", (item.get("logistic_type") or "—").upper())
    c12.metric("GTIN / MLB", f"{item.get('gtin') or '—'} / {item.get('mlb') or '—'}")
