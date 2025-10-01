from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from datetime import date

from app.utils.costs.variable.meli.config import pp_dir
from app.utils.costs.variable.meli.config import pp_outfile_fatura_resumo

from .aggregator import (
    compose_sua_fatura_inclui,
    compose_ja_cobramos,
    ajustar_cancelamentos_com_estornos_anteriores,
)
# imports opcionais (se disponíveis no aggregator)
try:
    from .aggregator import compose_nao_mapeados, total_nao_mapeados  # type: ignore
except Exception:
    compose_nao_mapeados = None
    total_nao_mapeados = None

# ----------------- helpers de I/O -----------------

def _load_json(p: Path) -> dict | list:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _require_file(p: Path) -> None:
    if p.exists():
        return
    folder = p.parent
    listed = []
    if folder.exists():
        listed = sorted(x.name for x in folder.glob("*.json"))
    msg = (
        f"Arquivo esperado não encontrado: {p}\n"
        f"Arquivos .json disponíveis em {folder}:\n"
        + (" - " + "\n - ".join(listed) if listed else " (nenhum)")
    )
    raise FileNotFoundError(msg)

# ----------------- helpers de datas -----------------

def _parse_iso_date(s) -> date | None:
    if not s:
        return None
    try:
        if isinstance(s, date):
            return s
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None

def _date_range_for(rows: list[dict], fields: list[str]) -> tuple[str | None, str | None]:
    dmin, dmax = None, None
    for r in rows:
        for f in fields:
            d = _parse_iso_date(r.get(f))
            if d is None:
                continue
            if dmin is None or d < dmin:
                dmin = d
            if dmax is None or d > dmax:
                dmax = d
    return (dmin.isoformat() if dmin else None, dmax.isoformat() if dmax else None)

def _merge_ranges(*ranges: tuple[date | None, date | None]) -> tuple[str | None, str | None]:
    gmin, gmax = None, None
    for (dmin, dmax) in ranges:
        if dmin is not None and (gmin is None or dmin < gmin):
            gmin = dmin
        if dmax is not None and (gmax is None or dmax > gmax):
            gmax = dmax
    return (gmin.isoformat() if gmin else None, gmax.isoformat() if gmax else None)

# ----------------- ajuste de estornos anteriores -----------------

def _estornos_anteriores(pagamentos_estornos: List[dict]) -> float:
    total = 0.0
    for r in pagamentos_estornos:
        v = r.get("valor_aplicado_outro_mes")
        if v is None:
            continue
        try:
            total += float(v)
        except Exception:
            pass
    return round(total, 2)

# ----------------- função principal -----------------

