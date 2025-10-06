from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from app.config.paths import Regiao

# filtros/IO do domínio
from .filters import (
    filtrar_por_modo,
    filtrar_por_situacao,
    pos_filtro_por_provedor,
    filtrar_por_cfop,
)

from .aggregator import carregar_linhas, gravar_pp
from .config import (
    COLUMNS,
    CFOPS_REVENDA,
    CFOPS_VENDA_PROPRIA,  # novos conjuntos por CFOP (venda própria × revenda)
    pp_consolidado_excel_path,
    pp_json_path,
    pp_month_dir,
    pp_resumo_json_path,
)

from app.utils.core.result_sink.service import build_sink
from .metrics import aggregate_por_natureza_dedup_por_nota

# --------------------------------------
# Constantes internas / discovery helpers
# --------------------------------------
_PROVIDERS = ("meli", "amazon", "bling")
_BACKUP_PAT = re.compile(r"(^\.|backup)", re.IGNORECASE)


def _is_valid_subdir(p: Path) -> bool:
    return p.is_dir() and not _BACKUP_PAT.search(p.name)


def _coerce_regiao(name: str) -> Optional[Union[Regiao, str]]:
    """Tenta mapear para Enum; senão retorna a própria string (minúscula)."""
    if not name:
        return None
    key = name.strip()
    try:
        return Regiao[key.upper()]
    except Exception:
        pass
    try:
        for r in Regiao:
            if r.value.lower() == key.lower():
                return r
    except Exception:
        pass
    return key.lower()


def _iter_buckets_mes(ano: int, mes: int) -> List[Tuple[str, Optional[Union[Regiao, str]]]]:
    """
    Retorna [(provider, regiao|None)] apenas para buckets que realmente possuem
    'tax_documents_pp.json'. Tolera regiões fora do Enum. Ignora backups.
    """
    buckets: List[Tuple[str, Optional[Union[Regiao, str]]]] = []
    for prov in _PROVIDERS:
        month_root = Path(pp_month_dir(prov, ano, mes, regiao=None))
        if not month_root.exists():
            continue

        # PP direto na raiz do mês (sem região)
        if Path(pp_json_path(prov, ano, mes, regiao=None)).exists():
            buckets.append((prov, None))

        # Subpastas como regiões
        subs = sorted([p for p in month_root.iterdir() if _is_valid_subdir(p)], key=lambda x: x.name.lower())
        for sub in subs:
            reg = _coerce_regiao(sub.name)
            if Path(pp_json_path(prov, ano, mes, reg)).exists():
                buckets.append((prov, reg))
    return buckets


# -----------------
# Helpers numéricos
# -----------------
def _to_float(x) -> float:
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0


def _digits_only(s: str) -> str:
    return "".join(c for c in str(s or "") if c.isdigit())


def _cnpj_from_row(row: Dict[str, Any]) -> str:
    """
    Extrai CNPJ do emissor:
    1) campos conhecidos; 2) fallback pela chave da NFe (pos. 6..19 dos 44 dígitos).
    """
    for key in ("CNPJ Emissor", "CNPJ Emitente", "CNPJ"):
        val = (row.get(key) or "").strip()
        if val:
            return val
    ch = _digits_only(row.get("Chave de acesso", ""))
    return ch[6:20] if len(ch) >= 20 else ""


def _load_pp_rows_from_json(provider: str, ano: int, mes: int, regiao=None, *, debug: bool = False) -> List[Dict[str, Any]]:
    src = pp_json_path(provider, ano, mes, regiao)
    if debug:
        print(f"[DEBUG] Lendo PP JSON: {src}")
    doc = json.loads(Path(src).read_text(encoding="utf-8"))
    return doc.get("rows") or []


def _sum_valor_nota_dedup_por_nota(rows: List[dict]) -> float:
    """Soma 'Valor Nota' contando cada NF uma única vez (dedupe por ID Nota/Chave)."""
    seen = set()
    total = 0.0
    for r in rows:
        nid = r.get("ID Nota") or r.get("Chave de acesso") or ""
        if not nid:
            total += _to_float(r.get("Valor Nota", 0))
            continue
        if nid in seen:
            continue
        seen.add(nid)
        total += _to_float(r.get("Valor Nota", 0))
    return total


# ================
# Services públicos
# ================
def gerar_pp_json(
    provider: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]] = None,
    *, dry_run: bool = False, debug: bool = False
) -> str:
    """Gera o canônico PP (JSON) a partir dos ZIP/XML do mês."""
    rows = carregar_linhas(provider, ano, mes, regiao, debug=debug)
    return gravar_pp(provider, ano, mes, regiao, rows, dry_run=dry_run, debug=debug)


