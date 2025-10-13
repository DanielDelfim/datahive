# app/utils/anuncios/service.py
from __future__ import annotations
from typing import List, Dict, Any, Optional

from .aggregator import _carregar_pp
import app.utils.anuncios.aggregator as ag
from .schemas import PPAnuncio, has_minimal_fields
from . import filters  # by_* / apply_filters
from app.utils.core.identifiers import normalize_gtin
from app.config.paths import Regiao, Camada
from app.utils.core.io import ler_json
from . import config as ancfg  # paths do domínio (anuncios)
from pathlib import Path
from app.config.paths import Marketplace

# ------------------- helpers internos -------------------

def _coerce_items(env: Any) -> List[Dict[str, Any]]:
    """
    Aceita formatos comuns:
    - dict com 'data' | 'items' | 'itens' | 'results' (lista ou dict-mapa)
    - lista já "flat"
    """
    if isinstance(env, dict):
        for key in ("data", "items", "itens", "results"):
            val = env.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                # aceita mapeamentos id->obj
                return [v for v in val.values() if isinstance(v, dict)]
        return []
    if isinstance(env, list):
        return [it for it in env if isinstance(it, dict)]
    return []

def _pp_path_for(regiao: Regiao) -> Optional["Path"]:
    """
    Resolve o caminho PP pelo config do domínio.
    Tenta ancfg.PP_PATH(regiao) e, se não existir, ancfg.anuncios_json(market, camada, regiao).
    """
    # Evita import opcional de Path no topo se não for necessário
    try:
        # Preferência: função explícita PP_PATH("sp"/"mg")
        if hasattr(ancfg, "PP_PATH"):
            return ancfg.PP_PATH(regiao.value.lower())
    except Exception:
        pass
    try:
        # Alternativa: helper transversal do domínio de anúncios
        if hasattr(ancfg, "anuncios_json"):
            return ancfg.anuncios_json(market=Marketplace.MELI, camada=Camada.PP, regiao=regiao)
    except Exception:
        pass
    return None

# ------------------- API de serviço (somente leitura) -------------------

def listar_anuncios_pp(regiao: Optional[Regiao] = None) -> List[Dict[str, Any]]:
    """
    Lê o(s) JSON(s) PP de anúncios (por região) e retorna lista de dicts prontos para o dashboard.
    Se regiao=None, agrega SP + MG e etiqueta o campo 'regiao' quando ausente.
    """
    regioes: List[Regiao] = [regiao] if regiao else [Regiao.SP, Regiao.MG]
    registros: List[Dict[str, Any]] = []

    for r in regioes:
        p = _pp_path_for(r)
        if not p:
            # Sem path resolvido para esta região; segue para a próxima
            continue
        try:
            env = ler_json(p)
        except FileNotFoundError:
            # PP ainda não gerado para esta região
            continue

        for it in _coerce_items(env):
            if "regiao" not in it:
                it = {**it, "regiao": r.value}
            registros.append(it)

    return registros

def listar_anuncios(
    regiao: str,
    mlbs: Optional[List[str]] = None,
    title_q: Optional[str] = None,
    sku_q: Optional[str] = None,
    fulfillment_only: bool = False,
    active_only: bool = False,
) -> List[PPAnuncio]:
    """
    Retorna a lista PP carregada por _carregar_pp(regiao) filtrada conforme critérios.
    """
    data = _carregar_pp(regiao)
    if not any([mlbs, title_q, sku_q, fulfillment_only, active_only]):
        return data
    return filters.apply_filters(
        data,
        mlbs=mlbs,
        title_q=title_q,
        sku_q=sku_q,
        fulfillment_only=fulfillment_only,
        active_only=active_only,
    )

def obter_anuncio_por_mlb_pp(regiao: str, mlb: str) -> Optional[PPAnuncio]:
    """
    Retorna um único anúncio PP por MLB (ou None se não encontrado).
    """
    if not mlb:
        return None
    q = mlb.strip().casefold()
    for rec in _carregar_pp(regiao):
        rid = str(rec.get("mlb") or "").strip().casefold()
        if rid == q:
            return rec
    return None

