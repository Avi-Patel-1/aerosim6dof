"""Failure helpers."""

from __future__ import annotations

from typing import Any


def active_failure(config: dict[str, Any] | None, t: float) -> dict[str, Any]:
    cfg = config or {}
    start = float(cfg.get("start_s", 0.0))
    end = float(cfg.get("end_s", 1e99))
    return cfg if start <= t <= end else {}