def gerar_resumo_por_natureza_from_pp(
    provider: str, ano: int, mes: int, regiao=None, *,
    modo: str = "todos", somente_autorizadas: bool = False,
    dry_run: bool = False, debug: bool = False
) -> str:
    """
    Lê o PP JSON e grava o resumo por Natureza.
    'modo' aplica filtro por CFOP (vendas/transferências/outros/todos) antes da agregação.
    A agregação deduplica por NF antes de somar cabeçalhos (evita duplicidade em notas multi-itens).
    """
    rows = _load_pp_rows_from_json(provider, ano, mes, regiao, debug=debug)
    rows = filtrar_por_modo(rows, modo)
    if somente_autorizadas:
        rows = filtrar_por_situacao(rows, {"autorizada"})
    rows = pos_filtro_por_provedor(rows, provider)

    resumo = aggregate_por_natureza_dedup_por_nota(rows)
    if not resumo:
        raise ValueError("DQ: PP existe mas não retornou linhas no filtro solicitado.")

    payload = {
        "_meta": {
            "filtro_cfop_modo": modo,
            "somente_autorizadas": bool(somente_autorizadas),
            "source_paths": [str(pp_json_path(provider, ano, mes, regiao))],
            "dedup_por_nota": True,
        },
        "rows": resumo,
    }
    target = pp_resumo_json_path(provider, ano, mes, regiao)
    sink = build_sink("json_file", target_path=target, do_backup=True, pretty=True)
    sink.write(payload, dry_run=dry_run, debug=debug)
    return str(target)


def gerar_excel_consolidado(ano: int, mes: int) -> str:
    """
    Excel detalhado (linha-a-linha / 1 linha por item).
    Inclui 'Situacao NFe' e 'CNPJ Emissor'. Ordenação determinística.
    """
    rows_all: List[Dict[str, Any]] = []

    for prov, reg in _iter_buckets_mes(ano, mes):
        p = Path(pp_json_path(prov, ano, mes, reg))
        doc = json.loads(p.read_text(encoding="utf-8"))
        rows = (doc.get("rows") or [])
        rows = pos_filtro_por_provedor(rows, prov)  # série=1 no Bling
        for r in rows:
            out = {col: r.get(col, "") for col in COLUMNS}
            out["Situacao NFe"] = r.get("Situacao NFe", out.get("Situacao NFe", ""))
            out["CNPJ Emissor"] = _cnpj_from_row(r)
            out["_provedor"] = prov
            out["_regiao"] = reg.value if isinstance(reg, Regiao) else (reg or "")
            rows_all.append(out)

    if not rows_all:
        raise ValueError("Nenhum PP JSON encontrado para o período.")

    df = pd.DataFrame(rows_all)

    for c in ("ID Nota", "_provedor", "_regiao", "Item Codigo"):
        if c not in df.columns:
            df[c] = ""
    df.sort_values(["ID Nota", "_provedor", "_regiao", "Item Codigo"], inplace=True, kind="mergesort")

    ordered_cols = COLUMNS + ["Situacao NFe", "CNPJ Emissor", "_provedor", "_regiao"]
    df = df.reindex(columns=ordered_cols)

    target = pp_consolidado_excel_path(ano, mes)
    df.to_excel(target, index=False)
    return str(target)


