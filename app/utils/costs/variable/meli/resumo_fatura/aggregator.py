from __future__ import annotations
from typing import Dict, List, Tuple
from .mapper import norm_str
from ..config import REQUIRED_BUCKETS, BUCKET_MAP
import re

import unicodedata

def _norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = " ".join(s.strip().split())
    return s.lower()
# mapa normalizado para lookup robusto
BUCKET_MAP_NORM = { _norm(k): v for k, v in BUCKET_MAP.items() }

def _sum_val(rows: List[dict], col: str) -> float:
    """Soma robusta: entende '1.234,56', 'sim/nao', 'true/false' etc."""
    total = 0.0
    for r in rows:
        total += _to_float_local(r.get(col))
    return round(total, 2)

def _sum_diff(rows: List[dict], col_a: str, col_b: str) -> float:
    """
    Soma (col_a - col_b), tratando None/strings como 0.0 quando necessário.
    Usada para 'Tarifa de envio extra ou intermunicipal' = valor_tarifa - envio_por_conta_do_cliente.
    """
    total = 0.0
    for r in rows:
        a = _to_float_local(r.get(col_a))
        b = _to_float_local(r.get(col_b))
        total += a - b
    return round(total, 2)

def _to_float_local(x) -> float:
    """Converte valores em BR/US (c/ ou s/ moeda) e booleanos textuais para float, sem explodir decimais."""

    # se já for número, não mexe
    if isinstance(x, (int, float)):
        return float(x)
    s_raw = str(x).strip()
    s_low = s_raw.lower()
    if s_low in {"true","t","sim","yes","y"}:
        return 1.0
    if s_low in {"false","f","nao","não","no","n"}:
        return 0.0
    # remove moeda e quaisquer caracteres não numéricos (mantém -, . , ,)
    s = re.sub(r"[^0-9,\.\-]", "", s_raw)
    if s == "":
        return 0.0
    # detectar separador decimal: último ponto ou vírgula presente
    last_dot   = s.rfind(".")
    last_comma = s.rfind(",")
    if last_dot != -1 and last_comma != -1:
        # se o último separador é ponto, ponto é decimal (milhar = vírgula)
        if last_dot > last_comma:
            s = s.replace(",", "")           # remove milhar ','
        else:
            s = s.replace(".", "").replace(",", ".")  # decimal é vírgula
    elif last_comma != -1:
        s = s.replace(",", ".")              # só vírgula -> decimal
    else:
        # só ponto ou nenhum -> mantém
        pass
    try:
        return float(s)
    except Exception:
        return 0.0

