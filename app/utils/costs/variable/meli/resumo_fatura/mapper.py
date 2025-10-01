from __future__ import annotations

def norm_str(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(str(s).strip().split())

def is_prefix(s: str | None, prefix: str) -> bool:
    return norm_str(s).startswith(prefix)
