from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union
from app.utils.precificacao.filters import is_item_full

from app.utils.precificacao.simulator import simular_mcp_item

from app.utils.precificacao.validators import anexar_warnings_mcp

from app.config.paths import (
    Marketplace,
    Regiao,
    Camada,
    atomic_write_json,
    Stage,
)

from app.utils.precificacao.config import (
    Periodo,
    get_precificacao_dataset_path,
    get_precificacao_metrics_path,
    get_anuncios_pp_path,
    get_produtos_pp_path,
    get_regras_meli_yaml_path,
)

from app.utils.precificacao.metrics import (
    calcular_metricas_item, agregar_metricas_documento,
)

# Services adjacentes
from app.utils.anuncios.service import listar_anuncios_pp, validar_integridade_pp
from app.utils.produtos.service import get_indices as get_indices_produtos

# ==== Result Sink (tolerante a layout) ====
JsonFileSink = StdoutSink = MultiSink = None  # type: ignore

# Tentativa 1: contrato centralizado em service.py
try:
    from app.utils.core.result_sink.service import JsonFileSink as _JFS, StdoutSink as _SS, MultiSink as _MS  # type: ignore
    JsonFileSink, StdoutSink, MultiSink = _JFS, _SS, _MS
except Exception:
    pass

# Tentativa 2: módulos separados
if JsonFileSink is None:
    try:
        from app.utils.core.result_sink.json_file_sink import JsonFileSink as _JFS  # type: ignore
        from app.utils.core.result_sink.stdout_sink import StdoutSink as _SS  # type: ignore
        from app.utils.core.result_sink.multi_sink import MultiSink as _MS  # type: ignore
        JsonFileSink, StdoutSink, MultiSink = _JFS, _SS, _MS
    except Exception:
        pass

# Fallback minimalista: usa atomic_write_json e um stdout simples
if JsonFileSink is None:
    class _FallbackJsonFileSink:
        def __init__(self, path: str, atomic: bool = True, rotate_keep: int = 0):
            self.path = path
            self.atomic = atomic
            self.rotate_keep = rotate_keep
        def emit(self, payload: dict, name: str = "") -> None:
            # atomic_write_json já é nossa primitiva segura
            atomic_write_json(self.path, payload)
    class _FallbackStdoutSink:
        def emit(self, payload: dict, name: str = "") -> None:
            print(f"[STDOUT:{name}]", json.dumps(payload, ensure_ascii=False)[:2000])
    class _FallbackMultiSink:
        def __init__(self, sinks):
            self.sinks = sinks
        def emit(self, payload: dict, name: str = "") -> None:
            for s in self.sinks:
                s.emit(payload, name=name)
    JsonFileSink, StdoutSink, MultiSink = _FallbackJsonFileSink, _FallbackStdoutSink, _FallbackMultiSink

SCHEMA_VERSION = "1.0.0"
SCRIPT_NAME = "precificacao.service"
SCRIPT_VERSION = "0.4.0"


# =========================
# Regras (exposto para metrics.py)
# =========================

def carregar_regras_ml() -> dict:
    """
    Lê o YAML de regras do Mercado Livre e devolve como dict.
    Mantido aqui pois metrics.py pode importar diretamente esse helper.
    """
    import yaml  # PyYAML
    yaml_path = get_regras_meli_yaml_path()
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# =========================
# Construção do documento
# =========================
def _num(x):
    """Converte para float quando possível; mantém None se vazio/inválido."""
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

def _coalesce_rebate(src: dict) -> tuple[float | None, float | None]:
    """
    Resolve campos de rebate vindos do PP de anúncios (variações de schema).
    Retorna: (rebate_price_discounted, rebate_price_list)
    """
    # Preço com rebate aplicado (o que vai para "discounted")
    r_discounted = (
        src.get("rebate_price_discounted")
        or src.get("rebate_price_all_methods")  # << campo do seu PP canônico
        or src.get("deal_price")
        or src.get("sale_price")
    )
    # Preço "de lista"/original (opcional, útil para auditoria e telas)
    r_list = (
        src.get("rebate_price_list")
        or src.get("original_price")
        or src.get("base_price")
    )
    return _num(r_discounted), _num(r_list)


