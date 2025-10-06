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

    # compat: usado por build_sink(...).write(...)
    def write(self, payload, *, dry_run: bool = False, debug: bool = False):
        if dry_run and debug:
            print("[DRY-RUN] StdoutSink.write")
            return
        self.emit(payload, name=None)
