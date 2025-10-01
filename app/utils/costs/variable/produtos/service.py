# app/utils/costs/variable/produtos/service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from app.config.paths import Camada, Regiao, Marketplace  # Enums
from .config import (
    faturamento_pp_json,
    transacoes_base_json,
    transacoes_enriquecidas_json,
)
from .config import resumo_transacoes_json
from .aggregator import map_faturamento_to_transacoes

# ---- Helpers para localizar lista de registros dentro de diferentes schemas ----
_LIKELY_LIST_KEYS: Sequence[str] = ("records", "data", "items", "vendas", "linhas")
_LIKELY_ORDER_KEYS: Sequence[str] = ("numero_venda", "order_id", "id_venda")


def _project_root_from_here() -> Path:
    """
    Infere a raiz do repositório subindo a partir deste arquivo:
    .../<repo>/app/utils/costs/variable/produtos/service.py -> .../<repo>
    """
    here = Path(__file__).resolve()
    # Estrutura esperada: .../<repo>/app/utils/costs/variable/produtos/service.py
    if len(here.parents) >= 6 and here.parents[5].name == "app":
        return here.parents[6]
    for p in here.parents:
        if p.name == "app":
            return p.parent
    return here.parents[-1]


def _to_path(p: Union[str, Path]) -> Path:
    """
    Converte para Path e resolve placeholders ${BASE_PATH} / {BASE_PATH}
    para a raiz do repositório.
    """
    if isinstance(p, Path):
        return p
    s = str(p)
    if "${BASE_PATH}" in s or "{BASE_PATH}" in s:
        root = _project_root_from_here()
        s = s.replace("${BASE_PATH}", str(root)).replace("{BASE_PATH}", str(root))
    return Path(s)


def _find_records_container(obj: Any) -> List[Dict[str, Any]]:
    """
    Encontra a lista de registros dentro do JSON, sendo tolerante a variações de schema.
    """
    # Caso 1: já é lista de dicts
    if isinstance(obj, list) and (len(obj) == 0 or isinstance(obj[0], dict)):
        return obj  # type: ignore[return-value]

    # Caso 2: dict com chaves usuais
    if isinstance(obj, dict):
        for k in _LIKELY_LIST_KEYS:
            v = obj.get(k)
            if isinstance(v, list) and (len(v) == 0 or isinstance(v[0], dict)):
                return v
        # Caso 3: varredura em nível 1 por listas de dicts
        for v in obj.values():
            if isinstance(v, list) and (len(v) == 0 or isinstance(v[0], dict)):
                return v

    # Caso 4: nada encontrado
    return []


def _has_order_key(d: Dict[str, Any]) -> bool:
    return any(k in d for k in _LIKELY_ORDER_KEYS)


def read_faturamento_pp_and_build_transacoes(
    market: Marketplace,
    ano: int,
    mes: int,
    regiao: Regiao,
    *,
    debug: bool = False,
    source_path_override: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Lê o PP do faturamento (já normalizado) e gera transações por produto/venda.
    Tolerante a diferentes formatos de PP (list direta, records/data/items,...).
    """

    # Caminho do PP (string do helper) -> Path resolvido
    src = _to_path(source_path_override) if source_path_override else _to_path(
        faturamento_pp_json(market.value, ano, mes, regiao)
    )

    if debug:
        print(f"[DBG] fonte PP: {src}  (exists={src.exists()})")

    if not src.exists():
        # Mantemos retorno vazio (caller decide como tratar)
        if debug:
            print(f"[WARN] Arquivo de faturamento PP não encontrado: {src}")
        return []

    with src.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    records = _find_records_container(obj)
    if debug:
        print(f"[DBG] registros encontrados no PP: {len(records)}")
        if records:
            print(f"[DBG] chaves do primeiro registro: {list(records[0].keys())[:12]}")
            print(f"[DBG] possui chave de venda? {_has_order_key(records[0])}")

    transacoes = map_faturamento_to_transacoes(records)
    if debug:
        print(f"[DBG] transacoes geradas: {len(transacoes)}")
    return transacoes


# ================== NOVO: BASE (primeira operação) ==================
def read_transacoes_base(
    ano: int,
    mes: int,
    regiao: Regiao,
    camada: "Camada" = None,
    *,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """
    Lê results_transacoes_por_produto.json (primeira operação).
    Tolerante a schemas (lista direta ou containers usuais).
    """
    from app.config.paths import Camada as _Camada
    camada = camada or _Camada.PP
    src = _to_path(transacoes_base_json(ano, mes, regiao, camada))
    if debug:
        print(f"[DBG] fonte BASE: {src} (exists={src.exists()})")
    if not src.exists():
        return []
    with src.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    records = _find_records_container(obj)
    if debug:
        print(f"[DBG] base encontrados: {len(records)}")
    return records

def deduplicate_by_numero_venda_base(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mantém apenas UMA linha por numero_venda na BASE.
    - Se numero_venda for None, mantém (não deduplica).
    - Para vendas repetidas, preserva a PRIMEIRA ocorrência.
    """
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in records:
        nv = r.get("numero_venda")
        if nv is None:
            out.append(r)
            continue
        if nv in seen:
            continue
        seen.add(nv)
        out.append(r)
    return out

# ================== NOVO: leitura do ENRIQUECIDO + resumo + agregado ==================

def _to_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str):
            x = x.replace(".", "").replace(",", ".") if ("," in x and x.count(",") == 1) else x
        return float(x)
    except Exception:
        return None

