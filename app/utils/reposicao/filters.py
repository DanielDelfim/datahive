# app/utils/reposicao/filters.py
from __future__ import annotations
from pathlib import Path
import re
from typing import Dict, Any, Iterable, List, Optional
import json

def _load_payload(src: Dict[str, Any] | str | Path) -> Dict[str, Any]:
    if isinstance(src, dict):
        return src
    p = Path(src)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def _normalize_lojas(lojas: Optional[Iterable[str]]) -> Optional[List[str]]:
    if lojas is None:
        return None
    return [str(loja_item).strip().lower() for loja_item in lojas if str(loja_item).strip()]

def _normalize_mlbs(mlbs: Optional[Iterable[str]]) -> Optional[List[str]]:
    if mlbs is None:
        return None
    return [str(m).strip() for m in mlbs if str(m).strip()]

_RE_NUM = re.compile(r"\d+")

def _only_digits(s: str) -> str:
    """Mantém apenas dígitos (útil para comparar GTIN/EAN com ou sem hífens/sufixos)."""
    return "".join(_RE_NUM.findall(str(s)))

def only_digits(s: str) -> str:
    """
    Público: mantém apenas dígitos de uma string.
    Use em chaves de junção (GTIN/EAN), evitando divergências como '7908812400175-50'.
    Ex.: only_digits('7908812400175-50') -> '7908812400175'
    """
    return _only_digits(s)

    return _only_digits(s)

def _normalize_gtins(gtins: Optional[Iterable[str]]) -> Optional[List[str]]:
    """
    Normaliza GTINs: strip + mantém apenas dígitos.
    Ex.: '7908812400175-50' -> '7908812400175'
    """
    if gtins is None:
        return None
    out: List[str] = []
    for g in gtins:
        s = str(g).strip()
        if not s:
            continue
        only = _only_digits(s)
        if only:
            out.append(only)
    return out or None

def filtrar_payload(
    payload_or_path: Dict[str, Any] | str | Path,
    lojas: Optional[Iterable[str]] = None,
    mlbs: Optional[Iterable[str]] = None,
    gtins: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Filtra um payload no formato:
    {
      "results": { "sp": { "MLBxxx": {...}, ... }, "mg": {...} },
      ...
    }
    1º por loja (sp/mg), depois por MLB.
    """
    payload = _load_payload(payload_or_path)
    results = payload.get("results", {})
    if not isinstance(results, dict):
        return {"results": {}}

    lojas_norm = _normalize_lojas(lojas)
    mlbs_norm = _normalize_mlbs(mlbs)
    gtins_norm = _normalize_gtins(gtins)

    out: Dict[str, Any] = {"results": {}}
    for loja, mapa in results.items():
        loja_key = str(loja).lower()
        if lojas_norm is not None and loja_key not in lojas_norm:
            continue
        if not isinstance(mapa, dict):
            continue

        # 1) filtro por MLB (se houver)
        recs = (
            {mlb: rec for mlb, rec in mapa.items() if mlb in mlbs_norm}
            if mlbs_norm is not None else dict(mapa)
        )

        # 2) filtro por GTIN (se houver) — compara usando dígitos apenas
        if gtins_norm is not None:
            filtered: Dict[str, Any] = {}
            for mlb, rec in recs.items():
                if not isinstance(rec, dict):
                    continue
                gt = rec.get("gtin")
                if gt is None:
                    continue
                if _only_digits(str(gt)) in gtins_norm:
                    filtered[mlb] = rec
            recs = filtered

        out["results"][loja_key] = recs

    # mantém metadados úteis
    for k in ("generated_at", "windows", "lojas"):
        if k in payload:
            out[k] = payload[k]
    return out

def flatten_filtrado(
    payload_or_path: Dict[str, Any] | str | Path,
    lojas: Optional[Iterable[str]] = None,
    mlbs: Optional[Iterable[str]] = None,
    gtins: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna lista de linhas (dict) flatten para exportação/relatórios.
    Cada linha contém: loja, mlb e campos calculados.
    """
    filtered = filtrar_payload(payload_or_path, lojas=lojas, mlbs=mlbs, gtins=gtins)
    rows: List[Dict[str, Any]] = []
    results = filtered.get("results", {})
    for loja, mapa in results.items():
        if not isinstance(mapa, dict):
            continue
        for mlb, rec in mapa.items():
            if not isinstance(rec, dict):
                continue
            row = {
                "loja": loja,
                "mlb": mlb,
                "gtin": rec.get("gtin"),
                # Vendas brutas por janela
                "sold_7": rec.get("sold_7"),
                "sold_15": rec.get("sold_15"),
                "sold_30": rec.get("sold_30"),
                # Médias diárias
                "media_diaria_7": rec.get("media_diaria_7"),
                "media_diaria_15": rec.get("media_diaria_15"),
                "media_diaria_30": rec.get("media_diaria_30"),
                "media_diaria_preferida": rec.get("media_diaria_preferida"),
                "media_diaria_ponderada": rec.get("media_diaria_ponderada"),
                # Projeções
                "expectativa_30d": rec.get("expectativa_30d"),
                "expectativa_60d": rec.get("expectativa_60d"),
                "consumo_previsto_7d": rec.get("consumo_previsto_7d"),
                # Reposição
                "reposicao_necessaria_7d": rec.get("reposicao_necessaria_7d"),
                "reposicao_necessaria_30d": rec.get("reposicao_necessaria_30d"),
                "reposicao_necessaria_60d": rec.get("reposicao_necessaria_60d"),
                # Estoque e cobertura
                "estoque_projetado_7d": rec.get("estoque_projetado_7d"),
                "estoque": rec.get("estoque"),
                "dias_cobertura": rec.get("dias_cobertura"),
            }
            rows.append(row)
    return rows
