from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set
import re

from app.config.paths import Regiao
from app.utils.core.io import ler_json as read_json
from .config import (
    get_regras_ml,
    produtos_pp_candidates,
    anuncios_pp_candidates_meli,
)
from .metrics import calcular_componentes


# =========================================================
# Utilitários de parsing
# =========================================================

_RECORD_HINT_KEYS = {"id", "mlb", "sku", "gtin", "title", "price", "preco", "preco_venda"}

def _looks_like_record(d: Mapping[str, Any]) -> bool:
    return any(k in d for k in _RECORD_HINT_KEYS)

def _extract_dicts(obj: Any, out: List[Dict[str, Any]], _depth: int = 0, _max_depth: int = 6) -> None:
    """Extrai recursivamente dicts “folha” de estruturas (listas/dicts) arbitrárias."""
    if _depth > _max_depth or obj is None:
        return
    if isinstance(obj, list):
        for el in obj:
            _extract_dicts(el, out, _depth + 1, _max_depth)
        return
    if isinstance(obj, Mapping):
        if _looks_like_record(obj):
            out.append(dict(obj))
            return
        for v in obj.values():
            _extract_dicts(v, out, _depth + 1, _max_depth)
        return
    # Demais tipos: ignorar


def _iter_registros(seq_or_map: Any) -> Iterable[Dict[str, Any]]:
    """Itera registros quando já estiver “achatado” em lista ou dict."""
    if isinstance(seq_or_map, Mapping):
        for v in seq_or_map.values():
            if isinstance(v, Mapping):
                yield dict(v)
    elif isinstance(seq_or_map, Iterable) and not isinstance(seq_or_map, (str, bytes)):
        for v in seq_or_map:
            if isinstance(v, Mapping):
                yield dict(v)


# =========================================================
# Match Produto ↔ Anúncio
# =========================================================

def _normalize_sku(s: Any) -> str:
    s = str(s or "").strip()
    if not s:
        return ""
    # remove sufixo após "-", por ex. "7898915380026-2" → "7898915380026"
    return re.split(r"[\s\-]", s)[0]

