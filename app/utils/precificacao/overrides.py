from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict

from .config import get_overrides_ml  # você criará este loader no config.py


@dataclass
class OverrideAplicado:
    origem: str        # "mlb" | "sku" | "gtin" | "cenario"
    campanha_id: str | None
    knobs: Dict[str, Any]


def _hoje() -> date:
    return datetime.now().date()


def _ativo(vig: Dict[str, Any], hoje: date) -> bool:
    if not isinstance(vig, dict):
        return True
    v_from = vig.get("from")
    v_to = vig.get("to")
    try:
        if v_from and hoje < date.fromisoformat(str(v_from)):
            return False
        if v_to and hoje > date.fromisoformat(str(v_to)):
            return False
    except Exception:
        return True
    return True


def resolver_override(mlb: str | None, sku: str | None, gtin: str | None,
                      cenario: str | None = None,
                      hoje: date | None = None) -> OverrideAplicado | None:
    """
    Consulta overrides.yaml e retorna o primeiro override aplicável por prioridade:
      mlb > sku > gtin > cenario. Retorna None se nada se aplica.
    """
    rules = get_overrides_ml()
    hoje = hoje or _hoje()

    # 1) por_item (prioridade)
    por_item = rules.get("por_item", {})
    for key, origem in ((mlb, "mlb"), (sku, "sku"), (gtin, "gtin")):
        if not key:
            continue
        data = por_item.get(str(key))
        if isinstance(data, dict) and _ativo(data.get("vigencia", {}), hoje):
            knobs = {k: v for k, v in data.items() if k.endswith("_override")}
            return OverrideAplicado(origem=origem, campanha_id=data.get("campanha_id"), knobs=knobs)

    # 2) cenario
    if cenario:
        cen = rules.get("cenarios", {}).get(str(cenario), {})
        knobs = {k: v for k, v in cen.items() if k.endswith("_override")}
        if knobs:
            return OverrideAplicado(origem="cenario", campanha_id=str(cenario), knobs=knobs)

    return None
