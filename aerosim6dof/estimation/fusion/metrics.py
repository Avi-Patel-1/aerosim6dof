"""Metric summarization for estimation fusion reports."""

from __future__ import annotations

import math
from typing import Any


def summarize_numeric_rows(rows: list[dict[str, Any]], *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    """Summarize each finite numeric column with current/min/max/RMSE."""

    excluded = set(exclude or set()) | {"time_s"}
    keys: list[str] = []
    for row in rows:
        for key, value in row.items():
            if key in excluded or key in keys:
                continue
            if _finite_or_none(value) is not None:
                keys.append(key)
    metrics: list[dict[str, Any]] = []
    for key in keys:
        summary = summarize_series(key, [row.get(key) for row in rows])
        if summary is not None:
            metrics.append(summary)
    return metrics


def summarize_series(metric: str, values: list[Any]) -> dict[str, Any] | None:
    """Return a stable metric row for a value series."""

    finite = [_finite_or_none(value) for value in values]
    finite_values = [value for value in finite if value is not None]
    if not finite_values:
        return None
    return {
        "metric": metric,
        "kind": _kind(metric),
        "stream": _stream(metric),
        "channel": _channel(metric),
        "unit": _unit(metric),
        "samples": len(finite_values),
        "current": finite_values[-1],
        "min": min(finite_values),
        "max": max(finite_values),
        "mean": sum(finite_values) / len(finite_values),
        "rmse": math.sqrt(sum(value * value for value in finite_values) / len(finite_values)),
        "abs_max": max(abs(value) for value in finite_values),
    }


def metrics_by_name(metric_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Convert metric rows to a JSON-friendly dictionary."""

    return {str(row["metric"]): {key: value for key, value in row.items() if key != "metric"} for row in metric_rows}


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _kind(metric: str) -> str:
    if "residual" in metric or "error" in metric:
        return "residual"
    if "quality" in metric or "available" in metric or "used" in metric or "valid" in metric:
        return "quality"
    if metric.endswith("_time_delta_s"):
        return "alignment"
    return "stream"


def _stream(metric: str) -> str:
    for prefix in ("truth_", "sensor_", "estimate_", "gnss_", "baro_", "pitot_", "radar_", "imu_", "gyro_"):
        if metric.startswith(prefix):
            return prefix[:-1]
    return "fusion"


def _channel(metric: str) -> str:
    cleaned = metric
    for prefix in ("truth_", "sensor_", "estimate_"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    for suffix in ("_residual_mps2", "_residual_mps", "_residual_rps", "_residual_deg", "_residual_m", "_error_mps", "_error_m"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return cleaned


def _unit(metric: str) -> str:
    if metric.endswith("_mps2"):
        return "m/s^2"
    if metric.endswith("_mps"):
        return "m/s"
    if metric.endswith("_rps"):
        return "rad/s"
    if metric.endswith("_dps"):
        return "deg/s"
    if metric.endswith("_deg"):
        return "deg"
    if metric.endswith("_m2"):
        return "m^2"
    if metric.endswith("_m"):
        return "m"
    if metric.endswith("_s"):
        return "s"
    return ""