def _build_index_produtos(produtos: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    idx: Dict[str, Mapping[str, Any]] = {}
    for p in produtos:
        sku = str(p.get("sku") or "").strip()
        gtin = str(p.get("gtin") or "").strip()
        if sku:
            idx[f"sku:{sku}"] = p
            # também indexa sku normalizado (se diferente)
            sku_n = _normalize_sku(sku)
            if sku_n and sku_n != sku:
                idx[f"sku:{sku_n}"] = p
        if gtin:
            idx[f"gtin:{gtin}"] = p
    return idx

def _candidate_keys_from_gtin_field(gtin_field: Any) -> List[str]:
    """Alguns anúncios trazem GTINs concatenados. Extraímos substrings numéricas (8–14)."""
    s = re.sub(r"\D", "", str(gtin_field or ""))
    keys: List[str] = []
    n = len(s)
    for L in range(14, 7, -1):  # tenta maiores primeiro
        for i in range(0, n - L + 1):
            keys.append(s[i:i+L])
    return keys

def _match_produto(idx: Mapping[str, Mapping[str, Any]], anuncio: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    # 1) sku direto → sku normalizado
    sku = (anuncio.get("sku") or "").strip()
    if sku and f"sku:{sku}" in idx:
        return idx[f"sku:{sku}"]
    sku_n = _normalize_sku(sku)
    if sku_n and f"sku:{sku_n}" in idx:
        return idx[f"sku:{sku_n}"]

    # 2) gtin direto
    gtin = (anuncio.get("gtin") or "").strip()
    if gtin and f"gtin:{gtin}" in idx:
        return idx[f"gtin:{gtin}"]

    # 3) substrings numéricas dentro do campo gtin
    for sub in _candidate_keys_from_gtin_field(gtin):
        if f"gtin:{sub}" in idx:
            return idx[f"gtin:{sub}"]
        if f"sku:{sub}" in idx:
            return idx[f"sku:{sub}"]

    # 4) substrings numéricas dentro do campo sku (quando sku contém sufixos mais complexos)
    for sub in _candidate_keys_from_gtin_field(sku):
        if f"sku:{sub}" in idx:
            return idx[f"sku:{sub}"]
        if f"gtin:{sub}" in idx:
            return idx[f"gtin:{sub}"]

    return None


# =========================================================
# Extração de campos e flags
# =========================================================

def _is_full(anuncio: Mapping[str, Any]) -> bool:
    if anuncio.get("fulfillment") is True:
        return True
    if anuncio.get("is_full") is True:
        return True
    if str(anuncio.get("logistic_type", "")).lower() in {"fulfillment", "fulfillment_center"}:
        return True
    return False

def _preco_venda(anuncio: Mapping[str, Any]) -> Optional[float]:
    # Prioridade: rebate_price > price > (fallbacks antigos)
    for k in ("rebate_price", "price", "sale_price", "preco", "preco_venda"):
        if k in anuncio and anuncio[k] is not None:
            try:
                return float(anuncio[k])
            except (TypeError, ValueError):
                continue
    return None

def _subsidio_tarifa(anuncio: Mapping[str, Any]) -> float:
    """
    Subsídio de tarifa concedido pelo ML quando há rebate:
      subsidio = max(price - rebate_price, 0)
    Retorna 0.0 quando rebate_price não existir/for nulo.
    """
    try:
        price = float(anuncio.get("price", 0) or 0)
        rebate = anuncio.get("rebate_price", None)
        if rebate is None:
            return 0.0
        rebate = float(rebate)
        return max(price - rebate, 0.0)
    except (TypeError, ValueError):
        return 0.0

def _sku_normalizado(s: Any) -> str:
    s = str(s or "").strip()
    if not s:
        return ""
    # remove sufixos (ex.: "7898915380927-2" -> "7898915380927")
    for sep in (" ", "-"):
        if sep in s:
            return s.split(sep, 1)[0]
    return s

def _custo_do_produto(produto: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not produto:
        return None
    for k in ("custo", "preco_custo", "cost", "preco_compra"):
        if k in produto and produto[k] is not None:
            try:
                return float(produto[k])
            except (TypeError, ValueError):
                continue
    return None

def _peso_em_kg(produto: Mapping[str, Any]) -> float:
    # estrutura aninhada do seu catálogo: pesos_g.{bruto, liq} — os valores estão em kg
    try:
        pesos_g = produto.get("pesos_g") or {}
        if isinstance(pesos_g, Mapping):
            if pesos_g.get("bruto") is not None:
                return float(pesos_g["bruto"])
            if pesos_g.get("liq") is not None:
                return float(pesos_g["liq"])
    except (TypeError, ValueError):
        pass
    for k in ("peso_kg", "weight_kg", "kg"):
        v = produto.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    for k in ("peso_g", "weight_g", "g"):
        v = produto.get(k)
        if v is not None:
            try:
                return float(v) / 1000.0
            except (TypeError, ValueError):
                pass
    return 0.0


# =========================================================
# Regras do YAML (seleção de fixos / frete grátis 40538)
# =========================================================

def _resolver_fixo_nao_full_por_preco(regras_nf: Mapping[str, Any], preco: float) -> float:
    faixas = regras_nf.get("custo_fixo_por_unidade_brl") or []
    fixo_brl = 0.0
    aplicado = False
    for item in faixas:
        if item.get("otherwise"):
            if not aplicado:
                try:
                    fixo_brl = float(item.get("valor", 0.0))
                except (TypeError, ValueError):
                    fixo_brl = 0.0
            break
        try:
            max_preco = float(item.get("max_preco", 0.0))
        except (TypeError, ValueError):
            continue
        if preco <= max_preco:
            if "valor_pct_do_preco" in item:
                try:
                    fixo_brl = preco * float(item["valor_pct_do_preco"])
                except (TypeError, ValueError):
                    fixo_brl = 0.0
            else:
                try:
                    fixo_brl = float(item.get("valor", 0.0))
                except (TypeError, ValueError):
                    fixo_brl = 0.0
            aplicado = True
            break
    return fixo_brl

def _banda_preco_key(preco: float) -> Optional[str]:
    if 79.0 <= preco <= 99.99:
        return "79-99.99"
    if 100.0 <= preco <= 119.99:
        return "100-119.99"
    if 120.0 <= preco <= 149.99:
        return "120-149.99"
    if 150.0 <= preco <= 199.99:
        return "150-199.99"
    if preco > 200.0:
        return ">200"
    return None

def _frete_gratis_40538_valor(regras_nf: Mapping[str, Any], preco: float, peso_kg: float) -> float:
    cfg = regras_nf.get("frete_gratis_40538") or {}
    try:
        threshold = float(cfg.get("threshold_preco_brl", 79.0))
    except (TypeError, ValueError):
        threshold = 79.0
    if preco < threshold:
        return 0.0
    bandas = cfg.get("tabelas_por_preco") or {}
    key = _banda_preco_key(preco)
    if not key or key not in bandas:
        return 0.0
    faixas = bandas[key] or []
    for item in faixas:
        try:
            max_kg = float(item.get("max_kg", 0.0))
        except (TypeError, ValueError):
            continue
        if peso_kg <= max_kg:
            try:
                return float(item.get("valor", 0.0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0

def _fixo_full_por_preco(regras_full: Mapping[str, Any], preco: float) -> float:
    faixas = regras_full.get("custo_fixo_por_unidade_brl") or []
    fixo = 0.0
    aplicado = False
    for item in faixas:
        if item.get("otherwise"):
            if not aplicado:
                try:
                    fixo = float(item.get("valor", 0.0))
                except (TypeError, ValueError):
                    fixo = 0.0
            break
        try:
            max_preco = float(item.get("max_preco", 0.0))
        except (TypeError, ValueError):
            continue
        if preco <= max_preco:
            try:
                fixo = float(item.get("valor", 0.0))
            except (TypeError, ValueError):
                fixo = 0.0
            aplicado = True
            break
    return fixo


# =========================================================
# API pública
# =========================================================

def precificar_meli(regiao: Regiao | None = None) -> List[Dict[str, Any]]:
    """
    Retorna 1 linha por anúncio do Mercado Livre:
      - MCP completo quando existir custo do produto;
      - MCP “sem custo” (base) quando o produto não estiver no catálogo.
    """
    regras = get_regras_ml()

    # ---- Anúncios (tenta múltiplos candidatos; pode mesclar) ----
    cand_anuncios = anuncios_pp_candidates_meli(regiao=regiao)
    existentes_anuncios: List[Path] = [Path(p) for p in cand_anuncios if Path(p).exists()]
    if not existentes_anuncios:
        pretty = "\n - ".join(str(p) for p in cand_anuncios)
        raise FileNotFoundError(
            "Não foi possível localizar o PP de anúncios do Mercado Livre.\n"
            "Caminhos testados:\n - " + pretty
        )
    anuncios_records: List[Dict[str, Any]] = []
    for p in existentes_anuncios:
        data = read_json(p)
        _extract_dicts(data, anuncios_records)

    # Deduplicar anúncios por mlb/id
    seen: Set[str] = set()
    anuncios: List[Dict[str, Any]] = []
    for a in anuncios_records:
        k = str(a.get("mlb") or a.get("id") or "")
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        anuncios.append(a)

    if not anuncios:
        pretty = "\n - ".join(str(p) for p in existentes_anuncios)
        raise RuntimeError(
            "Nenhum anúncio válido foi encontrado após leitura e parsing.\n"
            "Verifique o conteúdo dos arquivos:\n - " + pretty
        )

    # ---- Produtos (tenta múltiplos candidatos; pode mesclar) ----
    cand_produtos = produtos_pp_candidates()
    existentes_prod: List[Path] = [Path(p) for p in cand_produtos if Path(p).exists()]
    if not existentes_prod:
        pretty_p = "\n - ".join(str(p) for p in cand_produtos)
        raise FileNotFoundError(
            "Não foi possível localizar o PP de produtos.\n"
            "Caminhos testados:\n - " + pretty_p
        )
    produtos_records: List[Dict[str, Any]] = []
    for p in existentes_prod:
        data_p = read_json(p)
        _extract_dicts(data_p, produtos_records)

    # Índice para match rápido
    produtos_idx = _build_index_produtos(produtos_records)

    # ---- Cálculo por anúncio (sempre 1 linha) ----
    resultados: List[Dict[str, Any]] = []
    for a in anuncios:
        preco = _preco_venda(a)
        full = _is_full(a)
        produto = _match_produto(produtos_idx, a)
        custo_produto = _custo_do_produto(produto)

        # custo fixo (R$) conforme perfil
        fixo_brl = 0.0
        if preco is not None:
            if full:
                fixo_brl = _fixo_full_por_preco(regras.get("full", {}), preco)
            else:
                fixo_brl = _resolver_fixo_nao_full_por_preco(regras.get("nao_full", {}), preco)
                if produto:
                    peso_kg = _peso_em_kg(produto)
                    fg = _frete_gratis_40538_valor(regras.get("nao_full", {}), preco, peso_kg)
                    if fg > 0:
                        fixo_brl = fg

        # percentuais
        try:
            comissao_pct = float(regras["comissao"]["classico_pct"])
        except (TypeError, ValueError, KeyError):
            comissao_pct = 0.14
        imposto_pct = float(regras["default"]["imposto_pct"])
        marketing_pct = float(regras["default"]["marketing_pct"])

        # Monta linha de saída
        base = {
            "canal": "meli",
            "regiao": getattr(regiao, "value", None),
            "mlb": a.get("mlb") or a.get("id"),
            "sku": a.get("sku"),
            "gtin": a.get("gtin"),
            "title": a.get("title"),
            "full": full,
            "preco_venda": preco,
            "custo_fixo_brl": fixo_brl,
        }

        # 1) Sem preço → não dá para calcular nada
        if preco is None:
            resultados.append({**base, "status": "faltando_preco", "mcp_pct": None, "mcp_sem_custo_pct": None})
            continue

        # 2) Calcular “MCP base” (sem custo de produto) — sempre possível com preço
        comp_base = calcular_componentes(
            preco_venda=preco,
            custo=0.0 + fixo_brl,
            imposto_pct=imposto_pct,
            frete_pct=0.0,
            marketing_pct=marketing_pct,
            take_rate_pct=comissao_pct,
        )
        mcp_sem_custo = comp_base["mcp_pct"]

        # 3) Se existir custo de produto → MCP completo
        if custo_produto is not None:
            comp_full = calcular_componentes(
                preco_venda=preco,
                custo=custo_produto + fixo_brl,
                imposto_pct=imposto_pct,
                frete_pct=0.0,
                marketing_pct=marketing_pct,
                take_rate_pct=comissao_pct,
            )
            resultados.append({
                **base,
                "custo": comp_full["custo"],
                "imposto_valor": comp_full["imposto_valor"],
                "marketing_valor": comp_full["marketing_valor"],
                "tarifa_canal_valor": comp_full["tarifa_canal_valor"],
                "mc_valor": comp_full["mc_valor"],
                "mcp_pct": comp_full["mcp_pct"],
                "mcp_sem_custo_pct": mcp_sem_custo,
                "status": "ok",
            })
        else:
            # Sem custo → entrega MCP base e status explícito
            resultados.append({
                **base,
                "custo": None,
                "imposto_valor": comp_base["imposto_valor"],
                "marketing_valor": comp_base["marketing_valor"],
                "tarifa_canal_valor": comp_base["tarifa_canal_valor"],
                "mc_valor": comp_base["mc_valor"],
                "mcp_pct": None,
                "mcp_sem_custo_pct": mcp_sem_custo,
                "status": "produto_nao_encontrado",
            })

    return resultados

def listar_anuncios_meli(regiao: Regiao | None = None) -> List[Dict[str, Any]]:
    """
    Retorna somente os campos básicos do anúncio (sem MCP):
      canal, regiao, mlb, sku, gtin, title, full, preco_venda
    """
    # ---- Anúncios (tenta múltiplos candidatos; pode mesclar) ----
    cand_anuncios = anuncios_pp_candidates_meli(regiao=regiao)
    existentes_anuncios: List[Path] = [Path(p) for p in cand_anuncios if Path(p).exists()]
    if not existentes_anuncios:
        pretty = "\n - ".join(str(p) for p in cand_anuncios)
        raise FileNotFoundError(
            "Não foi possível localizar o PP de anúncios do Mercado Livre.\n"
            "Caminhos testados:\n - " + pretty
        )
    anuncios_records: List[Dict[str, Any]] = []
    for p in existentes_anuncios:
        data = read_json(p)
        _extract_dicts(data, anuncios_records)

    # Deduplicar por mlb/id
    seen: Set[str] = set()
    anuncios: List[Dict[str, Any]] = []
    for a in anuncios_records:
        k = str(a.get("mlb") or a.get("id") or "")
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        anuncios.append(a)

    saida: List[Dict[str, Any]] = []
    reg = getattr(regiao, "value", None)
    for a in anuncios:
        preco = _preco_venda(a)
        sku = a.get("sku")
        saida.append({
            "canal": "meli",
            "regiao": reg,
            "mlb": a.get("mlb") or a.get("id"),
            "sku": sku,
            "sku_normalizado": _sku_normalizado(sku) if sku else None,
            "gtin": a.get("gtin"),
            "title": a.get("title"),
            "full": _is_full(a),
            "preco_venda": preco if isinstance(preco, float) else None,
            # levar valores brutos para que as métricas apliquem o subsídio de tarifa
            "price": a.get("price"),
            "rebate_price": a.get("rebate_price"),
            "subsidio_tarifa_brl": _subsidio_tarifa(a),
        })
    return saida