def construir_dataset_base(periodo_or_regiao, regiao: Union[Regiao, str, None] = None) -> Dict[str, Any]:
    """
    Backward-compatible:
      - construir_dataset_base(Periodo(...), regiao)
      - construir_dataset_base(regiao)  # período inferido do mês/ano atuais (apenas para _meta)
    """
    from datetime import datetime

    if regiao is None:
        regiao = periodo_or_regiao
        now = datetime.utcnow()
        periodo = Periodo(now.year, now.month)
    else:
        periodo = periodo_or_regiao

    r = regiao.value if isinstance(regiao, Regiao) else str(regiao).lower()

    # 1) integridade do PP
    validar_integridade_pp(r)

    # 2) listar anúncios (PP)
    try:
        regiao_enum = regiao if isinstance(regiao, Regiao) else Regiao(r)
    except Exception:
        regiao_enum = Regiao.SP if r == "sp" else Regiao.MG
    anuncios = listar_anuncios_pp(regiao_enum)

    def _coletar_list(a):
        if a is None:
            return []
        if isinstance(a, list):
            return a
        if isinstance(a, dict):
            for k in ("data", "items", "results", "anuncios"):
                if k in a and isinstance(a[k], list):
                    return a[k]
            return []
        if isinstance(a, str):
            try:
                import json
                with open(a, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                return _coletar_list(obj)
            except Exception:
                return []
        return []

    anuncios_list = _coletar_list(anuncios)
    if not anuncios_list:
        import json as _json
        try:
            with open(get_anuncios_pp_path(regiao), "r", encoding="utf-8") as f:
                obj = _json.load(f)
            anuncios_list = _coletar_list(obj)
        except Exception:
            anuncios_list = []

    # 3) montar itens normalizados (com rebate coalescido)
    itens: List[Dict[str, Any]] = []
    for a in anuncios_list:
        rebate_disc, rebate_list = _coalesce_rebate(a)

        item = {
            "mlb": a.get("id") or a.get("mlb"),
            "sku": a.get("seller_sku") or a.get("sku"),
            "gtin": a.get("gtin") or a.get("ean"),
            "title": a.get("title"),
            "price": _num(a.get("price")),
            "original_price": _num(a.get("original_price")),  # opcional (auditoria)
            "rebate_price_discounted": rebate_disc,           # << agora preenche a partir de rebate_price_all_methods
            "rebate_price_list": rebate_list,
            "logistic_type": a.get("logistic_type"),
            "is_full": bool((a.get("logistic_type") or "").lower() in {"fulfillment", "fulfillment_co"}),
            "status": (a.get("status") or "").lower(), 
            "regiao": r,
        }

        # Fora do Full: não sugerimos faixa/custo fixo
        if not is_item_full(item):
            item["custo_fixo_full"] = None
            item["preco_min"] = None
            item["preco_max"] = None

        itens.append(item)

    itens.sort(key=lambda x: (str(x.get("mlb") or ""), str(x.get("sku") or "")))

    return {
        "periodo": {"ano": periodo.ano, "mes": periodo.mes},
        "regiao": r,
        "marketplace": Marketplace.MELI.value,
        "camada": Camada.PP.value,
        "stage": Stage.DEV.value,  # ajuste conforme seu ambiente ativo
        "itens": itens,
    }

def enriquecer_preco_compra(documento: Dict[str, Any]) -> Dict[str, Any]:
    indices = get_indices_produtos()
    if not isinstance(indices, dict) or (not indices.get('por_gtin') and not indices.get('por_sku')):
        indices = _build_produtos_indices_fallback()

    it_out: List[Dict[str, Any]] = []
    for it in documento["itens"]:
        gtin = (it.get("gtin") or "").strip() if it.get("gtin") else None
        sku = (it.get("sku") or "").strip() if it.get("sku") else None

        preco_compra = None
        if gtin and gtin in indices.get("por_gtin", {}):
            preco_compra = indices["por_gtin"][gtin].get("preco_compra")
        elif sku and sku in indices.get("por_sku", {}):
            preco_compra = indices["por_sku"][sku].get("preco_compra")

        it2 = dict(it)
        it2["preco_compra"] = preco_compra
        it_out.append(it2)

    documento2 = dict(documento)
    documento2["itens"] = it_out
    return documento2

# --- aplica overrides.yaml aos itens do documento ---
def aplicar_overrides_no_documento(documento: Dict[str, Any], cenario: str | None = None) -> Dict[str, Any]:
    from app.utils.precificacao.overrides import resolver_override
    it_out: List[Dict[str, Any]] = []
    for it in (documento.get("itens") or []):
        ov = resolver_override(
            mlb=(it.get("mlb") or None),
            sku=(it.get("sku") or None),
            gtin=(it.get("gtin") or None),
            cenario=cenario,
        )
        it2 = dict(it)
        if ov and ov.knobs:
            # derruba apenas chaves *_override; não mexe no resto
            it2.update(ov.knobs)
            # opcional: rastro de auditoria
            it2.setdefault("_override_info", {"origem": ov.origem, "campanha_id": ov.campanha_id})
        it_out.append(it2)
    doc2 = dict(documento)
    doc2["itens"] = it_out
    return doc2

def aplicar_metricas_no_documento(
    documento: Dict[str, Any], *,
    regras: dict | None = None,
    only_full: bool = False,
    use_rebate_as_price: bool = True,
    canal: str = "meli",
) -> Dict[str, Any]:
    itens_in = documento.get("itens", []) or []

    itens_out = []
    for it in itens_in:
        if only_full and not is_item_full(it):
            itens_out.append(dict(it))
            continue

        calc = calcular_metricas_item(it, regras=regras, use_rebate_as_price=use_rebate_as_price)
        merged = dict(it)
        merged.update(calc)
        itens_out.append(merged) 

    doc2 = dict(documento)
    doc2["itens"] = itens_out
    doc2["metrics"] = agregar_metricas_documento(itens_out)
    return doc2

def _build_produtos_indices_fallback() -> dict:
    """
    Lê o produtos.json diretamente e monta índices por_gtin / por_sku.
    Aceita tanto {"items": {...}} (dict por GTIN) quanto {"items": [...]}.
    """
    path = get_produtos_pp_path()
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    por_gtin, por_sku = {}, {}

    items = obj.get("items")
    if isinstance(items, dict):
        iterable = items.values()
    elif isinstance(items, list):
        iterable = items
    else:
        iterable = []

    for p in iterable:
        gtin = (p.get("gtin") or p.get("sku") or "").strip()
        sku = (p.get("sku") or "").strip()
        if gtin:
            por_gtin[gtin] = p
        if sku:
            por_sku[sku] = p

    return {"por_gtin": por_gtin, "por_sku": por_sku}

# =========================
# DQ checks
# =========================

def _fail(msg: str, *, samples: List[Dict[str, Any]] | None = None) -> None:
    if samples:
        StdoutSink().emit({"message": msg, "samples": samples}, name="DQ_FAIL_SAMPLES")
    raise ValueError(msg)


def _dq_checks(documento: Dict[str, Any], *, allow_empty: bool = False, source_path: str | None = None) -> None:
    import math as _math

    itens = documento.get("itens") or []
    if len(itens) == 0:
        if allow_empty:
            StdoutSink().emit({"warning": "DQ: row_count=0 (liberado por allow_empty)", "source": source_path or ""}, name="DQ_WARN")
            return
        _fail(f"DQ: row_count=0. Verifique a fonte: {source_path or ''}")

    # unicidade de mlb (quando presente)
    mlbs = [x.get("mlb") for x in itens if x.get("mlb")]
    if len(mlbs) != len(set(mlbs)):
        _fail("DQ: chaves MLB duplicadas detectadas.", samples=[{"mlb": m} for m in mlbs])

    # coerência de FULL
    for it in itens:
        if it.get("is_full") and not (it.get("gtin") or it.get("sku")):
            _fail("DQ: item FULL sem gtin/sku.", samples=[it])

    # tipos numéricos esperados
    def _is_num(v) -> bool:
        try:
            return (v is not None) and (not isinstance(v, bool)) and _math.isfinite(float(v))
        except Exception:
            return False

    for it in itens:
        price_fields = ["price", "rebate_price_list", "rebate_price_discounted"]
        if not any(_is_num(it.get(f)) for f in price_fields):
            _fail("DQ: item sem nenhum preço válido (price ou rebate_*).", samples=[it])

        if it.get("preco_compra") is not None and not _is_num(it.get("preco_compra")):
            _fail("DQ: preco_compra inválido.", samples=[it])


# =========================
# Persistência via Result Sink
# =========================

def _hash_payload_ordered(items: List[Dict[str, Any]]) -> str:
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib as _hashlib
    return "sha256:" + _hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_meta(documento: Dict[str, Any], *, source_paths: List[str]) -> Dict[str, Any]:
    row_count = len(documento.get("itens") or [])
    h = _hash_payload_ordered(documento["itens"])
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage": Stage.DEV.value,
        "marketplace": Marketplace.MELI.value,
        "regiao": documento.get("regiao"),
        "camada": Camada.PP.value,
        "schema_version": SCHEMA_VERSION,
        "script_name": SCRIPT_NAME,
        "script_version": SCRIPT_VERSION,
        "source_paths": source_paths,
        "row_count": row_count,
        "hash": h,
    }


