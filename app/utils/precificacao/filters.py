# C:\Apps\Datahive\app\utils\precificacao\filters.py

from .metrics import preco_efetivo

def aplicar_preco_efetivo(item: dict, considerar_rebate: bool) -> dict:
    item["preco_venda_efetivo"] = preco_efetivo(
        item.get("price"),
        item.get("rebate_price_discounted"),
        considerar_rebate
    )
    return item

def is_item_full(item: dict) -> bool:
    # Full quando logistic_type = 'fulfillment' ou flag booleana
    lt = (item.get("logistic_type") or "").lower()
    if lt == "fulfillment":
        return True
    return bool(item.get("is_full"))

