#C:\Apps\Datahive\app\utils\replacement\config.py
from __future__ import annotations
from dataclasses import dataclass

# Versões dos contratos (atualize quando mudar shape)
SCHEMA_VERSION = "1.0.0"
MODULE_VERSION = "1.0.0"

# Parâmetros de negócio padrão do domínio
WEIGHTS_7_15_30 = (0.45, 0.35, 0.20)
LEAD_TIME_DAYS = 7  # delay logístico considerado nas projeções

@dataclass(frozen=True)
class ReplacementParams:
    weights: tuple[float, float, float] = WEIGHTS_7_15_30
    lead_time_days: int = LEAD_TIME_DAYS

DEFAULT_PARAMS = ReplacementParams()
