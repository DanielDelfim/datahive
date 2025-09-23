# app/utils/core/result_sink/stdout_sink.py
from __future__ import annotations

import json
import sys
from typing import Optional


class StdoutSink:
    """Sink que imprime o resultado em tela (legível)."""

    def emit(self, result: dict, *, name: Optional[str] = None) -> None:
        if name:
            sys.stdout.write(f"\n=== Resultado: {name} ===\n")
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        sys.stdout.flush()