def salvar_documentos(
    documento: Dict[str, Any],
    regiao: Union[Regiao, str],
    *, keep: int = 7, debug: bool = False
) -> Tuple[str, str]:
    """
    Grava artefatos (principal + metrics) via ResultSink, com rotação keep=N.
    Retorna (path_json, path_metrics).
    """
    anuncios_path = str(get_anuncios_pp_path(regiao))
    import os as _os
    allow_empty = debug or (_os.getenv('DATAHIVE_ALLOW_EMPTY', '0') == '1')
    _dq_checks(documento, allow_empty=allow_empty, source_path=anuncios_path)


    source_paths = [
        str(get_anuncios_pp_path(regiao)),
        str(get_produtos_pp_path()),
    ]

    documento2 = dict(documento)
    documento2["_meta"] = _build_meta(documento, source_paths=source_paths)

    out_json = str(get_precificacao_dataset_path(regiao))
    out_metrics = str(get_precificacao_metrics_path(regiao))

    sinks = [JsonFileSink(out_json, atomic=True, rotate_keep=keep)]
    if debug:
        sinks.append(StdoutSink())
    sink = MultiSink(sinks)

    sink.emit(documento2, name="precificacao_dataset")

    metrics_only = {
        "periodo": documento.get("periodo"),
        "regiao": documento.get("regiao"),
        "marketplace": documento.get("marketplace"),
        "camada": documento.get("camada"),
        "_meta": {k: documento2["_meta"][k] for k in documento2["_meta"] if k not in {"row_count", "hash"}},
        "metrics": documento.get("metrics"),
    }
    JsonFileSink(out_metrics, atomic=True, rotate_keep=keep).emit(metrics_only, name="precificacao_metrics")

    return out_json, out_metrics


