"""Identifier-shape helpers. No project-specific logic."""
from __future__ import annotations

import re

_CAMEL_RE1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_RE2 = re.compile(r"([a-z0-9])([A-Z])")


def camel_to_snake(name: str) -> str:
    if not name or name.isupper():
        return name
    return _CAMEL_RE2.sub(r"\1_\2", _CAMEL_RE1.sub(r"\1_\2", name)).lower()
