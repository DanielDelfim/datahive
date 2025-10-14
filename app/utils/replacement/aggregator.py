# app/utils/replacement/aggregator.py
from __future__ import annotations
from typing import Any, Mapping, Sequence, Dict, List, Tuple, Optional
from collections import defaultdict

# === Dependências do domínio ===
from app.utils.anuncios.service import listar_anuncios_pp        # PP de anúncios (SP/MG)
from app.utils.vendas.meli import service as vendas_srv          # Vendas agregadas por MLB
from app.utils.replacement.metrics import estimate_30_60, estoque_pos_delay

# DEFAULT_PARAMS (pesos, lead time etc.) — usa fallback seguro se não existir
try:
    from app.utils.replacement.config import DEFAULT_PARAMS
except Exception:
    class _DP:
        weights = (0.5, 0.3, 0.2)  # w7/w15/w30
        lead_time_days = 7
    DEFAULT_PARAMS = _DP()  # type: ignore


# ============================== Helpers básicos ==============================

def _norm_key(x: Any) -> str:
    """Normaliza qualquer chave textual."""
    return str(x or "").strip()

def _norm_mlb(x: Any) -> str:
    """Normaliza MLB (upper)."""
    s = _norm_key(x)
    return s.upper() if s else s

def _to_num(x: Any, default: float = 0) -> float:
    """Converte valores variados em número (int/float)."""
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x.replace(",", "."))
        except Exception:
            return default
    if isinstance(x, dict):
        # campos comuns
        for k in ("qty", "quantity", "count", "value", "total", "sum", "qtd"):
            if k in x and x[k] is not None:
                return _to_num(x[k], default)
        # mapa de janelas
        for k in (7, "7", "w7", 15, "15", "w15", 30, "30", "w30"):
            if k in x and x[k] is not None:
                return _to_num(x[k], default)
        return default
    if isinstance(x, (list, tuple)) and x:
        return _to_num(x[0], default)
    return default


# ========================= Leitura de janelas (7/15/30) ======================

def _pick_window_from_any(row_like: Mapping, win: int | str) -> float:
    """
    Lê quantidade vendida na janela (7/15/30) aceitando formatos:
    - plano: vendas_7d, vendido_7d, sold_7, w7, qty_7, qtd_7, d7, last7...
    - aninhado: windows/qty/qtd/sold/sum/totals/values (+ aliases acima)
    """
    win = str(win)
    aliases = {
        "7":  ["vendas_7d","vendido_7d","sold_7","qty_7","qtd_7","w7","7","d7","last7"],
        "15": ["vendas_15d","vendido_15d","sold_15","qty_15","qtd_15","w15","15","d15","last15"],
        "30": ["vendas_30d","vendido_30d","sold_30","qty_30","qtd_30","w30","30","d30","last30"],
    }[win]

    # plano
    for k in aliases:
        if k in row_like and row_like[k] is not None and not isinstance(row_like[k], Mapping):
            return _to_num(row_like[k], 0)

    # aninhado
    for nest in ("windows", "qty", "qtd", "sold", "sum", "totals", "values"):
        v = row_like.get(nest)
        if not isinstance(v, Mapping):
            continue
        for k in aliases:
            if k in v and v[k] is not None:
                vv = v[k]
                if isinstance(vv, Mapping):
                    for leaf in ("qty_total", "items_count", "orders_count", "sum", "total", "qty"):
                        if leaf in vv and vv[leaf] is not None:
                            return _to_num(vv[leaf], 0)
                else:
                    return _to_num(vv, 0)
        # alternativo direto "w7"/"w15"/"w30"
        alt = f"w{win}"
        if alt in v and v[alt] is not None:
            return _to_num(v[alt], 0)

    return 0.0

def _sales_triplet(row_like: Mapping | None) -> Dict[str, int]:
    """Extrai vendas 7/15/30 em int (retorna 0 se ausente)."""
    if not isinstance(row_like, Mapping):
        return {"vendas_7d": 0, "vendas_15d": 0, "vendas_30d": 0}
    v7  = _pick_window_from_any(row_like, 7)
    v15 = _pick_window_from_any(row_like, 15)
    v30 = _pick_window_from_any(row_like, 30)
    return {"vendas_7d": int(v7 or 0), "vendas_15d": int(v15 or 0), "vendas_30d": int(v30 or 0)}


# ================== Desembrulho / índice de vendas por MLB ===================

