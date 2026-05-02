"""Scenario loading, inheritance, defaults, and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import deep_merge, load_json, load_with_optional_base


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Scenario:
    name: str
    dt: float
    duration: float
    vehicle: dict[str, Any]
    initial: dict[str, Any]
    guidance: dict[str, Any]
    autopilot: dict[str, Any]
    environment: dict[str, Any]
    wind: dict[str, Any]
    sensors: dict[str, Any]
    events: dict[str, Any]
    integrator: str
    raw: dict[str, Any]
    source_path: Path | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> "Scenario":
        p = Path(path)
        data = load_with_optional_base(p)
        base_dir = p.parent
        if "vehicle_config" in data:
            vpath = _resolve_path(data["vehicle_config"], base_dir)
            data["vehicle"] = deep_merge(load_with_optional_base(vpath), data.get("vehicle", {}))
        if "environment_config" in data:
            epath = _resolve_path(data["environment_config"], base_dir)
            env = deep_merge(load_with_optional_base(epath), data.get("environment", {}))
            data["environment"] = env
            if "wind" not in data and "wind" in env:
                data["wind"] = env["wind"]
        scenario = cls.from_dict(data, source_path=p)
        validate_scenario(scenario)
        return scenario

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_path: Path | None = None) -> "Scenario":
        env = data.get("environment", {})
        scenario = cls(
            name=str(data.get("name", source_path.stem if source_path else "scenario")),
            dt=float(data.get("dt", 0.02)),
            duration=float(data.get("duration", 20.0)),
            vehicle=data.get("vehicle", {}),
            initial=data.get("initial", {}),
            guidance=data.get("guidance", {}),
            autopilot=data.get("autopilot", data.get("guidance", {}).get("autopilot", {})),
            environment=env,
            wind=data.get("wind", env.get("wind", {})),
            sensors=data.get("sensors", {}),
            events=data.get("events", {}),
            integrator=str(data.get("integrator", "semi_implicit_euler")),
            raw=data,
            source_path=source_path,
        )
        validate_scenario(scenario)
        return scenario


def validate_scenario(scenario: Scenario) -> list[str]:
    errors: list[str] = []
    if not math.isfinite(scenario.dt) or scenario.dt <= 0.0:
        errors.append("dt must be a positive finite number")
    if not math.isfinite(scenario.duration) or scenario.duration <= 0.0:
        errors.append("duration must be a positive finite number")
    if scenario.dt > 0.0 and scenario.duration / scenario.dt > 500_000:
        errors.append("duration/dt creates more than 500000 steps")
    mass = _finite_number("vehicle.mass_kg", scenario.vehicle.get("mass_kg", 18.0), errors)
    dry = _finite_number("vehicle.dry_mass_kg", scenario.vehicle.get("dry_mass_kg", (mass or 18.0) * 0.75), errors)
    if mass is not None and dry is not None and (dry <= 0.0 or mass <= 0.0 or dry > mass):
        errors.append("vehicle.mass_kg and vehicle.dry_mass_kg must be positive with dry_mass_kg <= mass_kg")
    if scenario.integrator not in {"semi_implicit_euler", "euler", "rk2", "rk4", "adaptive_rk45"}:
        errors.append("integrator must be one of: semi_implicit_euler, euler, rk2, rk4, adaptive_rk45")
    for key in ("position_m", "velocity_mps", "euler_deg"):
        if key in scenario.initial:
            _vector3(f"initial.{key}", scenario.initial[key], errors)
    if "body_rates_dps" in scenario.initial:
        _vector3("initial.body_rates_dps", scenario.initial["body_rates_dps"], errors)
    reference = scenario.vehicle.get("reference", {})
    for key in ("area_m2", "span_m", "chord_m"):
        if key in reference:
            value = _finite_number(f"vehicle.reference.{key}", reference[key], errors)
            if value is not None and value <= 0.0:
                errors.append(f"vehicle.reference.{key} must be positive")
    propulsion = scenario.vehicle.get("propulsion", {})
    for key in ("max_thrust_n", "isp_s", "burn_time_s"):
        if key in propulsion:
            value = _finite_number(f"vehicle.propulsion.{key}", propulsion[key], errors)
            if value is not None and value < 0.0:
                errors.append(f"vehicle.propulsion.{key} cannot be negative")
    throttle = scenario.guidance.get("throttle")
    if throttle is not None:
        value = _finite_number("guidance.throttle", throttle, errors)
        if value is not None and not 0.0 <= value <= 1.0:
            errors.append("guidance.throttle must be between 0 and 1")
    for key in ("qbar_limit_pa", "load_limit_g", "target_threshold_m"):
        if key in scenario.events:
            value = _finite_number(f"events.{key}", scenario.events[key], errors)
            if value is not None and value <= 0.0:
                errors.append(f"events.{key} must be positive")
    _validate_engagement_objects(scenario.raw, errors)
    _validate_sensor_rates(scenario.sensors, errors)
    _validate_sensor_faults(scenario.sensors, errors)
    if errors:
        prefix = f"{scenario.source_path}: " if scenario.source_path else ""
        raise ValueError(prefix + "; ".join(errors))
    return []


def validate_scenario_file(path: str | Path) -> dict[str, Any]:
    scenario = Scenario.from_file(path)
    return {
        "valid": True,
        "scenario": scenario.name,
        "dt": scenario.dt,
        "duration": scenario.duration,
        "integrator": scenario.integrator,
    }


def _resolve_path(value: str, base_dir: Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    candidate = base_dir / p
    if candidate.exists():
        return candidate
    root_candidate = _repo_root() / p
    if root_candidate.exists():
        return root_candidate
    return candidate


def _finite_number(name: str, value: Any, errors: list[str]) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"{name} must be a finite number")
        return None
    if not math.isfinite(number):
        errors.append(f"{name} must be a finite number")
        return None
    return number


def _vector3(name: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        errors.append(f"{name} must have three finite numeric elements")
        return
    for idx, item in enumerate(value):
        _finite_number(f"{name}[{idx}]", item, errors)


def _validate_sensor_rates(config: dict[str, Any], errors: list[str]) -> None:
    for top_key in ("imu_rate_hz", "gps_rate_hz", "baro_rate_hz"):
        if top_key in config:
            value = _finite_number(f"sensors.{top_key}", config[top_key], errors)
            if value is not None and value < 0.0:
                errors.append(f"sensors.{top_key} cannot be negative")
    for section in ("imu", "gps", "barometer", "pitot", "magnetometer", "radar_altimeter", "optical_flow", "horizon"):
        sensor_cfg = config.get(section, {})
        if isinstance(sensor_cfg, dict) and "rate_hz" in sensor_cfg:
            value = _finite_number(f"sensors.{section}.rate_hz", sensor_cfg["rate_hz"], errors)
            if value is not None and value < 0.0:
                errors.append(f"sensors.{section}.rate_hz cannot be negative")


def _validate_sensor_faults(config: dict[str, Any], errors: list[str]) -> None:
    faults = config.get("faults", [])
    if faults in (None, []):
        return
    if not isinstance(faults, list):
        errors.append("sensors.faults must be a list")
        return
    valid_sensors = {"*", "imu", "gps", "barometer", "pitot", "magnetometer", "radar_altimeter", "optical_flow", "horizon"}
    valid_types = {"dropout", "bias_jump", "bias", "scale"}
    for idx, fault in enumerate(faults):
        if not isinstance(fault, dict):
            errors.append(f"sensors.faults[{idx}] must be an object")
            continue
        kind = str(fault.get("type", "bias_jump"))
        if kind not in valid_types:
            errors.append(f"sensors.faults[{idx}].type must be one of: bias_jump, bias, dropout, scale")
        sensor = fault.get("sensor", fault.get("target", fault.get("name", "")))
        sensors = fault.get("sensors")
        names = [str(sensor)] if sensor else []
        if isinstance(sensors, list):
            names.extend(str(item) for item in sensors)
        if not names:
            errors.append(f"sensors.faults[{idx}] must define sensor or sensors")
        for name in names:
            if name not in valid_sensors:
                errors.append(f"sensors.faults[{idx}] references unknown sensor {name}")
        start = _finite_number(f"sensors.faults[{idx}].start_s", fault.get("start_s", 0.0), errors)
        end = _finite_number(f"sensors.faults[{idx}].end_s", fault.get("end_s", 1e99), errors)
        if start is not None and end is not None and end < start:
            errors.append(f"sensors.faults[{idx}].end_s must be >= start_s")


def _validate_engagement_objects(config: dict[str, Any], errors: list[str]) -> None:
    targets = config.get("targets", [])
    if targets not in (None, []) and not isinstance(targets, list):
        errors.append("targets must be a list")
    if isinstance(targets, list):
        for idx, target in enumerate(targets):
            if not isinstance(target, dict):
                errors.append(f"targets[{idx}] must be an object")
                continue
            if "initial_position_m" in target:
                _vector3(f"targets[{idx}].initial_position_m", target["initial_position_m"], errors)
            if "position_m" in target:
                _vector3(f"targets[{idx}].position_m", target["position_m"], errors)
            if "velocity_mps" in target:
                _vector3(f"targets[{idx}].velocity_mps", target["velocity_mps"], errors)
    interceptors = config.get("interceptors", [])
    if interceptors not in (None, []) and not isinstance(interceptors, list):
        errors.append("interceptors must be a list")
    if isinstance(interceptors, list):
        for idx, interceptor in enumerate(interceptors):
            if not isinstance(interceptor, dict):
                errors.append(f"interceptors[{idx}] must be an object")
                continue
            for key in ("initial_position_m", "position_m", "initial_velocity_mps", "velocity_mps"):
                if key in interceptor:
                    _vector3(f"interceptors[{idx}].{key}", interceptor[key], errors)
            for key in ("launch_time_s", "max_speed_mps", "max_accel_mps2", "guidance_gain", "proximity_fuze_m"):
                if key in interceptor:
                    value = _finite_number(f"interceptors[{idx}].{key}", interceptor[key], errors)
                    if value is not None and value < 0.0:
                        errors.append(f"interceptors[{idx}].{key} cannot be negative")
