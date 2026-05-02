"""Standalone interceptor/missile dynamics primitives.

This module is intentionally decoupled from ``InterceptorSuite`` and the main
scenario runner. It provides small, deterministic building blocks that can be
covered by unit tests now and wired into the integrated engagement path later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from aerosim6dof.constants import G0

Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class SeekerConfig:
    min_range_m: float = 0.0
    max_range_m: float = 6000.0
    field_of_view_deg: float = 70.0
    boresight_unit: Vector3 = (1.0, 0.0, 0.0)

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "SeekerConfig":
        cfg = config or {}
        return cls(
            min_range_m=_finite(cfg.get("min_range_m"), cls.min_range_m),
            max_range_m=max(0.0, _finite(cfg.get("max_range_m"), cls.max_range_m)),
            field_of_view_deg=max(
                0.0,
                _finite(cfg.get("field_of_view_deg", cfg.get("fov_deg")), cls.field_of_view_deg),
            ),
            boresight_unit=_tuple3(cfg.get("boresight_unit", cfg.get("boresight_mps")), cls.boresight_unit),
        )


@dataclass(frozen=True)
class SeekerMeasurement:
    valid: bool
    status: str
    range_m: float
    range_rate_mps: float
    closing_speed_mps: float
    line_of_sight_unit: np.ndarray
    line_of_sight_rate_rps: np.ndarray
    boresight_unit: np.ndarray
    aspect_angle_rad: float


@dataclass(frozen=True)
class GuidanceConfig:
    navigation_constant: float = 3.0
    max_accel_mps2: float = 140.0
    require_valid_measurement: bool = True
    require_closing: bool = True
    min_closing_speed_mps: float = 1.0

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "GuidanceConfig":
        cfg = config or {}
        return cls(
            navigation_constant=max(
                0.0,
                _finite(cfg.get("navigation_constant", cfg.get("pn_gain")), cls.navigation_constant),
            ),
            max_accel_mps2=max(0.0, _finite(cfg.get("max_accel_mps2"), cls.max_accel_mps2)),
            require_valid_measurement=_bool(cfg.get("require_valid_measurement"), cls.require_valid_measurement),
            require_closing=_bool(cfg.get("require_closing"), cls.require_closing),
            min_closing_speed_mps=max(0.0, _finite(cfg.get("min_closing_speed_mps"), cls.min_closing_speed_mps)),
        )


@dataclass(frozen=True)
class GuidanceCommand:
    acceleration_command_mps2: np.ndarray
    command_norm_mps2: float
    valid: bool
    saturated: bool
    status: str


@dataclass(frozen=True)
class MotorConfig:
    max_thrust_n: float = 4500.0
    burn_time_s: float = 3.5
    ignition_delay_s: float = 0.0
    spool_time_s: float = 0.15
    isp_s: float = 210.0
    throttle: float = 1.0
    thrust_profile: tuple[tuple[float, float], ...] = ()

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "MotorConfig":
        cfg = config or {}
        return cls(
            max_thrust_n=max(0.0, _finite(cfg.get("max_thrust_n", cfg.get("thrust_n")), cls.max_thrust_n)),
            burn_time_s=max(0.0, _finite(cfg.get("burn_time_s"), cls.burn_time_s)),
            ignition_delay_s=max(0.0, _finite(cfg.get("ignition_delay_s"), cls.ignition_delay_s)),
            spool_time_s=max(0.0, _finite(cfg.get("spool_time_s"), cls.spool_time_s)),
            isp_s=max(1e-6, _finite(cfg.get("isp_s"), cls.isp_s)),
            throttle=_clamp(_finite(cfg.get("throttle"), cls.throttle), 0.0, 1.0),
            thrust_profile=_profile(cfg.get("thrust_profile", cfg.get("profile"))),
        )


@dataclass(frozen=True)
class MotorSample:
    thrust_n: float
    mass_flow_kgps: float
    spool_fraction: float
    profile_fraction: float
    active: bool
    burned_out: bool
    phase: str


@dataclass(frozen=True)
class ActuatorConfig:
    max_accel_mps2: float = 140.0
    rate_limit_mps3: float = 900.0

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "ActuatorConfig":
        cfg = config or {}
        return cls(
            max_accel_mps2=max(0.0, _finite(cfg.get("max_accel_mps2"), cls.max_accel_mps2)),
            rate_limit_mps3=max(0.0, _finite(cfg.get("rate_limit_mps3"), cls.rate_limit_mps3)),
        )


@dataclass(frozen=True)
class ActuatorSample:
    acceleration_mps2: np.ndarray
    requested_acceleration_mps2: np.ndarray
    saturated: bool
    rate_limited: bool


@dataclass(frozen=True)
class FuzeConfig:
    arming_time_s: float = 0.25
    proximity_radius_m: float = 8.0
    self_destruct_time_s: float = 30.0
    require_valid_measurement: bool = False

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "FuzeConfig":
        cfg = config or {}
        return cls(
            arming_time_s=max(0.0, _finite(cfg.get("arming_time_s"), cls.arming_time_s)),
            proximity_radius_m=max(
                0.0,
                _finite(cfg.get("proximity_radius_m", cfg.get("proximity_fuze_m")), cls.proximity_radius_m),
            ),
            self_destruct_time_s=max(0.0, _finite(cfg.get("self_destruct_time_s"), cls.self_destruct_time_s)),
            require_valid_measurement=_bool(cfg.get("require_valid_measurement"), cls.require_valid_measurement),
        )


@dataclass(frozen=True)
class FuzeSample:
    armed: bool
    fuzed: bool
    status: str
    range_m: float
    closest_range_m: float


@dataclass(frozen=True)
class MissileDynamicsConfig:
    dry_mass_kg: float = 45.0
    seeker: SeekerConfig = field(default_factory=SeekerConfig)
    guidance: GuidanceConfig = field(default_factory=GuidanceConfig)
    motor: MotorConfig = field(default_factory=MotorConfig)
    actuator: ActuatorConfig = field(default_factory=ActuatorConfig)
    fuze: FuzeConfig = field(default_factory=FuzeConfig)
    gravity_mps2: Vector3 = (0.0, 0.0, 0.0)

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "MissileDynamicsConfig":
        cfg = config or {}
        return cls(
            dry_mass_kg=max(0.0, _finite(cfg.get("dry_mass_kg"), cls.dry_mass_kg)),
            seeker=SeekerConfig.from_dict(_section(cfg, "seeker")),
            guidance=GuidanceConfig.from_dict(_section(cfg, "guidance")),
            motor=MotorConfig.from_dict(_section(cfg, "motor")),
            actuator=ActuatorConfig.from_dict(_section(cfg, "actuator", "control")),
            fuze=FuzeConfig.from_dict(_section(cfg, "fuze", "fuse")),
            gravity_mps2=_tuple3(cfg.get("gravity_mps2"), cls.gravity_mps2),
        )


@dataclass(frozen=True)
class MissileState:
    time_s: float
    position_m: np.ndarray
    velocity_mps: np.ndarray
    mass_kg: float
    control_accel_mps2: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=float))
    fuzed: bool = False
    closest_range_m: float = float("inf")


@dataclass(frozen=True)
class TargetState:
    position_m: np.ndarray
    velocity_mps: np.ndarray
    target_id: str = "target"


@dataclass(frozen=True)
class MissileStepResult:
    state: MissileState
    telemetry: dict[str, Any]


def measure_seeker(
    missile_position_m: np.ndarray,
    missile_velocity_mps: np.ndarray,
    target_position_m: np.ndarray,
    target_velocity_mps: np.ndarray,
    config: SeekerConfig | None = None,
    boresight_unit: np.ndarray | None = None,
) -> SeekerMeasurement:
    """Measure relative target geometry and gate it by range and field of view."""

    cfg = config or SeekerConfig()
    missile_position = _array3(missile_position_m)
    missile_velocity = _array3(missile_velocity_mps)
    target_position = _array3(target_position_m)
    target_velocity = _array3(target_velocity_mps)
    rel = target_position - missile_position
    rel_vel = target_velocity - missile_velocity
    range_m = float(np.linalg.norm(rel))
    fallback_boresight = _array3(boresight_unit) if boresight_unit is not None else _array3(cfg.boresight_unit)
    boresight = _unit(missile_velocity, fallback_boresight)
    los = _unit(rel, boresight)
    range_rate = (
        float(rel @ rel_vel / max(range_m, 1e-9))
        if _finite_bool(range_m)
        else float("nan")
    )
    los_rate = (
        np.cross(rel, rel_vel) / max(range_m * range_m, 1e-9)
        if _finite_bool(range_m)
        else np.zeros(3, dtype=float)
    )
    cos_aspect = _clamp(float(boresight @ los), -1.0, 1.0)
    aspect = math.acos(cos_aspect)
    half_fov = math.radians(max(0.0, cfg.field_of_view_deg) * 0.5)
    in_fov = cfg.field_of_view_deg >= 360.0 or aspect <= half_fov + 1e-12
    valid = True
    status = "valid"
    if not np.all(np.isfinite(rel)) or not np.all(np.isfinite(rel_vel)):
        valid = False
        status = "nonfinite"
    elif range_m < max(0.0, cfg.min_range_m):
        valid = False
        status = "range_below_min"
    elif range_m > max(0.0, cfg.max_range_m):
        valid = False
        status = "range_above_max"
    elif not in_fov:
        valid = False
        status = "outside_fov"
    return SeekerMeasurement(
        valid=valid,
        status=status,
        range_m=range_m,
        range_rate_mps=range_rate,
        closing_speed_mps=-range_rate,
        line_of_sight_unit=los,
        line_of_sight_rate_rps=los_rate,
        boresight_unit=boresight,
        aspect_angle_rad=aspect,
    )


def proportional_navigation(
    measurement: SeekerMeasurement,
    config: GuidanceConfig | None = None,
) -> GuidanceCommand:
    """Return a 3-D proportional-navigation lateral acceleration command."""

    cfg = config or GuidanceConfig()
    if cfg.require_valid_measurement and not measurement.valid:
        return _guidance_zero("invalid_measurement")
    if cfg.require_closing and measurement.closing_speed_mps < cfg.min_closing_speed_mps:
        return _guidance_zero("not_closing")
    accel = (
        cfg.navigation_constant
        * max(0.0, measurement.closing_speed_mps)
        * np.cross(measurement.line_of_sight_rate_rps, measurement.line_of_sight_unit)
    )
    limited, saturated = _limit_norm(accel, cfg.max_accel_mps2)
    return GuidanceCommand(
        acceleration_command_mps2=limited,
        command_norm_mps2=float(np.linalg.norm(limited)),
        valid=True,
        saturated=saturated,
        status="saturated" if saturated else "valid",
    )


def sample_motor(
    t: float,
    dt: float,
    config: MotorConfig | None = None,
    mass_kg: float | None = None,
    dry_mass_kg: float | None = None,
) -> MotorSample:
    """Sample a simple motor with optional profile, spool-up, and burnout."""

    cfg = config or MotorConfig()
    time_s = float(t)
    if time_s < cfg.ignition_delay_s:
        return MotorSample(0.0, 0.0, 0.0, 0.0, False, False, "ignition_delay")
    burn_age = time_s - cfg.ignition_delay_s
    if burn_age >= cfg.burn_time_s:
        return MotorSample(0.0, 0.0, 0.0, 0.0, False, True, "burnout")
    available_mass = float("inf")
    if mass_kg is not None and dry_mass_kg is not None:
        available_mass = max(0.0, float(mass_kg) - float(dry_mass_kg))
        if available_mass <= 1e-9:
            return MotorSample(0.0, 0.0, 0.0, 0.0, False, True, "propellant_depleted")
    spool = 1.0 if cfg.spool_time_s <= 1e-9 else _clamp(burn_age / cfg.spool_time_s, 0.0, 1.0)
    profile = _thrust_profile_fraction(burn_age, cfg.thrust_profile)
    thrust = max(0.0, cfg.max_thrust_n * cfg.throttle * spool * profile)
    mass_flow = thrust / max(cfg.isp_s * G0, 1e-9)
    phase = "spooling" if spool < 1.0 else "boost"
    if math.isfinite(available_mass) and mass_flow > 0.0 and dt > 0.0:
        required = mass_flow * float(dt)
        if required > available_mass:
            scale = available_mass / required
            thrust *= scale
            mass_flow = available_mass / float(dt)
            phase = "propellant_depleting"
    return MotorSample(
        thrust_n=thrust,
        mass_flow_kgps=mass_flow,
        spool_fraction=spool,
        profile_fraction=profile,
        active=thrust > 0.0,
        burned_out=False,
        phase=phase if thrust > 0.0 else "off",
    )


def rate_limit_vector(
    command_mps2: np.ndarray,
    previous_mps2: np.ndarray,
    dt: float,
    config: ActuatorConfig | None = None,
) -> ActuatorSample:
    """Apply vector magnitude and slew-rate limits to a commanded acceleration."""

    cfg = config or ActuatorConfig()
    requested = _array3(command_mps2)
    previous = _array3(previous_mps2)
    limited_request, saturated = _limit_norm(requested, cfg.max_accel_mps2)
    max_delta = max(0.0, cfg.rate_limit_mps3) * max(0.0, float(dt))
    delta = limited_request - previous
    delta_norm = float(np.linalg.norm(delta))
    rate_limited = delta_norm > max_delta > 0.0
    if rate_limited:
        delta = delta / delta_norm * max_delta
    elif max_delta <= 0.0 and delta_norm > 0.0:
        delta = np.zeros(3, dtype=float)
        rate_limited = True
    actual, output_saturated = _limit_norm(previous + delta, cfg.max_accel_mps2)
    return ActuatorSample(
        acceleration_mps2=actual,
        requested_acceleration_mps2=limited_request,
        saturated=saturated or output_saturated,
        rate_limited=rate_limited,
    )


def evaluate_fuze(
    t: float,
    measurement: SeekerMeasurement,
    previous_closest_range_m: float = float("inf"),
    previous_fuzed: bool = False,
    config: FuzeConfig | None = None,
) -> FuzeSample:
    """Evaluate arming, proximity detonation, and self-destruct state."""

    cfg = config or FuzeConfig()
    closest = _closest_range(previous_closest_range_m, measurement.range_m)
    armed = float(t) >= cfg.arming_time_s
    if previous_fuzed:
        return FuzeSample(
            armed=True,
            fuzed=True,
            status="already_fuzed",
            range_m=measurement.range_m,
            closest_range_m=closest,
        )
    if not armed:
        return FuzeSample(
            armed=False,
            fuzed=False,
            status="safe",
            range_m=measurement.range_m,
            closest_range_m=closest,
        )
    if cfg.self_destruct_time_s > 0.0 and float(t) >= cfg.self_destruct_time_s:
        return FuzeSample(
            armed=True,
            fuzed=True,
            status="self_destruct",
            range_m=measurement.range_m,
            closest_range_m=closest,
        )
    valid_for_fuze = measurement.valid or not cfg.require_valid_measurement
    candidate_range = closest if math.isfinite(closest) else measurement.range_m
    if valid_for_fuze and candidate_range <= cfg.proximity_radius_m:
        return FuzeSample(
            armed=True,
            fuzed=True,
            status="proximity",
            range_m=measurement.range_m,
            closest_range_m=closest,
        )
    return FuzeSample(
        armed=True,
        fuzed=False,
        status="armed",
        range_m=measurement.range_m,
        closest_range_m=closest,
    )


def step_missile(
    state: MissileState,
    target: TargetState,
    dt: float,
    config: MissileDynamicsConfig | None = None,
) -> MissileStepResult:
    """Advance one missile step and return the next state plus flat telemetry."""

    cfg = config or MissileDynamicsConfig()
    step_dt = max(0.0, float(dt))
    position = _array3(state.position_m)
    velocity = _array3(state.velocity_mps)
    target_position = _array3(target.position_m)
    target_velocity = _array3(target.velocity_mps)
    measurement = measure_seeker(position, velocity, target_position, target_velocity, cfg.seeker)

    if state.fuzed:
        fuze = evaluate_fuze(state.time_s, measurement, state.closest_range_m, True, cfg.fuze)
        return MissileStepResult(
            state,
            _telemetry(
                state,
                target,
                measurement,
                _guidance_zero("fuzed"),
                _actuator_hold(state),
                _motor_off("fuzed"),
                fuze,
                np.zeros(3),
            ),
        )

    guidance = proportional_navigation(measurement, cfg.guidance)
    actuator = rate_limit_vector(guidance.acceleration_command_mps2, state.control_accel_mps2, step_dt, cfg.actuator)
    motor = sample_motor(state.time_s, step_dt, cfg.motor, state.mass_kg, cfg.dry_mass_kg)
    thrust_direction = _unit(velocity, _array3(cfg.seeker.boresight_unit))
    thrust_accel = thrust_direction * (motor.thrust_n / max(float(state.mass_kg), 1e-9))
    total_accel = actuator.acceleration_mps2 + thrust_accel + _array3(cfg.gravity_mps2)
    next_velocity = velocity + total_accel * step_dt
    next_position = position + next_velocity * step_dt
    next_mass = max(cfg.dry_mass_kg, float(state.mass_kg) - motor.mass_flow_kgps * step_dt)
    next_time = float(state.time_s) + step_dt

    next_measurement = measure_seeker(next_position, next_velocity, target_position, target_velocity, cfg.seeker)
    closest = _closest_range(state.closest_range_m, measurement.range_m, next_measurement.range_m)
    fuze = evaluate_fuze(next_time, next_measurement, closest, False, cfg.fuze)
    next_state = MissileState(
        time_s=next_time,
        position_m=next_position,
        velocity_mps=next_velocity,
        mass_kg=next_mass,
        control_accel_mps2=actuator.acceleration_mps2,
        fuzed=fuze.fuzed,
        closest_range_m=fuze.closest_range_m,
    )
    telemetry = _telemetry(next_state, target, next_measurement, guidance, actuator, motor, fuze, total_accel)
    return MissileStepResult(next_state, telemetry)


missile_step = step_missile


def _telemetry(
    state: MissileState,
    target: TargetState,
    measurement: SeekerMeasurement,
    guidance: GuidanceCommand,
    actuator: ActuatorSample,
    motor: MotorSample,
    fuze: FuzeSample,
    total_accel_mps2: np.ndarray,
) -> dict[str, Any]:
    speed = float(np.linalg.norm(state.velocity_mps))
    return {
        "time_s": float(state.time_s),
        "target_id": target.target_id,
        "missile_x_m": float(state.position_m[0]),
        "missile_y_m": float(state.position_m[1]),
        "missile_z_m": float(state.position_m[2]),
        "missile_vx_mps": float(state.velocity_mps[0]),
        "missile_vy_mps": float(state.velocity_mps[1]),
        "missile_vz_mps": float(state.velocity_mps[2]),
        "missile_speed_mps": speed,
        "missile_mass_kg": float(state.mass_kg),
        "missile_accel_mps2": float(np.linalg.norm(total_accel_mps2)),
        "seeker_valid": 1.0 if measurement.valid else 0.0,
        "seeker_status": measurement.status,
        "seeker_range_m": measurement.range_m,
        "seeker_range_rate_mps": measurement.range_rate_mps,
        "seeker_closing_speed_mps": measurement.closing_speed_mps,
        "seeker_aspect_deg": math.degrees(measurement.aspect_angle_rad),
        "guidance_valid": 1.0 if guidance.valid else 0.0,
        "guidance_status": guidance.status,
        "guidance_accel_cmd_mps2": guidance.command_norm_mps2,
        "control_accel_mps2": float(np.linalg.norm(actuator.acceleration_mps2)),
        "control_rate_limited": 1.0 if actuator.rate_limited else 0.0,
        "control_saturated": 1.0 if actuator.saturated else 0.0,
        "motor_thrust_n": motor.thrust_n,
        "motor_mass_flow_kgps": motor.mass_flow_kgps,
        "motor_spool_fraction": motor.spool_fraction,
        "motor_phase": motor.phase,
        "fuze_armed": 1.0 if fuze.armed else 0.0,
        "fuze_fuzed": 1.0 if fuze.fuzed else 0.0,
        "fuze_status": fuze.status,
        "fuze_closest_range_m": fuze.closest_range_m,
    }


def _guidance_zero(status: str) -> GuidanceCommand:
    return GuidanceCommand(np.zeros(3, dtype=float), 0.0, False, False, status)


def _actuator_hold(state: MissileState) -> ActuatorSample:
    accel = _array3(state.control_accel_mps2)
    return ActuatorSample(accel, accel, False, False)


def _motor_off(phase: str) -> MotorSample:
    return MotorSample(0.0, 0.0, 0.0, 0.0, False, True, phase)


def _section(config: dict[str, Any], *names: str) -> dict[str, Any] | None:
    for name in names:
        section = config.get(name)
        if isinstance(section, dict):
            return section
    return None


def _array3(value: Any) -> np.ndarray:
    arr = np.array(value, dtype=float)
    if arr.shape != (3,):
        raise ValueError(f"expected a 3-vector, got shape {arr.shape}")
    return arr


def _tuple3(value: Any, default: Vector3) -> Vector3:
    try:
        arr = _array3(value if value is not None else default)
    except (TypeError, ValueError):
        arr = _array3(default)
    return (float(arr[0]), float(arr[1]), float(arr[2]))


def _unit(value: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(value))
    if norm <= 1e-12 or not math.isfinite(norm):
        fallback_norm = float(np.linalg.norm(fallback))
        if fallback_norm <= 1e-12 or not math.isfinite(fallback_norm):
            return np.array([1.0, 0.0, 0.0], dtype=float)
        return fallback / fallback_norm
    return value / norm


def _limit_norm(value: np.ndarray, limit: float) -> tuple[np.ndarray, bool]:
    arr = _array3(value)
    lim = max(0.0, float(limit))
    norm = float(np.linalg.norm(arr))
    if norm > lim > 0.0:
        return arr / norm * lim, True
    if lim <= 0.0 and norm > 0.0:
        return np.zeros(3, dtype=float), True
    return arr, False


def _closest_range(*ranges: float) -> float:
    finite = [float(r) for r in ranges if _finite_bool(float(r))]
    return min(finite) if finite else float("inf")


def _thrust_profile_fraction(t: float, profile: tuple[tuple[float, float], ...]) -> float:
    if not profile:
        return 1.0
    pairs = sorted((max(0.0, float(x)), max(0.0, float(y))) for x, y in profile)
    if t <= pairs[0][0]:
        return pairs[0][1]
    if t >= pairs[-1][0]:
        return pairs[-1][1]
    for (x0, y0), (x1, y1) in zip(pairs, pairs[1:]):
        if x0 <= t <= x1:
            span = max(x1 - x0, 1e-12)
            ratio = (t - x0) / span
            return y0 + ratio * (y1 - y0)
    return pairs[-1][1]


def _profile(value: Any) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    pairs: list[tuple[float, float]] = []
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                pairs.append((float(item[0]), float(item[1])))
            except (TypeError, ValueError):
                continue
    return tuple(pairs)


def _finite(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _finite_bool(value: float) -> bool:
    return math.isfinite(float(value))


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


__all__ = [
    "ActuatorConfig",
    "ActuatorSample",
    "FuzeConfig",
    "FuzeSample",
    "GuidanceCommand",
    "GuidanceConfig",
    "MissileDynamicsConfig",
    "MissileState",
    "MissileStepResult",
    "MotorConfig",
    "MotorSample",
    "SeekerConfig",
    "SeekerMeasurement",
    "TargetState",
    "evaluate_fuze",
    "measure_seeker",
    "missile_step",
    "proportional_navigation",
    "rate_limit_vector",
    "sample_motor",
    "step_missile",
]
