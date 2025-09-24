from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.config.paths import Regiao
from .service import listar_anuncios_meli


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def gerar_pp_basico(regiao: Optional[Regiao] = None) -> Dict[str, object]:
    """
    Gera payload PP básico (somente anúncios) para o canal ML.
    Não escreve em disco. Útil para pages/tests.
    - Se regiao=None: concatena SP+MG (se existirem).
    - Se regiao=Regiao.SP/MG: só aquela região.
    """
    if regiao is None:
        itens: List[Dict] = []
        for r in Regiao:
            if r.value.lower() in {"sp", "mg"}:
                itens.extend(listar_anuncios_meli(regiao=r))
        rotulo = "all"
    else:
        itens = listar_anuncios_meli(regiao=regiao)
        rotulo = regiao.value

    payload = {
        "canal": "meli",
        "versao": 1,
        "gerado_em": _iso_now(),
        "regiao": rotulo,
        "total_itens": len(itens),
        "itens": itens,
    }
    return payload