def _unwrap_result(resp: Any) -> Dict[str, dict]:
    """
    Tenta obter {key: row} a partir de múltiplos formatos:
    - {"result": {...}} | {"result": {"per_mlb": {...}}} | {"per_mlb": {...}} | {"data": {...}} | {"payload": {...}}
    - lista de registros com chaves mlb/id/item_id/sku/seller_sku/listing_id
    """
    if isinstance(resp, Mapping):
        for top in ("result", "data", "payload"):
            inner = resp.get(top)
            if isinstance(inner, Mapping):
                for leaf in ("per_mlb", "per_gtin"):
                    dd = inner.get(leaf)
                    if isinstance(dd, Mapping):
                        return { _norm_key(k): (dict(v) if isinstance(v, Mapping) else {"value": v}) for k, v in dd.items() }
                return { _norm_key(k): (dict(v) if isinstance(v, Mapping) else {"value": v}) for k, v in inner.items() }
        for leaf in ("per_mlb", "per_gtin"):
            dd = resp.get(leaf)
            if isinstance(dd, Mapping):
                return { _norm_key(k): (dict(v) if isinstance(v, Mapping) else {"value": v}) for k, v in dd.items() }
        return { _norm_key(k): (dict(v) if isinstance(v, Mapping) else {"value": v}) for k, v in resp.items() }

    if isinstance(resp, Sequence) and not isinstance(resp, (str, bytes)):
        out: Dict[str, dict] = {}
        for item in resp:
            if not isinstance(item, Mapping):
                continue
            key = (
                item.get("mlb") or item.get("id") or item.get("item_id") or
                item.get("sku") or item.get("seller_sku") or item.get("listing_id") or ""
            )
            k = _norm_key(key)
            if k:
                out[k] = dict(item)
        return out

    return {}


def _build_vendas_index_robusto(loja: str) -> Dict[str, dict]:
    """
    Retorna {MLB: registro_vendas}, casando por múltiplas chaves:
    - vendas indexadas por mlb/id/item_id | sku/seller_sku/listing_id
    - anúncios PP fornecem o dicionário de correspondência MLB -> {mlb, sku, seller_sku, listing_id}
    """
    # 1) vendas bruto
    try:
        raw = vendas_srv.get_por_mlb(loja, windows=(7, 15, 30), mode="qty")
    except Exception:
        raw = vendas_srv.get_por_mlb(loja)

    vendas_map = _unwrap_result(raw)  # pode estar por mlb OU sku/etc.

    # 2) index por todas as chaves possíveis
    by_any: Dict[str, dict] = {}
    for k, rec in vendas_map.items():
        kk = _norm_key(k).upper()
        by_any[kk] = rec
        if isinstance(rec, Mapping):
            for alt in ("mlb", "id", "item_id", "sku", "seller_sku", "listing_id"):
                if alt in rec and rec[alt] is not None:
                    by_any[_norm_key(rec[alt]).upper()] = rec

    # 3) anuncios PP → dicionário de correspondência por MLB
    ads = listar_anuncios_pp(regiao=loja) or []
    cross: Dict[str, Tuple[str, ...]] = {}  # MLB -> possíveis chaves de vendas
    for a in ads:
        mlb = _norm_mlb(a.get("mlb") or a.get("id"))
        if not mlb:
            continue
        candidates = {
            mlb,
            _norm_key(a.get("sku")).upper(),
            _norm_key(a.get("seller_sku")).upper(),
            _norm_key(a.get("listing_id")).upper(),
        }
        cross[mlb] = tuple(c for c in candidates if c)

    # 4) monta índice final por MLB
    out: Dict[str, dict] = {}
    for mlb, cand_keys in cross.items():
        rec = None
        for k in cand_keys:
            rec = by_any.get(k)
            if rec:
                break
        rec = rec or by_any.get(mlb)
        if rec:
            out[mlb] = rec
    return out


# =========================== Mapa MLB → GTIN / título ========================

def _map_mlb_to_gtin_title(loja: str) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, float]]:
    """
    Constrói:
      - gtin_by_mlb: {MLB: GTIN}
      - title_by_mlb: {MLB: title}
      - estoque_by_mlb: {MLB: estoque_total_na_regiao}
    a partir do PP de anúncios da região.
    """
    gtin_by_mlb: Dict[str, str] = {}
    title_by_mlb: Dict[str, str] = {}
    estoque_by_mlb: Dict[str, float] = defaultdict(float)

    for ad in listar_anuncios_pp(regiao=loja) or []:
        mlb = _norm_mlb(ad.get("mlb") or ad.get("id"))
        if not mlb:
            continue
        gt = _norm_key(ad.get("gtin") or ad.get("ean") or ad.get("barcode"))
        if gt:
            gtin_by_mlb[mlb] = gt
        title = ad.get("title") or ad.get("name") or ""
        if title:
            title_by_mlb[mlb] = title
        est_raw = ad.get("estoque", ad.get("available_quantity", 0))
        try:
            estoque_by_mlb[mlb] += float(est_raw or 0)
        except Exception:
            pass

    return gtin_by_mlb, title_by_mlb, dict(estoque_by_mlb)


