# C:\Apps\Datahive\app\utils\costs\variable\produtos\aggregator.py
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

def _get_first(d: Dict[str, Any], keys: Iterable[str], default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def _to_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str):
            x = x.replace(".", "").replace(",", ".") if "," in x and x.count(",") == 1 else x
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

def map_faturamento_to_transacoes(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mapeia registros do faturamento (PP) para estrutura de transações por produto/venda.

    Entrada esperada (robusto a variações de chaves):
      - numero_venda
      - numero_anuncio | mlb | item_id
      - quantidade | qtd
      - valor_unitario | preco_unitario
      - valor_transacao | total  (se ausente, calcula = valor_unitario * quantidade)

    Saída:
      { numero_venda, numero_anuncio, quantidade, valor_unitario, valor_transacao }
    """
    out: List[Dict[str, Any]] = []
    for r in records:
        numero_venda = _get_first(r, ["numero_venda", "order_id", "id_venda"])
        if not numero_venda:
            # ignora linhas sem vinculação de venda
            continue

        numero_anuncio = _get_first(r, ["numero_anuncio", "mlb", "item_id", "anuncio_id", "listing_id"])
        quantidade = _to_int(_get_first(r, ["quantidade", "quantidade_vendida", "quantity"]))
        valor_unitario = _to_float(_get_first(r, ["valor_unitario", "preco_unitario", "unit_price"]))
        valor_transacao = _to_float(_get_first(r, ["valor_transacao", "total", "valor_total"]))

        if valor_transacao is None and (valor_unitario is not None and quantidade is not None):
            valor_transacao = valor_unitario * quantidade

        out.append({
            "numero_venda": str(numero_venda),
            "numero_anuncio": str(numero_anuncio) if numero_anuncio is not None else None,
            "quantidade": quantidade,
            "valor_unitario": valor_unitario,
            "valor_transacao": valor_transacao,
        })
    return out
