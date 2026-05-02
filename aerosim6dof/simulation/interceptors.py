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
from aerosim6dof.simulation.missile_dynamics import (
    MissileDynamicsConfig,
    MissileState,
    TargetState,
    step_missile,
)


MISSILE_MODELS = {"missile_dynamics_v1", "missile"}
MISSILE_CONFIG_KEYS = {
    "dry_mass_kg",
    "seeker",
    "guidance",
    "motor",
    "actuator",
    "control",
    "fuze",
    "fuse",
    "gravity_mps2",
}


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
    dynamics_model: str = "kinematic"
    missile_config: MissileDynamicsConfig | None = None
    missile_initial_mass_kg: float | None = None
    missile_state: MissileState | None = None
    missile_telemetry: dict[str, Any] | None = None

    def active(self, t: float) -> bool:
        return self.launched and self.launch_time_s <= t <= self.end_s and not self.fuzed

    @property
    def missile_mode(self) -> bool:
        return self.dynamics_model in MISSILE_MODELS and self.missile_config is not None

    def reset_if_needed(self, carrier_position_m: np.ndarray, carrier_velocity_mps: np.ndarray) -> None:
        if self.position_m is None:
            self.position_m = np.array(self.initial_position_m if self.initial_position_m is not None else carrier_position_m, dtype=float)
        if self.velocity_mps is None:
            self.velocity_mps = np.array(carrier_velocity_mps + self.initial_velocity_mps, dtype=float)
        if self.missile_mode and self.missile_state is None:
            assert self.position_m is not None
            assert self.velocity_mps is not None
            assert self.missile_config is not None
            initial_mass = self.missile_initial_mass_kg
            if initial_mass is None:
                initial_mass = self.missile_config.dry_mass_kg
            self.missile_state = MissileState(
                time_s=0.0,
                position_m=np.array(self.position_m, dtype=float),
                velocity_mps=np.array(self.velocity_mps, dtype=float),
                mass_kg=max(self.missile_config.dry_mass_kg, float(initial_mass)),
            )