def compose_sua_fatura_inclui(fat_meli: List[dict], fat_mp: List[dict]) -> Tuple[List[dict], Dict[str,float]]:
    itens: List[dict] = []
    buckets_total: Dict[str, float] = {}

    def add_item(key: str, label: str, valor: float, fonte: Dict[str, float]):
        itens.append({"key": key, "label": label, "valor": round(valor, 2), "fontes": fonte})
        # somatório POR BUCKET para o retorno do resumo
        buckets_total[key] = buckets_total.get(key, 0.0) + float(valor or 0.0)

    # NORMALIZA 'detalhe' (minúsculo + sem acento) e aplica regra do "comprador"
    for r in fat_meli:
        r["detalhe"] = _norm(r.get("detalhe"))
        # regra solicitada: linhas com "comprador" não devem somar tarifa
        if "comprador" in r["detalhe"].lower():
            try:
                # zera apenas o valor da tarifa (mantém outros campos para auditoria)
                r["valor_tarifa"] = 0.0
            except Exception:
                r["valor_tarifa"] = 0.0

    # 1) Outras tarifas
    ot = [r for r in fat_meli if r.get("detalhe") == "tarifa por assessoria comercial"]
    v_ot = _sum_val(ot, "valor_tarifa")
    add_item("outras_tarifas", "Outras tarifas", v_ot, {"faturamento_meli": v_ot})

    # 2) Tarifas de venda (apenas cobranças; exclui estornos/cancelamentos)
    tv = [r for r in fat_meli if r.get("detalhe") in {"tarifa de venda", "custo de gestao da venda"}]
    v_tv = _sum_val(tv, "valor_tarifa")
    add_item("tarifas_venda", "Tarifas de venda", v_tv, {"faturamento_meli": v_tv})

    # 3) Envios no Mercado Livre (cobrança)
    # Nova regra: somar (valor_tarifa - envio_por_conta_do_cliente) apenas para esse detalhe.
    env_ml = [
        r for r in fat_meli
        # detalhe já está _norm; compare com minúsculas
        if r.get("detalhe") == "tarifa de envio extra ou intermunicipal"
        and _to_float_local(r.get("valor_tarifa")) > 0
    ]
    v_env_ml = _sum_diff(env_ml, "valor_tarifa", "envio_por_conta_do_cliente")
    # piso em 0 para não negativar após subtração
    if v_env_ml < 0:
        v_env_ml = 0.0
    add_item(
        "tarifas_envios_ml",
        "Tarifas de envios no Mercado Livre",
        v_env_ml,
        {"faturamento_meli": v_env_ml},
    )

    # 4) Publicidade
    pub = [r for r in fat_meli if r.get("detalhe") in {
        "campanhas de publicidade - product ads",
        "campanas de publicidad - brand ads"
    }]
    v_pub = _sum_val(pub, "valor_tarifa")
    add_item("tarifas_publicidade", "Tarifas por campanha de publicidade", v_pub, {"faturamento_meli": v_pub})

    # 5) Envios Full (4 tipos)
    full_set = {
        "custo do servico de coleta full",
        "custo por retirada de estoque full",
        "tarifa pelo servico de armazenamento full",
        "tarifa por estoque antigo no full",
    }
    full = [r for r in fat_meli if r.get("detalhe") in full_set]
    v_full = _sum_val(full, "valor_tarifa")
    add_item("tarifas_envios_full", "Tarifas de envios Full", v_full, {"faturamento_meli": v_full})

    # 6) Parcelamento
    # detalhe está normalizado; prefixo também
    parc = [r for r in fat_meli if str(r.get("detalhe") or "").startswith("taxa de parcelamento")]
    v_parc = _sum_val(parc, "valor_tarifa")
    add_item("taxas_parcelamento", "Taxas de parcelamento", v_parc, {"faturamento_meli": v_parc})

    # 7) Minha página
    mpag = [r for r in fat_meli if r.get("detalhe") == "tarifa de manutencao da minha pagina"]
    v_mpag = _sum_val(mpag, "valor_tarifa")
    add_item("minha_pagina", "Tarifas da Minha página", v_mpag, {"faturamento_meli": v_mpag})

    # 8) Serviços Mercado Pago (valor_tarifa no relatório do MP; excluir estornadas)
    mp = [r for r in fat_mp if not r.get("tarifa_estornada")]
    v_mp = _sum_val(mp, "valor_tarifa")
    add_item("servicos_mercado_pago", "Tarifas dos serviços do Mercado Pago", v_mp, {"faturamento_mp": v_mp})

    # 9) Cancelamentos de tarifas (estornos/cancelamentos do mês)
    canc_details = {
        "cancelamento da tarifa de envio extra ou intermunicipal",
        "estorno da tarifa de venda",
        "estorno do custo de gestao da venda",
    }

    canc = [r for r in fat_meli if r.get("detalhe") in canc_details]
    v_canc = _sum_val(canc, "valor_tarifa")  # deve ser negativo
    add_item("cancelamentos", "Cancelamentos de tarifas", v_canc, {"faturamento_meli": v_canc})

    # (A) Garantir que TODOS os buckets oficiais existam com 0.0 quando ausentes
    for key in REQUIRED_BUCKETS:
        buckets_total.setdefault(key, 0.0)

    # total “inclui”
    return itens, buckets_total

