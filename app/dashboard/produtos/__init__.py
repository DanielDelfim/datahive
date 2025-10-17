# app/dashboard/produtos/__init__.py
from __future__ import annotations
from typing import Any

def render_dashboard_produtos(ctx: Any) -> None:
    # Import tardio para evitar ciclo
    from . import compositor
    compositor.render(ctx)
