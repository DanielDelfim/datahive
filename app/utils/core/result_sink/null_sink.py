from __future__ import annotations
from typing import Any, Optional

class NullSink:
    """Descarta a saída (útil para dry-run global ou pipelines sem gravação)."""

    # API legado
    def emit(self, result: dict, *, name: Optional[str] = None) -> None:
        return

    # API atual
    def write(self, payload: Any, *, dry_run: bool = False, debug: bool = False):
        return
