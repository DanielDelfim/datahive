# scripts/custos/variaveis/produtos/enriquecer_transacoes_com_custo.py
from __future__ import annotations

import argparse
import json
import pathlib as _pl
from typing import Any, Dict, List, Tuple

from app.config.paths import Camada, Regiao
from app.utils.core.io import atomic_write_json  # nome correto
from app.utils.costs.variable.produtos.config import (
    transacoes_por_produto_json,
    transacoes_enriquecidas_json,
    gtins_sem_custo_json,
)
from app.utils.produtos.service import carregar_pp

# prioridade: 'preco_compra' (do cadastro), depois variações
CAMPOS_CUSTO_POSSIVEIS = (
    "preco_compra",
    "custo",
    "preco_custo",
    "unit_cost",
    "cost",
    "preco_custo_unitario",
    "unitPriceCost",
    "custo_unitario",
)
CAMPOS_QTD_POSSIVEIS = ("qtd", "quantidade", "quantity", "qtde", "qte")


def _to_int_regiao(x: str) -> Regiao:
    try:
        return Regiao[x.upper()]
    except KeyError:
        return Regiao(x.lower())


def _to_camada(x: str) -> Camada:
    try:
        return Camada[x.upper()]
    except KeyError:
        return Camada(x.lower())


def _extrair_custo_item(item: Dict[str, Any]) -> float | None:
    for k in CAMPOS_CUSTO_POSSIVEIS:
        v = item.get(k)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            return float(v)
        # aceitar string numérica
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            pass
    return None


def _coletar_itens_produtos(payload_produtos: Any, debug: bool = False) -> List[Dict[str, Any]]:
    """
    Normaliza o payload de produtos para lista de dicts.
    Aceita formatos:
      - {"items": [ {...}, ... ]}
      - {"items": { "<gtin>": {...}, ... }}
      - [ {...}, {...} ]
      - {"pp": [ {...}, ... ], ...}
      - {"789...": {...}, "790...": {...}}
    """
    itens: List[Dict[str, Any]] = []

    if isinstance(payload_produtos, dict):
        items = payload_produtos.get("items")
        if isinstance(items, list):
            itens.extend([x for x in items if isinstance(x, dict)])
        elif isinstance(items, dict):
            itens.extend([x for x in items.values() if isinstance(x, dict)])
        # varrer demais valores também (robustez)
        for v in payload_produtos.values():
            if isinstance(v, dict):
                itens.append(v)
            elif isinstance(v, list):
                itens.extend([x for x in v if isinstance(x, dict)])

    elif isinstance(payload_produtos, list):
        itens.extend([x for x in payload_produtos if isinstance(x, dict)])

    if debug:
        kind = type(payload_produtos).__name__
        n_src = (len(payload_produtos) if isinstance(payload_produtos, (list, dict)) else 0)
        print(f"[DBG] produtos payload tipo={kind} tamanho={n_src} itens_dicts={len(itens)}")

    return itens


def _construir_mapa_custo_por_gtin(payload_produtos: Any, debug: bool = False) -> Dict[str, float]:
    itens = _coletar_itens_produtos(payload_produtos, debug=debug)
    mapa: Dict[str, float] = {}
    for it in itens:
        # tenta vários campos para GTIN
        gtin = (str(it.get("gtin") or it.get("ean") or it.get("barcode") or it.get("id") or it.get("sku") or "")).strip()
        # heurística: tratar id/sku numérico de 13-14 dígitos como GTIN
        if not gtin:
            s = str(it.get("id") or "")
            if s.isdigit() and 13 <= len(s) <= 14:
                gtin = s
        # rejeita GTIN anômalo (não 13–14 dígitos ou não numérico)
        if not gtin or not gtin.isdigit() or not (13 <= len(gtin) <= 14):
            continue
        custo = _extrair_custo_item(it)
        if custo is not None:
            mapa[gtin] = float(custo)
    return mapa


def _qtd_from_row(row: Dict[str, Any]) -> float | None:
    for k in CAMPOS_QTD_POSSIVEIS:
        if k in row and row[k] is not None:
            try:
                return float(str(row[k]).replace(",", "."))
            except Exception:
                pass
    return None


def _load_json(path: str) -> Any:
    p = _pl.Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Fonte não encontrada: {p}\n"
            f"Dica: confira se DATA_DIR está correto (ex.: C:\\Apps\\Datahive\\data)."
        )
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _is_list_of_dicts(x: Any) -> bool:
    return isinstance(x, list) and (len(x) == 0 or isinstance(x[0], dict))


