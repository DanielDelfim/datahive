from __future__ import annotations

from typing import Iterable

# Categorias oficiais (tela "Sua fatura inclui")
# Acrescente "Outras tarifas" no começo da lista CATEGORIAS
CATEGORIAS = [
    "Tarifas de venda",
    "Aplicamos descontos sobre essas tarifas",
    "Tarifas de envios no Mercado Livre",
    "Tarifas por campanha de publicidade",
    "Taxas de parcelamento",
    "Tarifas de envios Full",
    "Tarifas dos serviços do Mercado Pago",
    "Tarifas da Minha página",
    "Outras tarifas",                      # <<< NOVA
    "Cancelamentos de tarifas",
]

# helpers no topo:
_SERV_MP_KEYS = (
    "serviços do mercado pago",
    "serviços do mercado pago",  # manter variações/acentos
    "serviço do mercado pago",
    "servicos mp",
    "serviços mp",
)

def _is_servicos_mp(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _SERV_MP_KEYS)


# helpers locais
def _has_assessoria(t: str) -> bool:
    t = (t or "").lower()
    return ("assessoria comercial" in t) or ("consultoria meli" in t) or ("assessoria" in t)


def categorias_fatura_ml() -> Iterable[str]:
    return list(CATEGORIAS)

def _contains(text: str, keys: Iterable[str]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keys)

def bucket_conceito_mp(conceito_raw: str) -> str:
    t = (conceito_raw or "").strip().lower()

    if "estorno" in t or "cancel" in t:
        return "Cancelamentos de tarifas"
    if "taxa de parcelamento" in t or "parcelament" in t:
        return "Taxas de parcelamento"
    if "publicidade" in t or "publicidad" in t or "ads" in t:
        return "Tarifas por campanha de publicidade"
    if "minha página" in t or "minha pagina" in t:
        return "Tarifas da Minha página"

    if _has_assessoria(t):
        return "Outras tarifas"            # <<< aqui

    if "custo de gest" in t or "gestao da venda" in t or "gestão da venda" in t:
        return "Tarifas de venda"
    if t == "tarifa de venda" or t.startswith("tarifa de venda"):
        return "Tarifas de venda"

    return "Tarifas de venda"
# ML
def bucket_conceito_ml(conceito_raw: str) -> str:
    t = (conceito_raw or "").strip().lower()

    if "estorno" in t or "cancel" in t:
        return "Cancelamentos de tarifas"

    if t.startswith("campanhas de publicidade") or "publicidade" in t \
       or "publicidad" in t or "product ads" in t or "brand ads" in t:
        return "Tarifas por campanha de publicidade"

    if "minha página" in t or "minha pagina" in t:
        return "Tarifas da Minha página"

    if "taxa de parcelamento" in t or "parcelament" in t:
        return "Taxas de parcelamento"

    if _has_assessoria(t):
        return "Outras tarifas"            # <<< aqui

    if t == "tarifa de venda" or t.startswith("tarifa de venda"):
        return "Tarifas de venda"
    if "custo de gest" in t or "gestao da venda" in t or "gestão da venda" in t:
        return "Tarifas de venda"

    if t.startswith("tarifa de envio") or "intermunicipal" in t or "etiqueta" in t:
        return "Tarifas de envios no Mercado Livre"

    if " full" in t or "armazenamento full" in t or "coleta full" in t:
        return "Tarifas de envios Full"

    return "Tarifas de envios no Mercado Livre"


def bucket_conceito_full(conceito_raw: str) -> str:
    if _contains(conceito_raw, ["armazen"]):
        return "Tarifas de envios Full"
    if _contains(conceito_raw, ["envio", "intermunicipal", "extra"]):
        return "Tarifas de envios Full"
    if _contains(conceito_raw, ["estorno", "cancel"]):
        return "Cancelamentos de tarifas"
    return "Tarifas de envios Full"

def bucket_conceito_pagamento_detalhe(conceito_raw: str) -> str:
    t = (conceito_raw or "").strip().lower()
    if "estorno" in t or "cancel" in t:
        return "Cancelamentos de tarifas"
    if _has_assessoria(t):
        return "Outras tarifas"
    if "publicidade" in t or "publicidad" in t or "product ads" in t or "brand ads" in t:
        return "Tarifas por campanha de publicidade"
    if "parcelament" in t:
        return "Taxas de parcelamento"
    # fallback conservador
    return "Tarifas de venda"
