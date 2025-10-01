from __future__ import annotations

from typing import Dict, Any, Iterable, List
import pandas as pd

from ..config import excel_dir
from ..excel.ingest import (
    carregar_faturamento_mp, carregar_faturamento_ml,
    carregar_tarifas_full, carregar_pagamento_faturas,
)
from ..excel.conceitos import categorias_fatura_ml

# === já existiam ===
from .aggregator import carregar_zip_dir
from ..config import billing_zip_raw_dir

def carregar_e_normalizar(*, market: str, ano: int, mes: int, regioes: Iterable[str]) -> List[Dict[str, Any]]:
    # (mantido para XML) ...
    all_notas: List[Dict[str, Any]] = []
    for regiao in regioes:
        dir_raw = billing_zip_raw_dir(market, ano, mes, regiao)
        notas = carregar_zip_dir(dir_raw=dir_raw, regiao=regiao, market=market)
        all_notas.extend(notas)
    by_id = {}
    for n in all_notas:
        by_id[n.get("id_unico")] = n
    return list(by_id.values())

# === novo: consolidação Excel ===
def consolidar_excel(*, market: str, ano: int, mes: int, regioes: Iterable[str]) -> Dict[str, Any]:
    """
    Consolida os três relatórios Excel (MP, ML, Full) e reconcilia com Pagamento de Faturas.
    Considera todas as regiões pedidas; soma e retorna totais mensais.
    """
    cats = list(categorias_fatura_ml())

    total_cobrancas = {c: 0.0 for c in cats}
    total_pagamentos = 0.0
    detalhes_por_fonte = {"MP": None, "ML": None, "FULL": None, "PAY": None}

    frames_mp, frames_ml, frames_full, frames_pay = [], [], [], []

    for reg in regioes:
        d = excel_dir(market, ano, mes, reg)

        mp = carregar_faturamento_mp(d)
        ml = carregar_faturamento_ml(d)
        fu = carregar_tarifas_full(d)
        pay = carregar_pagamento_faturas(d)

        if not mp.empty:
            g = mp.groupby("__categoria__", dropna=False)["__valor__"].sum()
            for c, v in g.items():
                if c in total_cobrancas:
                    total_cobrancas[c] += float(v or 0.0)
            frames_mp.append(mp)
        if not ml.empty:
            g = ml.groupby("__categoria__", dropna=False)["__valor__"].sum()
            for c, v in g.items():
                if c in total_cobrancas:
                    total_cobrancas[c] += float(v or 0.0)
            frames_ml.append(ml)
        if not fu.empty:
            g = fu.groupby("__categoria__", dropna=False)["__valor__"].sum()
            for c, v in g.items():
                if c in total_cobrancas:
                    total_cobrancas[c] += float(v or 0.0)
            frames_full.append(fu)
        if not pay.empty:
            total_pagamentos += float(pay["__valor_mes__"].fillna(0).sum())
            frames_pay.append(pay)

    total_cobrancas_num = sum(total_cobrancas.values())
    reconc = {
        "total_cobrancas": round(total_cobrancas_num, 2),
        "total_pagamentos": round(total_pagamentos, 2),
        "diferenca": round(total_pagamentos - total_cobrancas_num, 2),
    }

    # anexar detalhes (compactos)
    if frames_mp:
        detalhes_por_fonte["MP"] = pd.concat(frames_mp, ignore_index=True).to_dict(orient="records")
    if frames_ml:
        detalhes_por_fonte["ML"] = pd.concat(frames_ml, ignore_index=True).to_dict(orient="records")
    if frames_full:
        detalhes_por_fonte["FULL"] = pd.concat(frames_full, ignore_index=True).to_dict(orient="records")
    if frames_pay:
        detalhes_por_fonte["PAY"] = pd.concat(frames_pay, ignore_index=True).to_dict(orient="records")

    return {
        "fatura_por_categoria": {k: round(float(v), 2) for k, v in total_cobrancas.items()},
        "resumo": reconc,
        "detalhes_por_fonte": detalhes_por_fonte,
        "categorias": cats,
        "parametros": {"market": market, "ano": ano, "mes": mes, "regioes": list(regioes)},
    }
