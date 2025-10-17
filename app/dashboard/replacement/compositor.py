# app/dashboard/replacement/compositor.py
from __future__ import annotations

from typing import Dict, List

# ✅ Dashboard consome apenas services (diretriz do projeto)
from app.utils.replacement.service import (
    estimativa_consumo_por_mlb,
    estimativa_consumo_por_gtin_br,
)


def _coerce_int(x) -> int:
    try:
        return int(round(float(x)))
    except Exception:
        return 0


# 1) troque a função de cálculo local
def _calc_reposicao_sugerida(row: Dict, horizonte: int) -> int:
    """
    reposição_sugerida_H = max(0, venda_prevista_H - estoque_pos_lead_7_clamped)
    onde estoque_pos_lead_7_clamped = max(0, estoque_pos_lead_7 ou 0)
    """
    prev = row.get("venda_prevista_30" if horizonte == 30 else "venda_prevista_60",
                   row.get("estimado_30" if horizonte == 30 else "estimado_60", 0))

    # pega pos_lead de qualquer das chaves e CLAMPA a zero
    pos7_raw = (row.get("estoque_pos_delay_7")
                if row.get("estoque_pos_delay_7") is not None
                else row.get("estoque_pos_lead_7"))
    pos7 = 0 if pos7_raw is None else max(0, _coerce_int(pos7_raw))

    return max(0, _coerce_int(prev) - pos7)

def _normalize_row(row: Dict, key_field: str) -> Dict:
    out = dict(row or {})

    # Previsões (padroniza nome)
    out["venda_prevista_30"] = _coerce_int(
        row.get("venda_prevista_30", row.get("estimado_30", 0))
    )
    out["venda_prevista_60"] = _coerce_int(
        row.get("venda_prevista_60", row.get("estimado_60", 0))
    )

    # Vendidos (7/15/30)
    out["sold_7"] = _coerce_int(row.get("sold_7"))
    out["sold_15"] = _coerce_int(row.get("sold_15"))
    out["sold_30"] = _coerce_int(row.get("sold_30"))

    # Estoques
    if row.get("estoque_pos_delay_7") is not None:
        out["estoque_pos_delay_7"] = max(0, _coerce_int(row.get("estoque_pos_delay_7")))
    elif row.get("estoque_pos_lead_7") is not None:
        out["estoque_pos_delay_7"] = max(0, _coerce_int(row.get("estoque_pos_lead_7")))
    else:
        out["estoque_pos_delay_7"] = 0  # se não houver, considera 0
    if row.get("estoque_atual") is not None:
        out["estoque_atual"] = _coerce_int(row.get("estoque_atual"))

    # ✅ Recalcula SEMPRE a reposição sugerida localmente (não usa valor do service)
    out["reposicao_sugerida_30"] = _calc_reposicao_sugerida(out, 30)
    out["reposicao_sugerida_60"] = _calc_reposicao_sugerida(out, 60)

    # 🔁 Aliases p/ compatibilidade (quem ainda lê compra_sugerida_*)
    out["compra_sugerida_30"] = out["reposicao_sugerida_30"]
    out["compra_sugerida_60"] = out["reposicao_sugerida_60"]

    # Chaves e apresentação
    out[key_field] = row.get(key_field)
    out["title"] = row.get("title")
    out["gtin"] = row.get("gtin")
    out["mlb"] = row.get("mlb")
    return out


def _dict_to_sorted_list(d: Dict[str, Dict], key_field: str) -> List[Dict]:
    """
    Converte {chave: row} ⇒ [row...] já normalizado e ordenado (determinístico).
    Critério: title (asc), depois chave natural.
    """
    rows = []
    for k, v in (d or {}).items():
        v = dict(v or {})
        v.setdefault(key_field, k)
        rows.append(_normalize_row(v, key_field))
    rows.sort(key=lambda r: (str(r.get("title") or "").lower(), str(r.get(key_field) or "")))
    return rows


# -------------------- Facades para a página --------------------

def resumo_sp_mlb() -> List[Dict]:
    """
    SP por MLB — retorna lista de dicts com:
      sold_7/15/30, venda_prevista_30/60, estoque_atual, estoque_pos_delay_7,
      reposicao_sugerida_30/60, title, mlb, gtin.
    """
    data = estimativa_consumo_por_mlb("sp", windows=(7, 15, 30)) or {}
    return _dict_to_sorted_list(data, key_field="mlb")


def resumo_mg_mlb() -> List[Dict]:
    """MG por MLB — mesmo shape do resumo_sp_mlb()."""
    data = estimativa_consumo_por_mlb("mg", windows=(7, 15, 30)) or {}
    return _dict_to_sorted_list(data, key_field="mlb")


def resumo_br_gtin() -> List[Dict]:
    """BR (SP+MG) por GTIN — mesmo shape, chave natural = gtin."""
    data = estimativa_consumo_por_gtin_br(windows=(7, 15, 30)) or {}
    return _dict_to_sorted_list(data, key_field="gtin")
