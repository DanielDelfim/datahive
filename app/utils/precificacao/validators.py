# -*- coding: utf-8 -*-
"""
Validações do módulo de precificação.

- Garante que cada item (MLB) tem insumos suficientes para cálculo de MCP.
- Verifica presença/consistência de preços mínimo/máximo quando aplicável.
- Pode ser usado pelo script de agregação para anotar avisos no próprio dataset.

API principal:
- validar_item_mcp(item) -> list[str]
- validar_item_ranges(item) -> list[str]
- validar_documento(doc) -> list[{"mlb": ..., "warnings": [...]}]
- anotar_warnings_no_documento(doc) -> dict
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import math

from app.utils.precificacao.filters import is_item_full
from app.utils.precificacao.metrics import preco_efetivo


def _is_none(x: Any) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _get_preco_venda_efetivo(item: Dict[str, Any]) -> Optional[float]:
    # usa campo já calculado ou deriva de (price, rebate_price_discounted)
    pv = item.get("preco_efetivo")
    if _is_none(pv) or (isinstance(pv, (int, float)) and float(pv) <= 0):
        pv = preco_efetivo(item.get("price"), item.get("rebate_price_discounted"), considerar_rebate=True)
    try:
        return float(pv) if pv is not None else None
    except Exception:
        return None


def validar_item_mcp(item: Dict[str, Any]) -> List[str]:
    """Valida insumos mínimos para cálculo de MCP. Retorna lista de avisos (strings)."""
    warns: List[str] = []

    # preço de venda efetivo (com rebate)
    if _get_preco_venda_efetivo(item) is None:
        warns.append("preco_venda_efetivo_ausente")

    # preço de compra (custo do produto)
    if _is_none(item.get("preco_compra")):
        warns.append("preco_compra_ausente")

    # impostos/marketing/comissão — aceitamos pct OU valor absoluto (R$)
    if _is_none(item.get("imposto")) and _is_none(item.get("imposto_pct")):
        warns.append("imposto_ausente")
    if _is_none(item.get("marketing")) and _is_none(item.get("marketing_pct")):
        warns.append("marketing_ausente")
    if _is_none(item.get("comissao")) and _is_none(item.get("comissao_pct")):
        warns.append("comissao_ausente")

    # frete/custo fixo — relevantes para FULL
    if is_item_full(item):
        if _is_none(item.get("custo_fixo_full")):
            warns.append("custo_fixo_full_ausente")
        if _is_none(item.get("frete_sobre_custo")) and _is_none(item.get("frete_full")):
            warns.append("frete_ausente")

    return warns


def validar_item_ranges(item: Dict[str, Any]) -> List[str]:
    """Valida presença/consistência de preço mínimo/máximo quando aplicável (FULL)."""
    warns: List[str] = []
    if not is_item_full(item):
        return warns  # não exigimos faixa fora do FULL

    pmin = item.get("preco_min")
    if _is_none(pmin):
        pmin = item.get("preco_minimo")
    pmax = item.get("preco_max")
    if _is_none(pmax):
        pmax = item.get("preco_maximo")

    if _is_none(pmin):
        warns.append("preco_min_ausente")
    if _is_none(pmax):
        warns.append("preco_max_ausente")

    try:
        if (pmin is not None) and (pmax is not None) and float(pmin) > float(pmax):
            warns.append("faixa_preco_inconsistente")
    except Exception:
        warns.append("faixa_preco_invalida")

    return warns


def validar_documento(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lista avisos por MLB para um documento completo (dataset_precificacao.json)."""
    out: List[Dict[str, Any]] = []
    for it in (doc.get("itens") or []):
        w = sorted(set(validar_item_mcp(it) + validar_item_ranges(it)))
        if w:
            out.append({"mlb": it.get("mlb"), "warnings": w})
    return out


def anotar_warnings_no_documento(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Clona o documento e injeta 'warnings': [...] em cada item quando aplicável."""
    it_out: List[Dict[str, Any]] = []
    for it in (doc.get("itens") or []):
        w = sorted(set(validar_item_mcp(it) + validar_item_ranges(it)))
        it2 = dict(it)
        if w:
            it2["warnings"] = w
        else:
            it2.pop("warnings", None)
        it_out.append(it2)
    doc2 = dict(doc)
    doc2["itens"] = it_out
    return doc2

# --- Aliases de compatibilidade (mantêm chamadas antigas vivas) ---
def validar_insumos_mcp(item: dict) -> list[str]:
    # nome legado → usa a função atual por item
    return validar_item_mcp(item)

def anexar_warnings_mcp(documento: dict) -> dict:
    # nome legado → usa o anotador atual por documento
    return anotar_warnings_no_documento(documento)
