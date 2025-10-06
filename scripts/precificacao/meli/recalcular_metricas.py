
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json

from app.utils.precificacao.config import Periodo, get_precificacao_dataset_path
from app.utils.precificacao.service import executar, salvar_dataset
from app.utils.precificacao.metrics import carregar_regras_ml, preco_efetivo, _is_full_item
from app.utils.precificacao.custos_meli import custo_fixo_full
from app.config.paths import Regiao

# scripts/precificacao/meli/recalcular_metricas.py  (substituir apenas esta função)

from app.utils.precificacao.metrics import (
    calcular_metricas_item,
)

def _overwrite_commission_and_fixed(doc: dict, regras: dict, use_rebate_as_price: bool = True) -> dict:
    default = (regras or {}).get("default", {}) or {}
    cfg_comissao = (regras or {}).get("comissao", {}) or {}

    itens = doc.get("itens") or []
    out = []

    for it in itens:
        # preço efetivo
        p = preco_efetivo(
            it.get("price"),
            it.get("rebate_price_discounted"),
            considerar_rebate=use_rebate_as_price
        )
        it["preco_efetivo"] = p

        # comissão absoluta e custo fixo FULL
        # (se já existir, sobrescrevemos para manter regra atualizada do YAML)
        # pct por logística:
        if _is_full_item(it):
            comissao_base = cfg_comissao.get("full") or cfg_comissao.get("fulfillment") \
                            or cfg_comissao.get("classico_pct") or default.get("comissao_pct")
        else:
            comissao_base = cfg_comissao.get("seller") or cfg_comissao.get("classico_pct") \
                            or default.get("comissao_pct")
        comissao_pct = float(comissao_base or 0.0)
        it["comissao_pct"] = comissao_pct
        it["comissao"] = (p * comissao_pct) if (p and p > 0) else None

        if _is_full_item(it):
            it["custo_fixo_full"] = custo_fixo_full(p, regras) if (p is not None and p > 0) else 0.0
        else:
            it["custo_fixo_full"] = None

        # imposto/marketing absolutos (se faltarem)
        imposto_pct = float(default.get("imposto_pct") or 0.0)
        marketing_pct = float(default.get("marketing_pct") or 0.0)
        it["imposto_pct"] = imposto_pct
        it["marketing_pct"] = marketing_pct
        it["imposto"] = (p * imposto_pct) if (p and p > 0) else None
        it["marketing"] = (p * marketing_pct) if (p and p > 0) else None

        # frete (se ausente): frete_pct_sobre_custo * preco_compra
        if it.get("frete_sobre_custo") in (None, ""):
            fr_pct = float(default.get("frete_pct_sobre_custo") or 0.0)
            pc = it.get("preco_compra") or 0.0
            it["frete_sobre_custo"] = float(pc) * fr_pct

        # >>> Recalcula métricas do item para refletir os novos valores
        calc = calcular_metricas_item(it, regras=regras, use_rebate_as_price=use_rebate_as_price)
        it = {**it, **calc}

        out.append(it)

    doc2 = dict(doc)
    doc2["itens"] = out
    return doc2


def _count_with_metrics(dataset_path: Path) -> tuple[int, int]:
    try:
        with dataset_path.open("r", encoding="utf-8") as f:
            doc = json.load(f)
        items = doc.get("itens", []) or []
        total = len(items)
        with_metrics = sum(1 for it in items if it.get("mcp") is not None)
        return total, with_metrics
    except Exception:
        return 0, 0

def main():
    ap = argparse.ArgumentParser(description="Precificação: recalcula e garante comissão/custo fixo no dataset final.")
    ap.add_argument("--regiao", choices=["sp", "mg"], required=True)
    ap.add_argument("--ano", type=int, default=None, help="Opcional _meta")
    ap.add_argument("--mes", type=int, default=None, help="Opcional _meta (1..12)")
    ap.add_argument("--no-rebate", action="store_true", help="Se presente, NÃO usar rebate como preço efetivo.")
    ap.add_argument("--debug", action="store_true", help="StdoutSink extra.")
    args = ap.parse_args()

    # Periodo só para _meta; saída é por região fixa
    now = datetime.now(timezone.utc)
    ano = args.ano or now.year
    mes = args.mes or now.month
    periodo = Periodo(ano, mes)
    regiao_enum = Regiao.SP if args.regiao == "sp" else Regiao.MG

    # 1) Executa fluxo completo (base→custo→métricas) e grava os 2 artefatos
    executar(
        periodo,
        regiao_enum,
        use_rebate_as_price=(not args.no_rebate),
        keep=7,
        debug=args.debug,
    )

    # 2) Recarrega dataset e sobrescreve comissão/custo_fixo_full com base nas fórmulas puras
    ds_path = get_precificacao_dataset_path(regiao_enum)
    with ds_path.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    regras = carregar_regras_ml()
    doc2 = _overwrite_commission_and_fixed(doc, regras, use_rebate_as_price=(not args.no_rebate))

    # 3) Persiste novamente (canônico) via service.salvar_dataset (inclui _meta e hash)
    salvar_dataset(doc2, regiao_enum, keep=7, debug=args.debug)

    # 4) Estatísticas
    total, com_metricas = _count_with_metrics(ds_path)
    print(f"[ok] {ds_path}")
    print(f"[stats] itens={total} | com_metricas={com_metricas} | rebate={'off' if args.no_rebate else 'on'}")

if __name__ == "__main__":
    main()