def _to_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(x))
    except Exception:
        return None

def read_transacoes_enriquecidas(
    ano: int,
    mes: int,
    regiao: Regiao,
    camada: "Camada" = None,  # anotação tardia para evitar import circular
    *,
    debug: bool = False,
    source_path_override: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Lê results_transacoes_por_produto_enriquecido.json (lista de records).
    Tolerante a schemas: aceita lista direta ou containers "records"/"data"/...
    """
    from app.config.paths import Camada as _Camada  # import leve para evitar topo
    camada = camada or _Camada.PP

    src = _to_path(source_path_override) if source_path_override else _to_path(
        transacoes_enriquecidas_json(ano, mes, regiao, camada)
    )
    if debug:
        print(f"[DBG] fonte ENR: {src} (exists={src.exists()})")
    if not src.exists():
        if debug:
            print(f"[WARN] Arquivo enriquecido não encontrado: {src}")
        return []

    with src.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    # Reuso do detector do próprio módulo
    records = _find_records_container(obj)
    if debug:
        print(f"[DBG] enriquecidos encontrados: {len(records)}")
    # Garantir tipos básicos
    out: List[Dict[str, Any]] = []
    for r in records:
        q = _to_int(r.get("quantidade"))
        vu = _to_float(r.get("valor_unitario"))
        vt = _to_float(r.get("valor_transacao"))
        cu = _to_float(r.get("custo_unitario"))
        ct = _to_float(r.get("custo_total"))
        # Ajustes consistentes
        if vt is None and (vu is not None and q is not None):
            vt = vu * q
        if ct is None and (cu is not None and q is not None):
            ct = cu * q
        out.append({
            "numero_anuncio": r.get("numero_anuncio") or r.get("mlb") or r.get("item_id"),
            "gtin": r.get("gtin") or r.get("ean"),
            "quantidade": q,
            "valor_unitario": vu,
            "valor_transacao": vt,
            "custo_unitario": cu,
            "custo_total": ct,
        })
    return out


def read_resumo_transacoes_file(
    ano:int, mes:int, regiao:Regiao, camada:Camada=Camada.PP, *, debug:bool=False
) -> Dict[str, Any]:
    """
    Lê o arquivo já pré-processado:
      data/costs/variable/produtos/{ano}/{mes}/{regiao}/{camada}/resumo_transacoes.json
    """
    p = _to_path(resumo_transacoes_json(ano, mes, regiao, camada))
    if debug:
        print(f"[DBG] resumo_transacoes.json → {p} (exists={p.exists()})")
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def summarize_transacoes(records: List[Dict[str, Any]]) -> Dict[str, float]:
    qt = 0
    vt = 0.0
    ct = 0.0
    for r in records:
        q = _to_int(r.get("quantidade")) or 0
        v = _to_float(r.get("valor_transacao")) or 0.0
        c = _to_float(r.get("custo_total")) or 0.0
        qt += q
        vt += v
        ct += c
    return {
        "quantidade_total": int(qt),
        "valor_transacao_total": float(vt),
        "custo_total": float(ct),
    }

def aggregate_by_mlb_gtin(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Agrega por (mlb, gtin), somando quantidade/valor/custo e mantendo unitários como
    média ponderada pela quantidade.
    """
    from collections import defaultdict
    acc = defaultdict(lambda: {"q": 0, "vt": 0.0, "ct": 0.0, "sum_vu_q": 0.0, "sum_cu_q": 0.0})
    for r in records:
        mlb = r.get("numero_anuncio") or r.get("mlb") or r.get("item_id")
        gtin = r.get("gtin") or r.get("ean")
        key = (str(mlb) if mlb is not None else None, str(gtin) if gtin is not None else None)
        q = _to_int(r.get("quantidade")) or 0
        vu = _to_float(r.get("valor_unitario"))
        cu = _to_float(r.get("custo_unitario"))
        vt = _to_float(r.get("valor_transacao"))
        ct = _to_float(r.get("custo_total"))
        if vt is None and (vu is not None):
            vt = (vu * q) if q else None
        if ct is None and (cu is not None):
            ct = (cu * q) if q else None

        a = acc[key]
        a["q"] += q
        a["vt"] += vt or 0.0
        a["ct"] += ct or 0.0
        if vu is not None:
            a["sum_vu_q"] += (vu * q)
        if cu is not None:
            a["sum_cu_q"] += (cu * q)

    out: List[Dict[str, Any]] = []
    for (mlb, gtin), a in acc.items():
        q = a["q"]
        vu = (a["sum_vu_q"] / q) if q else None
        cu = (a["sum_cu_q"] / q) if q else None
        out.append({
            "mlb": mlb,
            "gtin": gtin,
            "quantidade": q,
            "valor_transacao": round(a["vt"], 2),
            "custo_total": round(a["ct"], 2),
            "valor_unitario": round(vu, 4) if vu is not None else None,
            "custo_unitario": round(cu, 4) if cu is not None else None,
        })
    return out


# ================== NOVO: deduplicação por número da venda ==================
def deduplicate_by_numero_venda(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mantém apenas UMA linha por numero_venda.
    - Se numero_venda for None, mantém a linha (não deduplica).
    - Para vendas repetidas, preserva a PRIMEIRA ocorrência.
    """
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in records:
        nv = r.get("numero_venda")
        if nv is None:
            out.append(r)  # sem número de venda: não deduplicamos
            continue
        if nv in seen:
            continue
        seen.add(nv)
        out.append(r)
    return out