# -------------------- NOVO: suporte a "não mapeados" --------------------
def _is_handled_det(det: str) -> bool:
    """
    Retorna True se 'det' já é coberto pelas regras de compose_sua_fatura_inclui.
    Mantém alinhamento 1:1 com os detalhes usados acima.
    """
    if det in {
        "tarifa por assessoria comercial",
        "tarifa de venda",
        "custo de gestao da venda",
        "tarifa de envio extra ou intermunicipal",
        "campanhas de publicidade - product ads",
        "campanas de publicidad - brand ads",
        "custo do servico de coleta full",
        "custo por retirada de estoque full",
        "tarifa pelo servico de armazenamento full",
        "tarifa por estoque antigo no full",
        "tarifa de manutencao da minha pagina",
        "cancelamento da tarifa de envio extra ou intermunicipal",
        "estorno da tarifa de venda",
        "estorno do custo de gestao da venda",
    }:
        return True
    # Parcelamento é tratado por prefixo
    if det and det.startswith("taxa de parcelamento"):
        return True
    return False

def compose_nao_mapeados(fat_meli: List[dict]) -> Dict[str, float]:
    """
    Agrega os 'detalhes' que NÃO são cobertos por compose_sua_fatura_inclui.
    - Normaliza texto via norm_str (já usada no pipeline)
    - Ignora linhas com 'comprador' (tarifa zerada na etapa anterior)
    - Soma por chave de detalhe normalizada
    """
    out: Dict[str, float] = {}
    for r in fat_meli:
        det = _norm(r.get("detalhe"))
        if not det or "comprador" in det.lower():
            continue
        if _is_handled_det(det):
            continue
        out[det] = out.get(det, 0.0) + _to_float_local(r.get("valor_tarifa"))

    # arredonda
    for k in list(out.keys()):
        out[k] = round(out[k], 2)
    return out

def total_nao_mapeados(d: Dict[str, float]) -> float:
    return round(sum(d.values()), 2)

def compose_ja_cobramos(pagto_estornos: List[dict], detalhe_pagto: List[dict], total_fatura: float) -> List[dict]:
    itens = []

    # Normaliza tipo_pagamento
    for r in pagto_estornos:
        r["tipo_pagamento"] = norm_str(r.get("tipo_pagamento"))

    # 1) Cancelamentos de tarifas em estornos (valor aplicado ao mês)
    est = [r for r in pagto_estornos if r.get("tipo_pagamento").lower().startswith("estorno")]
    v_est = _sum_val(est, "valor_aplicado_mes")
    itens.append({"key":"estornos","label":"Cancelamentos de tarifas em estornos","valor": round(-abs(v_est),2), "fontes":{"pagamentos_estornos": v_est}})

    # 2) Débito automático
    deb = [r for r in pagto_estornos if r.get("tipo_pagamento").lower().startswith("pagamento com débito automático")]
    v_deb = _sum_val(deb, "valor_aplicado_mes")
    itens.append({"key":"debito_automatico","label":"Pagamentos com débito automático","valor": round(-abs(v_deb),2), "fontes":{"pagamentos_estornos": v_deb}})

    # 3) Pagamento cobrado na operação (resíduo)
    v_res = -round(total_fatura + itens[0]["valor"] + itens[1]["valor"], 2)
    itens.append({"key":"cobrado_operacao","label":"Pagamento cobrado na operação","valor": v_res, "fontes":{"residuo": v_res}})

    return itens

def ajustar_cancelamentos_com_estornos_anteriores(sua_fatura_inclui: List[dict], estornos_anteriores: float) -> None:
    # Ajusta a linha 'cancelamentos' somando estornos anteriores (cartão da direita no print)
    for item in sua_fatura_inclui:
        if item["key"] == "cancelamentos":
            item["valor"] = round(item["valor"] + estornos_anteriores, 2)
            item["fontes"]["estornos_anteriores"] = estornos_anteriores
            break
