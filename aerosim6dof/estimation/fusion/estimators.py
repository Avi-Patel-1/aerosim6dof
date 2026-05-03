"""Small fusion estimators for post-run analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from aerosim6dof.estimation.navigation_filter import gnss_quality_score


GPS_POSITION_KEYS = ("gps_x_m", "gps_y_m", "gps_z_m")
GPS_VELOCITY_KEYS = ("gps_vx_mps", "gps_vy_mps", "gps_vz_mps")


@dataclass(frozen=True)
class FusionEstimate:
    """Flat snapshot from the simple post-run fusion estimator."""

    time_s: float
    x_m: float
    y_m: float
    z_m: float
    vx_mps: float
    vy_mps: float
    vz_mps: float
    speed_mps: float
    gnss_quality_score: float
    gnss_used: bool
    barometer_used: bool
    pitot_used: bool
    radar_altimeter_used: bool


class SimpleFusionEstimator:
    """Deterministic constant-velocity estimator with simple sensor blending.

    The estimator is intentionally modest. It is a reporting primitive, not a
    simulator dynamics component: it predicts position from velocity, uses GNSS
    when available, and lightly blends altitude and speed aids when present.
    """

    def __init__(
        self,
        *,
        gnss_position_weight: float = 0.85,
        gnss_velocity_weight: float = 0.75,
        barometer_weight: float = 0.25,
        radar_altimeter_weight: float = 0.2,
        pitot_speed_weight: float = 0.2,
        max_dt_s: float = 5.0,
    ):
        self.gnss_position_weight = _clip(gnss_position_weight, 0.0, 1.0)
        self.gnss_velocity_weight = _clip(gnss_velocity_weight, 0.0, 1.0)
        self.barometer_weight = _clip(barometer_weight, 0.0, 1.0)
        self.radar_altimeter_weight = _clip(radar_altimeter_weight, 0.0, 1.0)
        self.pitot_speed_weight = _clip(pitot_speed_weight, 0.0, 1.0)
        self.max_dt_s = max(1e-6, _finite_or_default(max_dt_s, 5.0))
        self.position_m = [0.0, 0.0, 0.0]
        self.velocity_mps = [0.0, 0.0, 0.0]
        self.initialized = False
        self.time_s: float | None = None

    def step(self, time_s: float, sensor_row: dict[str, Any]) -> FusionEstimate:
        """Advance the estimate to `time_s` and blend available measurements."""

        current_time = _finite_or_default(time_s, self.time_s or 0.0)
        if self.initialized and self.time_s is not None:
            dt = _clip(current_time - self.time_s, 0.0, self.max_dt_s)
            for index in range(3):
                self.position_m[index] += self.velocity_mps[index] * dt
        elif not self.initialized:
            self._initialize(sensor_row)
        self.time_s = current_time

        quality = gnss_quality_score(sensor_row)
        gnss_used = False
        position = _vector_from_row(sensor_row, GPS_POSITION_KEYS)
        velocity = _vector_from_row(sensor_row, GPS_VELOCITY_KEYS)
        if quality > 0.0 and position is not None:
            weight = _clip(self.gnss_position_weight * max(quality, 0.05), 0.05, self.gnss_position_weight)
            self.position_m = _blend_vectors(self.position_m, position, weight)
            gnss_used = True
        if quality > 0.0 and velocity is not None:
            weight = _clip(self.gnss_velocity_weight * max(quality, 0.05), 0.05, self.gnss_velocity_weight)
            self.velocity_mps = _blend_vectors(self.velocity_mps, velocity, weight)
            gnss_used = True

        barometer_used = self._blend_altitude(sensor_row, "baro_alt_m", "baro_valid", self.barometer_weight)
        radar_used = self._blend_altitude(sensor_row, "radar_agl_m", "radar_valid", self.radar_altimeter_weight)
        pitot_used = self._blend_speed(sensor_row)
        self.initialized = True
        return FusionEstimate(
            time_s=current_time,
            x_m=float(self.position_m[0]),
            y_m=float(self.position_m[1]),
            z_m=float(self.position_m[2]),
            vx_mps=float(self.velocity_mps[0]),
            vy_mps=float(self.velocity_mps[1]),
            vz_mps=float(self.velocity_mps[2]),
            speed_mps=float(_norm(self.velocity_mps)),
            gnss_quality_score=float(quality),
            gnss_used=gnss_used,
            barometer_used=barometer_used,
            pitot_used=pitot_used,
            radar_altimeter_used=radar_used,
        )

    def _initialize(self, sensor_row: dict[str, Any]) -> None:
        position = _vector_from_row(sensor_row, GPS_POSITION_KEYS)
        velocity = _vector_from_row(sensor_row, GPS_VELOCITY_KEYS)
        if position is not None and gnss_quality_score(sensor_row) > 0.0:
            self.position_m = [float(value) for value in position]
        else:
            altitude = _first_valid_measurement(sensor_row, ("baro_alt_m", "radar_agl_m"))
            if altitude is not None:
                self.position_m[2] = altitude
        if velocity is not None and gnss_quality_score(sensor_row) > 0.0:
            self.velocity_mps = [float(value) for value in velocity]
        else:
            speed = _valid_channel_value(sensor_row, "pitot_airspeed_mps", "pitot_valid")
            if speed is not None:
                self.velocity_mps[0] = speed
        self.initialized = True

    def _blend_altitude(self, sensor_row: dict[str, Any], value_key: str, valid_key: str, weight: float) -> bool:
        value = _valid_channel_value(sensor_row, value_key, valid_key)
        if value is None:
            return False
        if value_key == "radar_agl_m":
            terrain_elevation = _finite_or_none(sensor_row.get("terrain_elevation_m"))
            if terrain_elevation is not None:
                value += terrain_elevation
        self.position_m[2] = _blend(self.position_m[2], value, weight)
        return True

    def _blend_speed(self, sensor_row: dict[str, Any]) -> bool:
        value = _valid_channel_value(sensor_row, "pitot_airspeed_mps", "pitot_valid")
        if value is None:
            return False
        speed = _norm(self.velocity_mps)
        if speed > 1e-9:
            scale = _blend(1.0, value / speed, self.pitot_speed_weight)
            self.velocity_mps = [component * scale for component in self.velocity_mps]
        else:
            self.velocity_mps[0] = _blend(self.velocity_mps[0], value, self.pitot_speed_weight)
        return True


def _vector_from_row(row: dict[str, Any], keys: tuple[str, str, str]) -> list[float] | None:
    values = [_finite_or_none(row.get(key)) for key in keys]
    if all(value is not None for value in values):
        return [float(value) for value in values if value is not None]
    return None


def _valid_channel_value(row: dict[str, Any], value_key: str, valid_key: str) -> float | None:
    value = _finite_or_none(row.get(value_key))
    if value is None:
        return None
    valid = _finite_or_none(row.get(valid_key))
    if valid_key in row and (valid is None or valid <= 0.5):
        return None
    return value


def _first_valid_measurement(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        valid_key = "baro_valid" if key.startswith("baro_") else "radar_valid"
        value = _valid_channel_value(row, key, valid_key)
        if value is not None:
            if key == "radar_agl_m":
                terrain_elevation = _finite_or_none(row.get("terrain_elevation_m"))
                if terrain_elevation is not None:
                    return value + terrain_elevation
            return value
    return None


def _blend(current: float, measured: float, weight: float) -> float:
    clipped = _clip(weight, 0.0, 1.0)
    return float((1.0 - clipped) * current + clipped * measured)


def _blend_vectors(current: list[float], measured: list[float], weight: float) -> list[float]:
    return [_blend(current[index], measured[index], weight) for index in range(3)]


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_or_default(value: Any, default: float) -> float:
    number = _finite_or_none(value)
    return float(default) if number is None else number


def _clip(value: float, lower: float, upper: float) -> float:
    return float(min(upper, max(lower, value)))
