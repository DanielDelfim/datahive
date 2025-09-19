# app/utils/reposicao/filters.py
from __future__ import annotations
from pathlib import Path
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

def filtrar_payload(
    payload_or_path: Dict[str, Any] | str | Path,
    lojas: Optional[Iterable[str]] = None,
    mlbs: Optional[Iterable[str]] = None,
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

    out: Dict[str, Any] = {"results": {}}
    for loja, mapa in results.items():
        loja_key = str(loja).lower()
        if lojas_norm is not None and loja_key not in lojas_norm:
            continue
        if not isinstance(mapa, dict):
            continue

        if mlbs_norm is None:
            out["results"][loja_key] = mapa
        else:
            rec_mlb = {mlb: rec for mlb, rec in mapa.items() if mlb in mlbs_norm}
            out["results"][loja_key] = rec_mlb

    # mantém metadados úteis
    for k in ("generated_at", "windows", "lojas"):
        if k in payload:
            out[k] = payload[k]
    return out

def flatten_filtrado(
    payload_or_path: Dict[str, Any] | str | Path,
    lojas: Optional[Iterable[str]] = None,
    mlbs: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna lista de linhas (dict) flatten para exportação/relatórios.
    Cada linha contém: loja, mlb e campos calculados.
    """
    filtered = filtrar_payload(payload_or_path, lojas=lojas, mlbs=mlbs)
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