# ======================= Linha final (estima/estoque/etc.) ====================

def _compose_row(mlb: str, base: dict, vendas_rec: Optional[dict],
                 gtin_by_mlb: Dict[str, str],
                 title_by_mlb: Dict[str, str],
                 estoque_by_mlb: Dict[str, float]) -> dict:
    """
    Monta uma linha enriquecida por MLB com:
      mlb, title, gtin, vendas_7/15/30, taxa_diaria, estimado_30/60,
      consumo_previsto_7d_lead, estoque_atual, estoque_pos_delay_7, replacement_30/60 (quando houver).
    """
    row: dict = dict(base or {})
    row["mlb"] = mlb
    row["title"] = row.get("title") or title_by_mlb.get(mlb) or ""
    row["gtin"] = row.get("gtin") or gtin_by_mlb.get(mlb)

    # vendas
    sales = _sales_triplet(vendas_rec)
    row.update(sales)

    # estimativas a partir das vendas (padrão do domínio)
    est = estimate_30_60(sales["vendas_7d"], sales["vendas_15d"], sales["vendas_30d"], DEFAULT_PARAMS.weights)
    row.update(est)

    # consumo previsto durante lead time (ex.: 7 dias)
    row["consumo_previsto_7d_lead"] = est["taxa_diaria"] * DEFAULT_PARAMS.lead_time_days

    # estoque atual por MLB (somado na região)
    estoque_atual = estoque_by_mlb.get(mlb)
    row["estoque_atual"] = estoque_atual

    # estoque após delay (lead time)
    row["estoque_pos_delay_7"] = estoque_pos_delay(estoque_atual, est["taxa_diaria"], DEFAULT_PARAMS.lead_time_days)

    # se já existirem replacement_30/60 no base, preserva; caso contrário ficam implícitos por estimado_30/60
    # (não forçamos aqui para manter separação semântica)
    return row


# =============================== Funções públicas =============================

def montar_anuncios_por_mlb_enriquecido(regiao: str) -> List[Dict[str, Any]]:
    """
    Enriquece dados por MLB na região informada (sp|mg):
      - Join robusto entre VENDAS (por MLB) e ANÚNCIOS (PP) por múltiplas chaves
      - Injeta GTIN/title/estoque
      - Calcula vendas 7/15/30, taxa_diaria, estimado_30/60, consumo_previsto_7d_lead, estoque_pos_delay_7
    Retorna lista ordenada de linhas (determinística).
    """
    loja = (_norm_key(regiao) or "").lower()
    if loja not in ("sp", "mg"):
        raise ValueError("regiao inválida: use 'sp' ou 'mg'.")

    # mapas a partir do PP de anúncios
    gtin_by_mlb, title_by_mlb, estoque_by_mlb = _map_mlb_to_gtin_title(loja)

    # índice de vendas robusto (casando mlb/id/item_id/sku/seller_sku/listing_id)
    vendas_index = _build_vendas_index_robusto(loja)

    # universo de MLBs = o que existe no PP de anúncios (garante consistência)
    mlbs = sorted(gtin_by_mlb.keys() | title_by_mlb.keys() | estoque_by_mlb.keys())

    out: List[Dict[str, Any]] = []
    for mlb in mlbs:
        rec_v = vendas_index.get(mlb)
        linha = _compose_row(mlb, {}, rec_v, gtin_by_mlb, title_by_mlb, estoque_by_mlb)
        linha["regiao"] = loja
        out.append(linha)

    # ordenação determinística (por estimado_30 desc, title asc, mlb asc)
    out.sort(key=lambda r: (-float(r.get("estimado_30") or 0), r.get("title") or "", r.get("mlb") or ""))

    return out

def carregar_por_mlb_regiao(regiao: str) -> dict[str, dict]:
    """
    BACKCOMPAT:
      Antes: esta função existia e era importada pela page/service.
      Agora: delegamos para `montar_anuncios_por_mlb_enriquecido(regiao)` e
      retornamos no formato {mlb: row} para não quebrar quem esperava dict.
    """
    rows = montar_anuncios_por_mlb_enriquecido(regiao)
    return {str(r.get("mlb") or "").upper(): r for r in rows}

__all__ = [
    "montar_anuncios_por_mlb_enriquecido",
    "carregar_por_mlb_regiao",  # backcompat
]