class InterceptorSuite:
    def __init__(self, interceptors: list[InterceptorObject] | None = None):
        self.interceptors = interceptors or []

    @classmethod
    def from_scenario(cls, scenario: Any) -> "InterceptorSuite":
        raw = getattr(scenario, "raw", {})
        configured = raw.get("interceptors", []) if isinstance(raw, dict) else []
        missile_config = raw.get("missile", {}) if isinstance(raw, dict) and isinstance(raw.get("missile"), dict) else {}
        interceptors = [
            interceptor
            for index, item in enumerate(_items(configured))
            if (interceptor := _interceptor_from_config(item, index, missile_config)) is not None
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
                if _fuzed(row, interceptor) and not interceptor.fuzed:
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
                    if "missile_fuzed" in row:
                        row["missile_fuzed"] = 1.0
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
        if interceptor.missile_mode:
            self._integrate_missile(interceptor, target, dt)
            return
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

    def _integrate_missile(self, interceptor: InterceptorObject, target: dict[str, Any], dt: float) -> None:
        assert interceptor.missile_config is not None
        if interceptor.missile_state is None:
            assert interceptor.position_m is not None
            assert interceptor.velocity_mps is not None
            initial_mass = interceptor.missile_initial_mass_kg
            if initial_mass is None:
                initial_mass = interceptor.missile_config.dry_mass_kg
            interceptor.missile_state = MissileState(
                time_s=0.0,
                position_m=np.array(interceptor.position_m, dtype=float),
                velocity_mps=np.array(interceptor.velocity_mps, dtype=float),
                mass_kg=max(interceptor.missile_config.dry_mass_kg, float(initial_mass)),
            )
        target_state = TargetState(
            position_m=_target_position(target),
            velocity_mps=_target_velocity(target),
            target_id=str(target.get("target_id", interceptor.target_id)),
        )
        result = step_missile(interceptor.missile_state, target_state, dt, interceptor.missile_config)
        interceptor.missile_state = result.state
        interceptor.position_m = np.array(result.state.position_m, dtype=float)
        interceptor.velocity_mps = np.array(result.state.velocity_mps, dtype=float)
        interceptor.missile_telemetry = _missile_row_telemetry(result.telemetry)

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
        row = {
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
        if interceptor.missile_mode:
            row.update(_missile_row_defaults(interceptor))
            if interceptor.missile_telemetry:
                row.update(interceptor.missile_telemetry)
        return row

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


def _interceptor_from_config(config: dict[str, Any], index: int, scenario_missile_config: dict[str, Any] | None = None) -> InterceptorObject | None:
    try:
        initial = config.get("initial_position_m", config.get("position_m"))
        dynamics_model = _dynamics_model(config)
        missile_config_dict = _merged_missile_config(config, scenario_missile_config)
        missile_config = MissileDynamicsConfig.from_dict(missile_config_dict) if dynamics_model in MISSILE_MODELS else None
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
            dynamics_model=dynamics_model,
            missile_config=missile_config,
            missile_initial_mass_kg=_missile_initial_mass(config, scenario_missile_config),
        )
    except (TypeError, ValueError):
        return None


def _dynamics_model(config: dict[str, Any]) -> str:
    return str(config.get("dynamics_model", config.get("model", "kinematic"))).strip().lower()


def _merged_missile_config(config: dict[str, Any], scenario_missile_config: dict[str, Any] | None) -> dict[str, Any]:
    merged = _copy_dict(scenario_missile_config)
    nested = config.get("missile")
    if isinstance(nested, dict):
        merged = _deep_merge(merged, nested)
    for key in MISSILE_CONFIG_KEYS:
        if key in config:
            merged[key] = config[key]
    if "proximity_fuze_m" in config:
        fuze = _copy_dict(merged.get("fuze"))
        fuze.setdefault("proximity_radius_m", config["proximity_fuze_m"])
        merged["fuze"] = fuze
    if "max_accel_mps2" in config:
        guidance = _copy_dict(merged.get("guidance"))
        actuator = _copy_dict(merged.get("actuator", merged.get("control")))
        guidance.setdefault("max_accel_mps2", config["max_accel_mps2"])
        actuator.setdefault("max_accel_mps2", config["max_accel_mps2"])
        merged["guidance"] = guidance
        merged["actuator"] = actuator
    return merged


def _missile_initial_mass(config: dict[str, Any], scenario_missile_config: dict[str, Any] | None) -> float | None:
    for source in (config, config.get("missile"), scenario_missile_config):
        if isinstance(source, dict):
            value = source.get("initial_mass_kg", source.get("mass_kg"))
            if value is not None:
                return max(0.0, _finite(value, 0.0))
    return None


def _copy_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _missile_row_defaults(interceptor: InterceptorObject) -> dict[str, Any]:
    return {
        "missile_mode": 1.0,
        "seeker_valid": 0.0,
        "missile_motor_thrust_n": 0.0,
        "missile_motor_mass_flow_kgps": 0.0,
        "missile_commanded_accel_mps2": 0.0,
        "missile_lateral_accel_mps2": 0.0,
        "missile_closing_speed_mps": float("nan"),
        "missile_fuze_armed": 0.0,
        "missile_fuzed": 1.0 if interceptor.fuzed else 0.0,
    }


def _missile_row_telemetry(telemetry: dict[str, Any]) -> dict[str, Any]:
    return {
        "missile_mode": 1.0,
        "seeker_valid": _float_flag(telemetry.get("seeker_valid")),
        "missile_motor_thrust_n": _finite(telemetry.get("motor_thrust_n"), 0.0),
        "missile_motor_mass_flow_kgps": _finite(telemetry.get("motor_mass_flow_kgps"), 0.0),
        "missile_commanded_accel_mps2": _finite(telemetry.get("guidance_accel_cmd_mps2"), 0.0),
        "missile_lateral_accel_mps2": _finite(telemetry.get("control_accel_mps2"), 0.0),
        "missile_closing_speed_mps": _finite(telemetry.get("seeker_closing_speed_mps"), float("nan")),
        "missile_fuze_armed": _float_flag(telemetry.get("fuze_armed")),
        "missile_fuzed": _float_flag(telemetry.get("fuze_fuzed")),
    }


def _fuzed(row: dict[str, Any], interceptor: InterceptorObject) -> bool:
    if interceptor.missile_mode and _flag(row.get("missile_fuzed")):
        return True
    distance = _finite(row.get("interceptor_range_m"), float("nan"))
    return math.isfinite(distance) and distance <= interceptor.proximity_fuze_m


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


def _float_flag(value: Any) -> float:
    return 1.0 if _flag(value) else 0.0


def _finite(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default