def campos_basicos(rec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai campos mínimos para exibição rápida.
    """
    return {
        "mlb": rec.get("mlb"),
        "sku": rec.get("sku"),
        "gtin": rec.get("gtin") or rec.get("ean") or rec.get("barcode"),
        "title": rec.get("title"),
        "estoque": rec.get("estoque"),
        "price": rec.get("price"),
        "rebate_price": rec.get("rebate_price"),
        "original_price": rec.get("original_price"),
        "status": rec.get("status"),
        "logistic_type": rec.get("logistic_type"),
    }

def validar_integridade_pp(regiao: str) -> Dict[str, Any]:
    """
    Valida estrutura básica do PP da região.
    Retorna {'ok': bool, 'total': int, 'erros': [...] }.
    """
    erros: List[str] = []
    data = _carregar_pp(regiao)
    if not isinstance(data, list):
        return {"ok": False, "total": 0, "erros": ["Envelope PP inválido ou ausente."]}

    total = len(data)
    for i, rec in enumerate(data):
        if not has_minimal_fields(rec):
            erros.append(f"Registro #{i} sem campos mínimos (mlb/title).")
        # Aqui você pode adicionar validações extras conforme necessário.

    return {"ok": len(erros) == 0, "total": total, "erros": erros}

# ------------------- normalização de GTINs + busca unitária -------------------

def _normalize_gtins_inplace(anuncio: dict) -> None:
    # topo
    for k in ("gtin", "ean", "barcode", "gtin13", "ean_code", "gtin_13"):
        if k in anuncio and anuncio[k]:
            anuncio[k] = normalize_gtin(str(anuncio[k]))
    # attributes no topo
    for a in anuncio.get("attributes", []) or []:
        key = (a.get("id") or a.get("name") or "").strip().lower()
        if key in {"gtin", "ean", "barcode", "código de barras", "codigo de barras"}:
            v = a.get("value_name") or a.get("value") or a.get("value_id")
            if v:
                a["value_name"] = normalize_gtin(str(v))
    # variations[*].attributes
    for var in anuncio.get("variations", []) or []:
        for a in var.get("attributes", []) or []:
            key = (a.get("id") or a.get("name") or "").strip().lower()
            if key in {"gtin", "ean", "barcode", "código de barras", "codigo de barras"}:
                v = a.get("value_name") or a.get("value") or a.get("value_id")
                if v:
                    a["value_name"] = normalize_gtin(str(v))

def _chamada_api_ou_cache(regiao: str, mlb: str) -> Optional[dict]:
    """
    Placeholder: troque por implementação real quando necessário.
    Por ora, reutiliza o PP.
    """
    return obter_anuncio_por_mlb_pp(regiao, mlb)

def obter_anuncio_por_mlb(regiao: str, mlb: str) -> Optional[dict]:
    anuncio = _chamada_api_ou_cache(regiao, mlb)
    if anuncio:
        _normalize_gtins_inplace(anuncio)
    return anuncio

def _resolve_regioes(regiao: Regiao | str | None) -> list[Regiao]:
    # Se não vier nada (ou vier "none"), tenta em TODAS as regiões do enum
    if regiao is None or str(regiao).strip().lower() in {"none", ""}:
        return list(Regiao)

    # Já é enum?
    if isinstance(regiao, Regiao):
        return [regiao]

    # Tenta casar por value ("sp","mg",...) ou por name ("SP","MG",...)
    s = str(regiao).strip().lower()
    for r in Regiao:
        if r.value == s or r.name.lower() == s:
            return [r]

    # Último recurso: tentar construir pelo value/name; se falhar, considera todas
    try:
        return [Regiao(s)]
    except Exception:
        return list(Regiao)

def obter_raw_por_mlb(mlb: str, regiao: Regiao | str | None) -> Optional[Dict[str, Any]]:
    """
    Retorna o registro RAW (cru) do anúncio para o MLB. Se regiao vier None/“none”,
    procura em todas as regiões do Enum Regiao.
    """
    if not mlb:
        return None

    for r in _resolve_regioes(regiao):
        items = ag.carregar_raw(r)  # lista de dicts (pode ser vazia)
        for it in items:
            try:
                if str(it.get("id")) == str(mlb):
                    return it
            except Exception:
                continue
    return None