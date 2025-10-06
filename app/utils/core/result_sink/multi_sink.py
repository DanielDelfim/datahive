from __future__ import annotations
from typing import Iterable, Any, Optional

class MultiSink:
    """Despacha o mesmo payload para N sinks filhos."""

    def __init__(self, *, children: Iterable):
        self.children = list(children)

    # API legado
    def emit(self, result: dict, *, name: Optional[str] = None) -> None:
        for s in self.children:
            if hasattr(s, "emit"):
                s.emit(result, name=name)
            else:
                s.write(result, dry_run=False, debug=False)

    # API atual
    def write(self, payload: Any, *, dry_run: bool = False, debug: bool = False):
        for s in self.children:
            if hasattr(s, "write"):
                s.write(payload, dry_run=dry_run, debug=debug)
            else:
                s.emit(payload, name=None)
