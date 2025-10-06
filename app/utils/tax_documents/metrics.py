from __future__ import annotations
from typing import Iterable, Dict, Any, List
from collections import defaultdict

# Campos de cabeçalho (se repetem por item ⇒ usar por NF)
_CAMPOS_HEADER = [
    "Valor Produtos","Frete","Seguro","Outras Despesas","Desconto",
    "Valor IPI","Valor ICMS","Valor ICMS Subst","Valor Nota","Total Faturado",
    "Base ICMS","Base ICMS Subst",
    "Valor Imposto Simples / ICMS","Valor Imposto ST / ICMS",
    "Valor Imposto COFINS","Valor Imposto PIS",
    "Valor Imposto IPI","Valor Imposto II",
]
# ⚠️ Bases de PIS/COFINS são POR ITEM:
CAMPOS_ITEM_SOMA = [
    "Valor Base COFINS","Valor Base PIS",
    "Valor Base Simples / ICMS","Valor Base Calculo Simples / ICMS",  # se quiser somar como item
]

def _to_num(x) -> float:
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0

def _dedup_por_nota(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Para cada ID Nota, escolhe UM registro representativo (cabeçalho) por NF.
    Estratégia: mantém o primeiro que aparecer por ID Nota e zera os demais
    campos de cabeçalho. Assim, ao somar, cada NF conta uma vez só.
    """
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in rows:
        nid = r.get("ID Nota") or r.get("Chave de acesso") or ""
        if nid not in seen:
            seen.add(nid)
            out.append(dict(r))  # mantém original
        else:
            # zera campos de cabeçalho (para não somar de novo)
            rr = dict(r)
            for k in _CAMPOS_HEADER:
                if k in rr:
                    rr[k] = 0
            out.append(rr)
    return out

def aggregate_por_natureza_sem_dedup(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Versão antiga (soma direta nas linhas) — deixa aqui se quiser comparar/debugar."""
    acc = defaultdict(lambda: {k: 0.0 for k in _CAMPOS_HEADER})
    for r in rows:
        nat = (r.get("Natureza") or "").strip() or "(sem natureza)"
        for k in _CAMPOS_HEADER:
            acc[nat][k] += _to_num(r.get(k))
    return [{"Natureza": nat, **{k: round(v, 2) for k, v in acc[nat].items()}} for nat in sorted(acc)]

def _dedup_por_nota_preservando_items(rows):
    """
    Mantém 1ª linha da NF com os CAMPOS_HEADER; zera CAMPOS_HEADER nas demais
    linhas da mesma NF; NUNCA zera CAMPOS_ITEM_SOMA (eles serão somados por item).
    """
    seen = set()
    out = []
    for r in rows:
        nid = r.get("ID Nota") or r.get("Chave de acesso") or ""
        rr = dict(r)
        if nid in seen:
            for k in _CAMPOS_HEADER:
                if k in rr:
                    rr[k] = 0
        else:
            seen.add(nid)
        out.append(rr)
    return out

def aggregate_por_natureza_dedup_por_nota(rows):
    rows_nf = _dedup_por_nota_preservando_items(rows)
    acc = {}
    for r in rows_nf:
        nat = (r.get("Natureza") or "").strip() or "(sem natureza)"
        if nat not in acc:
            acc[nat] = {k: 0.0 for k in (_CAMPOS_HEADER + CAMPOS_ITEM_SOMA)}
        # soma cabeçalho (uma vez por NF)
        for k in _CAMPOS_HEADER:
            acc[nat][k] += _to_num(r.get(k))
        # soma itens (todas as linhas)
        for k in CAMPOS_ITEM_SOMA:
            acc[nat][k] += _to_num(r.get(k))
    return [
        {"Natureza": nat, **{k: round(v, 2) for k, v in vals.items()}}
        for nat, vals in sorted(acc.items())
    ]