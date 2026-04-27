"""Run summary metrics."""

from __future__ import annotations

from typing import Any

import numpy as np


def summarize(rows: list[dict[str, Any]], events: list[dict[str, Any]], scenario_name: str) -> dict[str, Any]:
    final = rows[-1]
    miss = final.get("target_distance_m")
    miss_value = float(miss) if isinstance(miss, (float, int)) and np.isfinite(miss) else None
    return {
        "scenario": scenario_name,
        "samples": len(rows),
        "duration_s": float(final["time_s"]),
        "final": {
            "time_s": float(final["time_s"]),
            "x_m": float(final["x_m"]),
            "y_m": float(final["y_m"]),
            "altitude_m": float(final["altitude_m"]),
            "speed_mps": float(final["speed_mps"]),
            "mass_kg": float(final["mass_kg"]),
        },
        "max_altitude_m": max(float(r["altitude_m"]) for r in rows),
        "max_speed_mps": max(float(r["speed_mps"]) for r in rows),
        "max_load_factor_g": max(float(r["load_factor_g"]) for r in rows),
        "max_qbar_pa": max(float(r["qbar_pa"]) for r in rows),
        "min_target_distance_m": miss_value
        if miss_value is not None
        else _finite_min([r.get("target_distance_m") for r in rows]),
        "event_count": len(events),
    }


def _finite_min(values: list[Any]) -> float | None:
    finite = [float(v) for v in values if isinstance(v, (int, float)) and np.isfinite(v)]
    return min(finite) if finite else None

