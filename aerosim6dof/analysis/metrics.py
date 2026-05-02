"""Run summary metrics."""

from __future__ import annotations

from typing import Any

import numpy as np


def summarize(rows: list[dict[str, Any]], events: list[dict[str, Any]], scenario_name: str) -> dict[str, Any]:
    final = rows[-1]
    miss = final.get("target_distance_m")
    miss_value = float(miss) if isinstance(miss, (float, int)) and np.isfinite(miss) else None
    min_target_range = _finite_min([r.get("target_range_m") for r in rows])
    min_target_distance = min_target_range
    if min_target_distance is None:
        min_target_distance = miss_value if miss_value is not None else _finite_min([r.get("target_distance_m") for r in rows])
    return {
        "scenario": scenario_name,
        "samples": len(rows),
        "duration_s": float(final["time_s"]),
        "final": {
            "time_s": float(final["time_s"]),
            "x_m": float(final["x_m"]),
            "y_m": float(final["y_m"]),
            "altitude_m": float(final["altitude_m"]),
            "altitude_agl_m": _finite_float(final.get("altitude_agl_m")),
            "terrain_elevation_m": _finite_float(final.get("terrain_elevation_m")),
            "ground_contact_state": final.get("ground_contact_state"),
            "ground_contact_severity": _finite_float(final.get("ground_contact_severity")),
            "speed_mps": float(final["speed_mps"]),
            "mass_kg": float(final["mass_kg"]),
            "target_id": final.get("target_id"),
            "target_range_m": _finite_float(final.get("target_range_m")),
            "closing_speed_mps": _finite_float(final.get("closing_speed_mps")),
        },
        "max_altitude_m": max(float(r["altitude_m"]) for r in rows),
        "min_altitude_agl_m": _finite_min([r.get("altitude_agl_m") for r in rows]),
        "min_altitude_agl_rate_mps": _finite_min([r.get("altitude_agl_rate_mps") for r in rows]),
        "max_impact_speed_mps": _finite_max([r.get("impact_speed_mps") for r in rows]),
        "ground_contact_count": sum(1 for r in rows if _finite_float(r.get("ground_contact")) == 1.0),
        "max_speed_mps": max(float(r["speed_mps"]) for r in rows),
        "max_load_factor_g": max(float(r["load_factor_g"]) for r in rows),
        "max_qbar_pa": max(float(r["qbar_pa"]) for r in rows),
        "min_target_distance_m": min_target_distance,
        "min_target_range_m": min_target_range,
        "max_closing_speed_mps": _finite_max([r.get("closing_speed_mps") for r in rows]),
        "event_count": len(events),
    }


def _finite_min(values: list[Any]) -> float | None:
    finite = [float(v) for v in values if isinstance(v, (int, float)) and np.isfinite(v)]
    return min(finite) if finite else None


def _finite_max(values: list[Any]) -> float | None:
    finite = [float(v) for v in values if isinstance(v, (int, float)) and np.isfinite(v)]
    return max(finite) if finite else None


def _finite_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and np.isfinite(value) else None
