"""Availability and dropout quality summaries."""

from __future__ import annotations

import math
from typing import Any


def availability_summary(
    rows: list[dict[str, Any]],
    *,
    available_key: str,
    quality_key: str | None = None,
    time_key: str = "time_s",
) -> dict[str, Any]:
    """Summarize binary availability and optional quality score columns."""

    availability: list[tuple[float | None, bool]] = []
    for row in rows:
        value = _finite_or_none(row.get(available_key))
        if value is None:
            continue
        availability.append((_finite_or_none(row.get(time_key)), value > 0.5))
    quality_values = []
    if quality_key is not None:
        quality_values = [_finite_or_none(row.get(quality_key)) for row in rows]
        quality_values = [value for value in quality_values if value is not None]
    if not availability:
        return {
            "present": False,
            "valid_fraction": None,
            "dropout_events": None,
            "longest_dropout_s": None,
            "current_available": None,
            "quality_current": None,
            "quality_mean": None,
            "quality_min": None,
            "quality_max": None,
        }
    available_values = [available for _, available in availability]
    return {
        "present": True,
        "valid_fraction": sum(1 for value in available_values if value) / len(available_values) if available_values else None,
        "dropout_events": _transition_count(available_values) if available_values else None,
        "longest_dropout_s": _longest_false_duration(availability),
        "current_available": available_values[-1] if available_values else None,
        "quality_current": quality_values[-1] if quality_values else None,
        "quality_mean": sum(quality_values) / len(quality_values) if quality_values else None,
        "quality_min": min(quality_values) if quality_values else None,
        "quality_max": max(quality_values) if quality_values else None,
    }


def _transition_count(values: list[bool]) -> int:
    if not values:
        return 0
    return sum(1 for previous, current in zip(values, values[1:]) if previous != current)


def _longest_false_duration(values: list[tuple[float | None, bool]]) -> float | None:
    timed = [(time_s, available) for time_s, available in values if time_s is not None]
    if not timed:
        return None
    longest = 0.0
    dropout_start: float | None = None
    last_time = timed[0][0]
    for time_s, available in timed:
        if not available and dropout_start is None:
            dropout_start = time_s
        elif available and dropout_start is not None:
            longest = max(longest, time_s - dropout_start)
            dropout_start = None
        last_time = time_s
    if dropout_start is not None:
        longest = max(longest, last_time - dropout_start)
    return float(longest)


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
