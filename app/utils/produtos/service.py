# app/utils/produtos/service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.paths import Camada
from app.utils.produtos.config import produtos_json, cadastro_produtos_excel

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

from app.utils.produtos.aggregator import carregar_excel_normalizado


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