def _extract_transacoes(data: Any, debug: bool = False) -> Tuple[List[Dict[str, Any]], str | None]:
    """
    Extrai lista de transações e retorna também o nome da chave usada (se houver).
    Preferência:
      1) data['records'] (formato meta+records)
      2) chaves candidatas: 'transacoes','transactions','items','rows','data','results','lista'
      3) dict mapeado id->obj (values())
      4) primeiro valor list[dict]
      5) se data já for list[dict], retorna direto
    """
    if _is_list_of_dicts(data):
        if debug:
            print("[DBG] transacoes detectadas: raíz é list[dict]")
        return data, None

    if isinstance(data, dict):
        if "records" in data and _is_list_of_dicts(data["records"]):
            if debug:
                print("[DBG] transacoes detectadas: data['records'] list[dict] (formato com meta+records)")
            return data["records"], "records"

        candidates = ("transacoes", "transactions", "items", "rows", "data", "results", "lista")
        for key in candidates:
            if key in data and _is_list_of_dicts(data[key]):
                if debug:
                    print(f"[DBG] transacoes detectadas: data['{key}'] list[dict]")
                return data[key], key

        values = list(data.values())
        if values and all(isinstance(v, dict) for v in values):
            if debug:
                print("[DBG] transacoes detectadas: dict mapeado id->obj (values())")
            return values, None

        for k, v in data.items():
            if _is_list_of_dicts(v):
                if debug:
                    print(f"[DBG] transacoes detectadas: primeiro list[dict] em data['{k}']")
                return v, k

    raise ValueError("Estrutura inesperada: não encontrei lista de transações (list[dict]) no JSON de entrada.")


def _enriquecer_transacoes(transacoes: List[Dict[str, Any]], custo_por_gtin: Dict[str, float]) -> Tuple[List[Dict[str, Any]], List[str]]:
    faltantes: set[str] = set()
    out: List[Dict[str, Any]] = []

    for row in transacoes:
        gtin = (str(row.get("gtin") or row.get("ean") or "")).strip()
        # política conservadora: se GTIN inválido, marcar como faltante
        if gtin and (not gtin.isdigit() or not (13 <= len(gtin) <= 14)):
            faltantes.add(gtin)
            out.append(dict(row))
            continue

        novo = dict(row)
        if gtin and gtin in custo_por_gtin:
            custo_unit = custo_por_gtin[gtin]
            novo["custo_unitario"] = round(float(custo_unit), 6)
            qtd = _qtd_from_row(row)
            if qtd is not None:
                novo["custo_total"] = round(float(qtd) * float(custo_unit), 6)
        else:
            faltantes.add(gtin if gtin else "__SEM_GTIN__")

        out.append(novo)

    return out, sorted(faltantes)


def main():
    ap = argparse.ArgumentParser(description="Enriquecer transações por produto com custo unitário por GTIN.")
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--regiao", type=str, required=True, help="ex.: mg, sp")
    ap.add_argument("--camada", type=str, default="pp", help="pp|raw (default: pp)")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    regiao = _to_int_regiao(args.regiao)
    camada = _to_camada(args.camada)

    src_path = transacoes_por_produto_json(args.ano, args.mes, regiao, camada)
    dst_enriquecido = transacoes_enriquecidas_json(args.ano, args.mes, regiao, camada)
    dst_faltantes = gtins_sem_custo_json(args.ano, args.mes, regiao, camada)

    if args.debug:
        print(f"[DBG] src: {src_path}")
        print(f"[DBG] dst_enriquecido: {dst_enriquecido}")
        print(f"[DBG] dst_faltantes: {dst_faltantes}")
        print("[DBG] carregando produtos...")

    produtos_payload = carregar_pp(camada=camada)
    custo_por_gtin = _construir_mapa_custo_por_gtin(produtos_payload, debug=args.debug)

    data = _load_json(src_path)
    transacoes, chave = _extract_transacoes(data, debug=args.debug)

    enriquecidas, faltantes = _enriquecer_transacoes(transacoes, custo_por_gtin)

    # Preserva estrutura original quando possível
    if isinstance(data, dict):
        data_out = dict(data)
        if chave and chave in data and _is_list_of_dicts(data[chave]):
            data_out[chave] = enriquecidas
        elif "records" in data and _is_list_of_dicts(data["records"]):
            data_out["records"] = enriquecidas
        else:
            data_out["transacoes"] = enriquecidas
    else:
        data_out = enriquecidas

    if args.debug:
        print(f"[DBG] transacoes: {len(transacoes)} | enriquecidas: {len(enriquecidas)} | gtins_sem_custo: {len(faltantes)}")

    # Escritas atômicas com backup
    atomic_write_json(dst_enriquecido, data_out, do_backup=True)
    atomic_write_json(dst_faltantes, {"gtins_sem_custo": faltantes}, do_backup=True)


if __name__ == "__main__":
    main()