# ===== Backward compatibility (scripts antigos) =====

def salvar_dataset(documento: Dict[str, Any], regiao: Union[Regiao, str], *, keep: int = 7, debug: bool = False) -> str:
    """
    Compat: scripts antigos chamam salvar_dataset().
    Aqui gravamos apenas o dataset principal (sem o artefato de métricas).
    """
    anuncios_path = str(get_anuncios_pp_path(regiao))
    import os as _os
    allow_empty = debug or (_os.getenv('DATAHIVE_ALLOW_EMPTY', '0') == '1')
    _dq_checks(documento, allow_empty=allow_empty, source_path=anuncios_path)


    source_paths = [
        str(get_anuncios_pp_path(regiao)),
        str(get_produtos_pp_path()),
    ]
    documento2 = dict(documento)
    documento2["_meta"] = _build_meta(documento, source_paths=source_paths)

    out_json = str(get_precificacao_dataset_path(regiao))

    sinks = [JsonFileSink(out_json, atomic=True, rotate_keep=keep)]
    if debug:
        sinks.append(StdoutSink())
    MultiSink(sinks).emit(documento2, name="precificacao_dataset")

    return out_json

# =========================
# Orquestração do módulo
# =========================
def executar(periodo: Periodo, regiao: Union[Regiao, str], *, use_rebate_as_price: bool = True, keep: int = 7, debug: bool = False) -> Tuple[str, str]:
    """
    1) carrega anúncios (PP) → documento base
    2) enriquece com preço de compra (produtos PP)
    3) calcula métricas item-a-item e agregadas
    4) executa validações e grava artefatos por região
    """
    base = construir_dataset_base(periodo, regiao)
    com_custo = enriquecer_preco_compra(base)
    # >>> NOVO: aplica overrides por MLB/SKU/GTIN/cenário
    com_overrides = aplicar_overrides_no_documento(com_custo, cenario=None)
    # calcula métricas já considerando overrides
    com_metricas = aplicar_metricas_no_documento(com_overrides, use_rebate_as_price=use_rebate_as_price)
    # validação
    validado = anexar_warnings_mcp(com_metricas)


    return salvar_documentos(validado, regiao, keep=keep, debug=debug)

def simular_mcp(mlb: str, regiao: Union[Regiao, str], preco_venda: float, subsidio_valor: float = 0.0) -> Dict[str, Any]:
    """Carrega o item do dataset da região e retorna simulação de MCP para (preço, subsídio)."""
    ds_path = get_precificacao_dataset_path(regiao)
    with open(ds_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    itens = doc.get("itens") or []
    alvo = next((it for it in itens if str(it.get("mlb")) == str(mlb)), None)
    if not alvo:
        return {"error": f"MLB {mlb} não encontrado no dataset de {regiao}."}
    return simular_mcp_item(alvo, preco_venda=float(preco_venda), subsidio_valor=float(subsidio_valor))