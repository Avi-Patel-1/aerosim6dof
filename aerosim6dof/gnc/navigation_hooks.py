"""Navigation hooks."""

from __future__ import annotations

from typing import Any

import numpy as np


class NavigationHook:
    def __init__(self, mode: str = "truth"):
        self.mode = mode
        self._position_m: np.ndarray | None = None
        self._velocity_mps: np.ndarray | None = None
        self._last_sensor_time_s: float | None = None

    def estimate(self, state: Any, sensor_values: dict[str, float] | None = None) -> dict[str, Any]:
        if self.mode == "noisy_sensors" and sensor_values:
            return self._sensor_bridge(state, sensor_values)
        return {"position_m": state.position_m.copy(), "velocity_mps": state.velocity_mps.copy()}

    def _sensor_bridge(self, state: Any, sensor_values: dict[str, float]) -> dict[str, Any]:
        sensor_time = _finite(sensor_values.get("sensor_time_s"))
        if self._position_m is None:
            self._position_m = state.position_m.copy()
            self._velocity_mps = state.velocity_mps.copy()
        if sensor_time is not None and self._last_sensor_time_s is not None and self._velocity_mps is not None:
            dt = max(0.0, min(1.0, sensor_time - self._last_sensor_time_s))
            self._position_m = self._position_m + self._velocity_mps * dt
        gps_valid = _finite(sensor_values.get("gps_valid"))
        if gps_valid is not None and gps_valid > 0.5:
            self._position_m = np.array(
                [
                    sensor_values.get("gps_x_m", self._position_m[0]),
                    sensor_values.get("gps_y_m", self._position_m[1]),
                    sensor_values.get("gps_z_m", self._position_m[2]),
                ],
                dtype=float,
            )
            self._velocity_mps = np.array(
                [
                    sensor_values.get("gps_vx_mps", state.velocity_mps[0]),
                    sensor_values.get("gps_vy_mps", state.velocity_mps[1]),
                    sensor_values.get("gps_vz_mps", state.velocity_mps[2]),
                ],
                dtype=float,
            )
            quality = "gps"
        else:
            quality = "dead_reckoned"
            baro_valid = _finite(sensor_values.get("baro_valid"))
            if baro_valid is not None and baro_valid > 0.5 and "baro_alt_m" in sensor_values:
                self._position_m[2] = float(sensor_values["baro_alt_m"])
                quality = "baro_dead_reckoned"
            radar_valid = _finite(sensor_values.get("radar_valid"))
            if radar_valid is not None and radar_valid > 0.5 and "radar_agl_m" in sensor_values:
                self._position_m[2] = float(sensor_values["radar_agl_m"])
                quality = "radar_dead_reckoned"
        if sensor_time is not None:
            self._last_sensor_time_s = sensor_time
        return {"position_m": self._position_m.copy(), "velocity_mps": self._velocity_mps.copy(), "navigation_quality": quality}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None
