"""JSON configuration loading and merging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{p}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{p}: top-level JSON value must be an object")
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_with_optional_base(path: str | Path, key: str = "extends") -> dict[str, Any]:
    p = Path(path)
    data = load_json(p)
    if key not in data:
        return data
    base_path = Path(data[key])
    if not base_path.is_absolute():
        base_path = p.parent / base_path
    base = load_with_optional_base(base_path, key)
    child = dict(data)
    child.pop(key, None)
    return deep_merge(base, child)