def gerar_excel_consolidado_por_nota(ano: int, mes: int) -> str:
    """
    Excel com UMA LINHA POR NF-e.
    - Cabeçalhos: 'first' (não somar).
    - Situação por nota: cancelada > denegada > autorizada.
    - Bling: filtra automaticamente Serie == '1'.
    """
    buckets = _iter_buckets_mes(ano, mes)
    if not buckets:
        raise ValueError("Nenhum PP JSON disponível para o período.")

    rows_all: List[Dict[str, Any]] = []
    for prov, reg in buckets:
        p = Path(pp_json_path(prov, ano, mes, reg))
        doc = json.loads(p.read_text(encoding="utf-8"))
        for r in (doc.get("rows") or []):
            d = dict(r)
            d["_provedor"] = prov
            d["_regiao"] = reg.value if isinstance(reg, Regiao) else (reg or "")
            d["CNPJ Emissor"] = _cnpj_from_row(r)
            rows_all.append(d)

    if not rows_all:
        raise ValueError("Nenhuma linha encontrada nos PP JSON do mês.")

    df = pd.DataFrame(rows_all)

    # Filtro: Bling só série 1
    if "_provedor" in df.columns:
        is_bling = df["_provedor"].eq("bling")
        if "Serie" in df.columns:
            df = df[~is_bling | df["Serie"].astype(str).eq("1")]

    # Cabeçalhos por NF (não somar)
    cols_fixas = [
        "ID Nota", "Serie", "Numero Nota", "Data emissao", "Data saída",
        "Regime Tributario", "Natureza", "CNPJ Emissor", "Situacao NFe",
        "Contato", "CPF / CNPJ", "Municipio", "UF", "Cep", "Endereco", "Nro",
        "Bairro", "Complemento", "E-mail", "Fone",
        "Peso líquido", "Peso bruto", "Frete por conta", "Observacoes", "Chave de acesso",
        "Valor Nota", "Frete", "Seguro", "Outras Despesas", "Desconto",
        "Valor IPI", "Valor ICMS", "Valor ICMS Subst",
        "Base ICMS", "Base ICMS Subst",
        "Valor Base Simples / ICMS", "Valor Imposto Simples / ICMS",
        "Valor Base Calculo Simples / ICMS", "Valor Imposto ST / ICMS",
        "Valor Base COFINS", "Valor Imposto COFINS",
        "Valor Base PIS", "Valor Imposto PIS",
        "Valor Base IPI", "Valor Imposto IPI",
        "Valor Base II", "Valor Imposto II",
    ]
    item_sums: List[str] = []  # se quiser recompor somas por item no futuro

    for c in cols_fixas + item_sums + ["_provedor", "_regiao"]:
        if c not in df.columns:
            df[c] = ""

    s = df.get("Situacao NFe", "").astype(str).str.lower()
    df["_is_cancelada"] = s.eq("cancelada")
    df["_is_denegada"] = s.eq("denegada")

    grp_keys = ["ID Nota", "_provedor", "_regiao"]
    agg_map = {c: "first" for c in cols_fixas}
    agg_map.update({c: "sum" for c in item_sums})
    agg_map.update({"_is_cancelada": "max", "_is_denegada": "max"})
    df_agg = df.groupby(grp_keys, as_index=False).agg(agg_map)

    df_agg["Situacao NFe"] = "autorizada"
    df_agg.loc[df_agg["_is_denegada"] == 1, "Situacao NFe"] = "denegada"
    df_agg.loc[df_agg["_is_cancelada"] == 1, "Situacao NFe"] = "cancelada"

    df_agg.sort_values(["_provedor", "_regiao", "ID Nota"], inplace=True, kind="mergesort")
    ordered = cols_fixas + ["_provedor", "_regiao"]
    df_agg = df_agg.reindex(columns=ordered)

    p = Path(pp_consolidado_excel_path(ano, mes))
    target = p.with_name(p.stem + "_por_nota.xlsx")
    df_agg.to_excel(target, index=False)
    return str(target)


def totais_vendas_por_provedor_cfop(ano: int, mes: int, *, somente_autorizadas: bool = True) -> Tuple[Dict[str, Dict[str, float]], float]:
    """
    Soma 'Valor Nota' por **CFOP** para todos os provedores/regiões do mês:
      - venda:   CFOPS_VENDA_PROPRIA (ex.: 5101/6101)
      - revenda: CFOPS_REVENDA       (ex.: 5102/5405/6102/6405)
    Regras aplicadas: somente autorizadas (opcional), regra por provedor (ex.: Bling série=1),
    dedupe por NF, e total geral.
    Retorno: ({prov: {'venda','revenda','total'}}, total_geral)
    """
    out: Dict[str, Dict[str, float]] = {
        "meli": {"venda": 0.0, "revenda": 0.0, "total": 0.0},
        "amazon": {"venda": 0.0, "revenda": 0.0, "total": 0.0},
        "bling": {"venda": 0.0, "revenda": 0.0, "total": 0.0},
    }

    for prov, reg in _iter_buckets_mes(ano, mes):
        rows = _load_pp_rows_from_json(prov, ano, mes, reg)
        if somente_autorizadas:
            rows = filtrar_por_situacao(rows, {"autorizada"})
        rows = pos_filtro_por_provedor(rows, prov)

        venda_rows = filtrar_por_cfop(rows, incluir=CFOPS_VENDA_PROPRIA)
        rev_rows   = filtrar_por_cfop(rows, incluir=CFOPS_REVENDA)

        v = _sum_valor_nota_dedup_por_nota(venda_rows)
        r = _sum_valor_nota_dedup_por_nota(rev_rows)

        out[prov]["venda"] += v
        out[prov]["revenda"] += r
        out[prov]["total"] += (v + r)

    total_geral = sum(x["total"] for x in out.values())
    return out, total_geral