def build_resumo_fatura(ano: int, mes: int, regiao, competencia: Optional[str] = None) -> Dict[str, Any]:
    pp = pp_dir(ano, mes, regiao)

    # Nomes corretos (PP)
    p_fat_meli = pp / "faturamento_meli_pp.json"
    p_fat_mp   = pp / "faturamento_mercadopago_pp.json"
    p_pag_est  = pp / "pagamentos_estornos_pp.json"
    p_det_mes  = pp / "detalhe_pagamentos_mes_pp.json"

    # Validação explícita + dica do que existe
    for p in (p_fat_meli, p_fat_mp, p_pag_est, p_det_mes):
        _require_file(p)

    # Carregar
    fat_meli = _load_json(p_fat_meli).get("rows", [])
    fat_mp   = _load_json(p_fat_mp).get("rows", [])
    pagtos   = _load_json(p_pag_est).get("rows", [])
    detalhes = _load_json(p_det_mes).get("rows", [])

    periodo_meli = _date_range_for(fat_meli, ["data_tarifa"])  # fallback incluir "data_venda" se quiser
    periodo_mp = _date_range_for(fat_mp, ["data_movimento"])
    periodo_pagamentos = _date_range_for(pagtos, ["data_pagamento_ou_estorno", "data_cancelamento"])
    periodo_detalhe = _date_range_for(detalhes, ["data_pagamento", "data_tarifa"])

    # “Sua fatura inclui” — aceitar retorno com 2 ou 3 itens
    _res = compose_sua_fatura_inclui(fat_meli, fat_mp)
    # _res pode ser: (itens, inclui_dict) ou (itens, inclui_dict, nao_mapeados)
    if isinstance(_res, (tuple, list)) and len(_res) >= 2:
        itens_inclui = _res[0]
        inclui_dict = _res[1]
        nao_mapeados = _res[2] if len(_res) >= 3 else {}
    else:
        raise ValueError("compose_sua_fatura_inclui retornou formato inesperado")

    # fallback: se aggregator não retornou 'nao_mapeados' e houver helper disponível
    if not nao_mapeados and compose_nao_mapeados:
        try:
            nao_mapeados = compose_nao_mapeados(fat_meli)  # type: ignore
        except Exception:
            nao_mapeados = {}

    # Ajuste com “Estornos de faturas anteriores”
    ea = _estornos_anteriores(pagtos)
    ajustar_cancelamentos_com_estornos_anteriores(itens_inclui, ea)

    # total_fatura a partir do dicionário de buckets
    total_fatura = round(sum(inclui_dict.values()), 2)

    # 'já cobramos' vem como lista -> converter para dict com chaves esperadas
    cobramos_list = compose_ja_cobramos(pagtos, detalhes, total_fatura)
    cobramos_dict = {}
    try:
        for it in cobramos_list:
            k = it.get("key")
            v = float(it.get("valor") or 0.0)
            if k:
                cobramos_dict[k] = v
    except Exception:
        pass
    # garantir chaves esperadas com 0.0 quando ausentes
    for _k in ("estornos", "debito_automatico", "cobrado_operacao"):
        cobramos_dict.setdefault(_k, 0.0)

    total_recebido = round(sum(cobramos_dict.values()), 2)
    falta_pagar = round(total_fatura + total_recebido, 2)

    return {
        "meta": {
            "ano": ano,
            "mes": mes,
            "regiao": regiao.value if hasattr(regiao, "value") else str(regiao),
            "competencia": competencia,
            "fonte_pp": str(pp),
            # <<< NOVO: períodos individuais + período de fatura (âncora = meli)
            "periodos": {
                "faturamento_meli": {"min_date": periodo_meli[0], "max_date": periodo_meli[1]},
                "faturamento_mercadopago": {"min_date": periodo_mp[0], "max_date": periodo_mp[1]},
                "pagamentos_estornos": {"min_date": periodo_pagamentos[0], "max_date": periodo_pagamentos[1]},
                "detalhe_pagamentos_mes": {"min_date": periodo_detalhe[0], "max_date": periodo_detalhe[1]},
            },
            "periodo_fatura": {"min_date": periodo_meli[0], "max_date": periodo_meli[1]},
        },
        "sua_fatura_inclui": inclui_dict,
        "nao_mapeados": nao_mapeados,
        "nao_mapeados_total": round(sum(nao_mapeados.values()), 2) if isinstance(nao_mapeados, dict) else 0.0,
        "ja_cobramos": cobramos_dict,
        "total_fatura": total_fatura,
        "total_recebido": total_recebido,
        "falta_pagar": falta_pagar,
        "cartao_lateral": {"estornos_faturas_anteriores": ea},
    }



# ----------------- NOVO: leitura do fatura_resumo_pp.json pronto -----------------
def read_fatura_resumo_pp_file(
    ano: int,
    mes: int,
    regiao,
    camada=None,
    *,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Lê o arquivo já pré-processado em:
      data/costs/variable/meli/{ano}/{mes}/{regiao}/pp/fatura_resumo_pp.json
    (Usa o helper existente em meli/config.py)
    """
    p = pp_outfile_fatura_resumo(ano, mes, regiao)
    if debug:
        print(f"[DBG] fatura_resumo_pp.json → {p}")
    if not Path(p).exists():
        if debug:
            print("[WARN] fatura_resumo_pp.json não encontrado")
        return {}
    with Path(p).open("r", encoding="utf-8") as f:
        return json.load(f)