"""Kinematic interceptor objects for engagement studies.

The interceptor model is deliberately separate from the vehicle dynamics. It is
integrated inside the simulation loop so runs produce real interceptor state
history, while the primary vehicle state derivative remains unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from aerosim6dof.core.vectors import vec3


@dataclass
class InterceptorObject:
    interceptor_id: str
    target_id: str
    launch_time_s: float
    initial_position_m: np.ndarray | None
    initial_velocity_mps: np.ndarray
    max_speed_mps: float
    max_accel_mps2: float
    guidance_gain: float
    proximity_fuze_m: float
    end_s: float
    position_m: np.ndarray | None = None
    velocity_mps: np.ndarray | None = None
    launched: bool = False
    fuzed: bool = False
    fuzed_time_s: float | None = None
    best_miss_distance_m: float = float("inf")
    best_miss_time_s: float = 0.0

    def active(self, t: float) -> bool:
        return self.launched and self.launch_time_s <= t <= self.end_s and not self.fuzed

    def reset_if_needed(self, carrier_position_m: np.ndarray, carrier_velocity_mps: np.ndarray) -> None:
        if self.position_m is None:
            self.position_m = np.array(self.initial_position_m if self.initial_position_m is not None else carrier_position_m, dtype=float)
        if self.velocity_mps is None:
            self.velocity_mps = np.array(carrier_velocity_mps + self.initial_velocity_mps, dtype=float)


class InterceptorSuite:
    def __init__(self, interceptors: list[InterceptorObject] | None = None):
        self.interceptors = interceptors or []

    @classmethod
    def from_scenario(cls, scenario: Any) -> "InterceptorSuite":
        raw = getattr(scenario, "raw", {})
        configured = raw.get("interceptors", []) if isinstance(raw, dict) else []
        interceptors = [
            interceptor
            for index, item in enumerate(_items(configured))
            if (interceptor := _interceptor_from_config(item, index)) is not None
        ]
        return cls(interceptors)

    def step(
        self,
        t: float,
        dt: float,
        carrier_position_m: np.ndarray,
        carrier_velocity_mps: np.ndarray,
        target_rows: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        target_map = {str(row.get("target_id", "")): row for row in target_rows if _flag(row.get("target_active"))}
        closest: dict[str, Any] | None = None
        for interceptor in self.interceptors:
            if t >= interceptor.launch_time_s and not interceptor.launched:
                interceptor.reset_if_needed(carrier_position_m, carrier_velocity_mps)
                interceptor.launched = True
                events.append(
                    {
                        "time_s": float(t),
                        "type": "interceptor_launch",
                        "description": f"{interceptor.interceptor_id} launched toward {interceptor.target_id}.",
                        "interceptor_id": interceptor.interceptor_id,
                        "target_id": interceptor.target_id,
                    }
                )
            target = target_map.get(interceptor.target_id) or _first_primary(target_rows) or (target_rows[0] if target_rows else None)
            row = self._row(t, interceptor, target)
            if interceptor.active(t) and target is not None:
                self._integrate(interceptor, target, dt)
                row = self._row(t, interceptor, target)
                distance = float(row["interceptor_range_m"])
                if distance < interceptor.best_miss_distance_m:
                    interceptor.best_miss_distance_m = distance
                    interceptor.best_miss_time_s = float(t)
                if distance <= interceptor.proximity_fuze_m and not interceptor.fuzed:
                    interceptor.fuzed = True
                    interceptor.fuzed_time_s = float(t)
                    events.append(
                        {
                            "time_s": float(t),
                            "type": "interceptor_fuze",
                            "description": f"{interceptor.interceptor_id} reached {distance:.2f} m from {row.get('target_id', interceptor.target_id)}.",
                            "interceptor_id": interceptor.interceptor_id,
                            "target_id": str(row.get("target_id", interceptor.target_id)),
                            "miss_distance_m": distance,
                        }
                    )
                    row["interceptor_fuzed"] = 1.0
            rows.append(row)
            if _flag(row.get("interceptor_active")) and (closest is None or float(row["interceptor_range_m"]) < float(closest["interceptor_range_m"])):
                closest = row
        return self._summary(closest), rows, events

    def finalize_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for interceptor in self.interceptors:
            if math.isfinite(interceptor.best_miss_distance_m):
                events.append(
                    {
                        "time_s": float(interceptor.best_miss_time_s),
                        "type": "interceptor_closest_approach",
                        "description": f"{interceptor.interceptor_id} closest approach was {interceptor.best_miss_distance_m:.2f} m.",
                        "interceptor_id": interceptor.interceptor_id,
                        "target_id": interceptor.target_id,
                        "miss_distance_m": interceptor.best_miss_distance_m,
                    }
                )
        return events

    def _integrate(self, interceptor: InterceptorObject, target: dict[str, Any], dt: float) -> None:
        assert interceptor.position_m is not None
        assert interceptor.velocity_mps is not None
        target_position = _target_position(target)
        target_velocity = _target_velocity(target)
        rel = target_position - interceptor.position_m
        distance = max(float(np.linalg.norm(rel)), 1e-9)
        desired_velocity = target_velocity + rel / distance * interceptor.max_speed_mps
        velocity_error = desired_velocity - interceptor.velocity_mps
        accel = velocity_error * interceptor.guidance_gain
        accel_norm = float(np.linalg.norm(accel))
        if accel_norm > interceptor.max_accel_mps2 > 0.0:
            accel = accel / accel_norm * interceptor.max_accel_mps2
        interceptor.velocity_mps = interceptor.velocity_mps + accel * dt
        speed = float(np.linalg.norm(interceptor.velocity_mps))
        if speed > interceptor.max_speed_mps > 0.0:
            interceptor.velocity_mps = interceptor.velocity_mps / speed * interceptor.max_speed_mps
        interceptor.position_m = interceptor.position_m + interceptor.velocity_mps * dt

    def _row(self, t: float, interceptor: InterceptorObject, target: dict[str, Any] | None) -> dict[str, Any]:
        position = interceptor.position_m if interceptor.position_m is not None else np.full(3, float("nan"))
        velocity = interceptor.velocity_mps if interceptor.velocity_mps is not None else np.full(3, float("nan"))
        target_position = _target_position(target) if target is not None else np.full(3, float("nan"))
        target_velocity = _target_velocity(target) if target is not None else np.full(3, float("nan"))
        rel = target_position - position
        rel_vel = target_velocity - velocity
        distance = float(np.linalg.norm(rel)) if np.all(np.isfinite(rel)) else float("nan")
        range_rate = float(rel @ rel_vel / max(distance, 1e-9)) if math.isfinite(distance) else float("nan")
        active = 1.0 if interceptor.active(t) else 0.0
        return {
            "time_s": float(t),
            "interceptor_id": interceptor.interceptor_id,
            "interceptor_target_id": str(target.get("target_id", interceptor.target_id)) if target is not None else interceptor.target_id,
            "interceptor_active": active,
            "interceptor_launched": 1.0 if interceptor.launched else 0.0,
            "interceptor_fuzed": 1.0 if interceptor.fuzed else 0.0,
            "interceptor_x_m": float(position[0]),
            "interceptor_y_m": float(position[1]),
            "interceptor_z_m": float(position[2]),
            "interceptor_vx_mps": float(velocity[0]),
            "interceptor_vy_mps": float(velocity[1]),
            "interceptor_vz_mps": float(velocity[2]),
            "interceptor_speed_mps": float(np.linalg.norm(velocity)) if np.all(np.isfinite(velocity)) else float("nan"),
            "interceptor_range_m": distance,
            "interceptor_range_rate_mps": range_rate,
            "interceptor_closing_speed_mps": -range_rate if math.isfinite(range_rate) else float("nan"),
            "interceptor_best_miss_m": interceptor.best_miss_distance_m if math.isfinite(interceptor.best_miss_distance_m) else distance,
            "interceptor_time_to_go_s": distance / max(-range_rate, 1e-9) if math.isfinite(distance) and math.isfinite(range_rate) and range_rate < 0.0 else float("nan"),
        }

    def _summary(self, closest: dict[str, Any] | None) -> dict[str, Any]:
        if closest is None:
            return {
                "interceptor_count": float(len(self.interceptors)),
                "interceptor_id": "",
                "interceptor_target_id": "",
                "interceptor_active": 0.0,
                "interceptor_launched": 0.0,
                "interceptor_fuzed": 0.0,
                "interceptor_x_m": float("nan"),
                "interceptor_y_m": float("nan"),
                "interceptor_z_m": float("nan"),
                "interceptor_range_m": float("nan"),
                "interceptor_closing_speed_mps": float("nan"),
                "interceptor_best_miss_m": float("nan"),
                "interceptor_time_to_go_s": float("nan"),
            }
        return {"interceptor_count": float(len(self.interceptors)), **closest}


def _items(configured: Any) -> list[dict[str, Any]]:
    if isinstance(configured, dict):
        return [configured]
    if isinstance(configured, list):
        return [item for item in configured if isinstance(item, dict)]
    return []


def _interceptor_from_config(config: dict[str, Any], index: int) -> InterceptorObject | None:
    try:
        initial = config.get("initial_position_m", config.get("position_m"))
        return InterceptorObject(
            interceptor_id=str(config.get("id", config.get("name", f"interceptor_{index + 1}"))),
            target_id=str(config.get("target_id", "primary_target")),
            launch_time_s=_finite(config.get("launch_time_s"), 0.0),
            initial_position_m=None if initial is None else vec3(initial, (0.0, 0.0, 0.0)),
            initial_velocity_mps=vec3(config.get("initial_velocity_mps", config.get("velocity_mps")), (0.0, 0.0, 0.0)),
            max_speed_mps=max(1.0, _finite(config.get("max_speed_mps"), 260.0)),
            max_accel_mps2=max(0.1, _finite(config.get("max_accel_mps2"), 85.0)),
            guidance_gain=max(0.0, _finite(config.get("guidance_gain"), 2.0)),
            proximity_fuze_m=max(0.0, _finite(config.get("proximity_fuze_m"), 15.0)),
            end_s=_finite(config.get("end_s"), 1e99),
        )
    except (TypeError, ValueError):
        return None


def _first_primary(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("target_role", "")) == "primary" and _flag(row.get("target_active")):
            return row
    return None


def _target_position(row: dict[str, Any] | None) -> np.ndarray:
    if row is None:
        return np.full(3, float("nan"))
    return np.array([_finite(row.get("target_x_m"), float("nan")), _finite(row.get("target_y_m"), float("nan")), _finite(row.get("target_z_m"), float("nan"))], dtype=float)


def _target_velocity(row: dict[str, Any] | None) -> np.ndarray:
    if row is None:
        return np.full(3, float("nan"))
    return np.array([_finite(row.get("target_vx_mps"), 0.0), _finite(row.get("target_vy_mps"), 0.0), _finite(row.get("target_vz_mps"), 0.0)], dtype=float)


def _flag(value: Any) -> bool:
    try:
        return float(value) > 0.5
    except (TypeError, ValueError):
        return False


def _finite(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default
