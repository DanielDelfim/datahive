# app/utils/produtos/service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.paths import Camada
from app.utils.produtos.config import produtos_json, cadastro_produtos_excel
from app.utils.produtos.mappers.dimensions import normalize_peso_dimensoes

# Import resiliente do módulo de mapeamento:
# 1) nome atual "mappers"
# 2) nome legado "mapeadores"
# 3) fallback relativo quando executado como pacote
try:
    from app.utils.produtos import mappers as mapeadores  # nome local padronizado
except ImportError:
    try:
        from app.utils.produtos import mapeadores  # legado
    except ImportError:
        try:
            from . import mappers as mapeadores  # relativo
        except ImportError:
            from . import mapeadores  # relativo (legado)

from app.utils.produtos.aggregator import carregar_excel_normalizado, carregar_excel_normalizado_detalhado

def normalizar_excel_detalhado() -> tuple[dict, list[dict]]:
    """Fachada pública p/ geração do PP a partir do Excel (sem escrita)."""
    from app.utils.produtos.config import cadastro_produtos_excel
    return carregar_excel_normalizado_detalhado(cadastro_produtos_excel())

def carregar_pp(camada: Camada = Camada.PP) -> Dict[str, Any]:
    """
    Lê o produtos_pp.json e retorna o payload completo:
    { "count": int, "source": str, "items": { sku: {...}, ... } }
    """
    path = produtos_json(camada)
    if not Path(path).exists():
        return {"count": 0, "source": None, "items": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # sanity
    data.setdefault("items", {})
    data.setdefault("count", len(data["items"]))
    return data


def listar_skus(camada: Camada = Camada.PP) -> list[str]:
    data = carregar_pp(camada)
    return sorted(list(data["items"].keys()))


def get_por_sku(sku: str, camada: Camada = Camada.PP) -> Optional[Dict[str, Any]]:
    data = carregar_pp(camada)
    return data["items"].get(sku)


def get_itens(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    return carregar_pp(camada)["items"]


def get_indices(camada: Camada = Camada.PP) -> Dict[str, Dict[str, Any]]:
    """
    Devolve índices auxiliares (mapeamentos) prontos para uso.
    """
    items = get_itens(camada)
    return {
        "sku_to_gtin": mapeadores.sku_to_gtin(items),
        "gtin_to_skus": mapeadores.gtin_to_skus(items),
        "sku_to_dun14": mapeadores.sku_to_dun14(items),
    }

def preview_normalizacao_excel() -> Dict[str, Dict[str, Any]]:
    """
    Carrega o Excel do módulo a partir do caminho padrão e devolve
    a normalização em memória (NÃO escreve arquivo).
    Útil para dry-run/validação.
    """
    excel = cadastro_produtos_excel()
    return carregar_excel_normalizado(excel)

def listar_produtos() -> dict[str, dict]: return get_itens()
def obter_custos_por_gtin(gtin: str) -> float | None:
    for rec in get_itens().values():
        if rec.get("gtin") == gtin:
            return rec.get("preco_compra")
    return None

def listar_produtos_normalizado() -> Dict[str, Dict[str, Any]]:
    """
    Fachada pública: retorna dict[sku]->registro com
    peso/altura/largura/profundidade já preenchidos (kg/cm) quando possíveis.
    Não grava; apenas enriquece os registros carregados do PP.
    """
    base = listar_produtos()  # já existente no seu service
    out: Dict[str, Dict[str, Any]] = {}
    for sku, rec in base.items():
        rec2 = dict(rec)  # cópia superficial
        dims = normalize_peso_dimensoes(rec2)
        # só preenche se estiver faltando ou None:
        for k, v in dims.items():
            if rec2.get(k) in (None, "", [], {}):
                rec2[k] = v
        out[sku] = rec2
    return out

# --- Helpers por GTIN (enriquecimento para reposição) ---

def get_por_gtin(gtin: str, camada: Camada = Camada.PP) -> Optional[Dict[str, Any]]:
    """
    Retorna o registro completo do produto com esse GTIN (quando houver).
    """
    for rec in get_itens(camada).values():
        if rec.get("gtin") == gtin:
            return rec
    return None

def get_pack_info_por_gtin(gtin: str, camada: Camada = Camada.PP) -> Dict[str, Any]:
    """
    Extrai os campos relevantes para planejamento de compra/reposição.
    Campos: preco_compra, multiplo_compra, caixa_cm, pesos_caixa_g, pesos_g, dimensoes_cm.
    Retorna dicionário só com os campos encontrados (pode vir vazio).
    """
    rec = get_por_gtin(gtin, camada)
    if not rec:
        return {}
    keys = [
        "preco_compra",
        "multiplo_compra",
        "caixa_cm",
        "pesos_caixa_g",
        "pesos_g",
        "dimensoes_cm",
    ]
    out = {}
    for k in keys:
        v = rec.get(k)
        if v not in (None, "", []):
            out[k] = v
    return out
