
from __future__ import annotations

from typing import Any, Dict, List, Optional
import math

# ---------------- Utils numéricos/lookup (puros) ----------------

def _to_num(v) -> Optional[float]:
    try:
        if v is None or isinstance(v, bool):
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None

def _pct(v) -> float:
    try:
        if v is None:
            return 0.0
        x = float(v)
        return x if math.isfinite(x) else 0.0
    except Exception:
        return 0.0

def _dig(node: Any, *path: str) -> Any:
    cur = node
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur

def _is_full_logistic(logistic_type: str | None) -> bool:
    lt = (logistic_type or "").lower()
    return lt.startswith("fulfillment")


# ---------------- API pública (pura) ----------------

def comissao_pct_for(logistic_type: str | None, regras: Dict[str, Any]) -> float:
    """
    Percentual de comissão (0..1). Fallback para comissao.classico_pct.
    """
    default = (regras or {}).get("default", {}) or {}
    cfg = (regras or {}).get("comissao", {}) or {}

    if _is_full_logistic(logistic_type):
        cand = (
            cfg.get("full")
            or cfg.get("fulfillment")
            or cfg.get("classico_pct")
            or default.get("comissao_pct")
        )
    else:
        cand = (
            cfg.get("seller")
            or cfg.get("classico_pct")
            or default.get("comissao_pct")
        )
    return _pct(cand)


def calcular_comissao(preco: float | None, logistic_type: str | None, regras: Dict[str, Any]) -> Optional[float]:
    p = _to_num(preco)
    if p is None or p <= 0:
        return None
    return p * comissao_pct_for(logistic_type, regras)


def _pick_faixa_por_preco(p: float, faixas: List[dict]) -> Optional[dict]:
    """
    Seleciona a primeira faixa onde p <= max_preco. Mantém uma faixa 'otherwise' se houver.
    """
    otherwise = None
    for t in (faixas or []):
        if t.get("otherwise"):
            otherwise = t
            continue
        max_preco = _to_num(t.get("max_preco") or t.get("max") or t.get("limite") or t.get("to") or t.get("upper"))
        if max_preco is None:
            continue
        if p <= max_preco:
            return t
    return otherwise


def custo_fixo_full(preco: float | None, regras: Dict[str, Any]) -> float:
    """
    Custo fixo para FULL por unidade, a partir de faixas de preço declaradas em:
      full.custo_fixo_por_unidade_brl: 
        - { max_preco: 19.99, valor: 1.00 }
        - { max_preco: 39.99, valor: 2.00 }
        - { otherwise: true, valor: 0.0 }
    Também aceita 'valor_pct_do_preco' como percentual do preço.
    """
    p = _to_num(preco)
    if p is None or p <= 0:
        return 0.0

    lst = _dig(regras, "full", "custo_fixo_por_unidade_brl")
    if isinstance(lst, list) and lst:
        faixa = _pick_faixa_por_preco(p, lst)
        if faixa:
            # percentual tem precedência se existir explicitamente
            if faixa.get("valor_pct_do_preco") is not None:
                return float(p * _pct(faixa.get("valor_pct_do_preco")))
            v = _to_num(faixa.get("valor") or faixa.get("value") or faixa.get("amount"))
            if v is not None:
                return float(v)
        # Se não achou faixa válida, 0.0 é um fallback seguro
        return 0.0

    # Fallback: se o YAML não tiver o bloco esperado, retorna 0.0 (evita valores errados)
    return 0.0
