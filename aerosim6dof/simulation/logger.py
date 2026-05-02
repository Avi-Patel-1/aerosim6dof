"""Log row assembly helpers."""

from __future__ import annotations

import math
from typing import Any

from aerosim6dof.core.quaternions import to_euler


def build_rows(
    t: float,
    state: Any,
    evaluation: Any,
    guidance: Any,
    commands_rad: dict[str, float],
    controls_rad: dict[str, float],
    actuator_flags: dict[str, Any],
    sensors: dict[str, float],
    terrain_elevation_m: float | None = None,
    altitude_agl_m: float | None = None,
    contact_state: dict[str, Any] | None = None,
    target_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    roll, pitch, yaw = to_euler(state.quaternion)
    terrain_elevation = float(terrain_elevation_m) if terrain_elevation_m is not None else 0.0
    altitude_agl = float(altitude_agl_m) if altitude_agl_m is not None else float(state.position_m[2]) - terrain_elevation
    target = target_state or {}
    truth = {
        "time_s": t,
        "x_m": float(state.position_m[0]),
        "y_m": float(state.position_m[1]),
        "altitude_m": float(state.position_m[2]),
        "terrain_elevation_m": terrain_elevation,
        "altitude_agl_m": altitude_agl,
        "terrain_slope_x": float((contact_state or {}).get("terrain_slope_x", 0.0)),
        "terrain_slope_y": float((contact_state or {}).get("terrain_slope_y", 0.0)),
        "terrain_slope_deg": float((contact_state or {}).get("terrain_slope_deg", 0.0)),
        "terrain_rate_mps": float((contact_state or {}).get("terrain_rate_mps", 0.0)),
        "altitude_agl_rate_mps": float((contact_state or {}).get("altitude_agl_rate_mps", 0.0)),
        "ground_contact": float((contact_state or {}).get("ground_contact", 0.0)),
        "ground_contact_state": str((contact_state or {}).get("ground_contact_state", "airborne")),
        "ground_contact_severity": float((contact_state or {}).get("ground_contact_severity", 0.0)),
        "impact_speed_mps": float((contact_state or {}).get("impact_speed_mps", 0.0)),
        "vx_mps": float(state.velocity_mps[0]),
        "vy_mps": float(state.velocity_mps[1]),
        "vz_mps": float(state.velocity_mps[2]),
        "speed_mps": float((state.velocity_mps @ state.velocity_mps) ** 0.5),
        "mass_kg": float(state.mass_kg),
        "roll_deg": math.degrees(roll),
        "pitch_deg": math.degrees(pitch),
        "yaw_deg": math.degrees(yaw),
        "p_dps": math.degrees(float(state.rates_rps[0])),
        "q_dps": math.degrees(float(state.rates_rps[1])),
        "r_dps": math.degrees(float(state.rates_rps[2])),
        "alpha_deg": math.degrees(evaluation.aero.alpha_rad),
        "beta_deg": math.degrees(evaluation.aero.beta_rad),
        "qbar_pa": float(evaluation.aero.qbar_pa),
        "mach": float(evaluation.aero.mach),
        "airspeed_mps": float(evaluation.airspeed_mps),
        "load_factor_g": float(evaluation.load_factor_g),
        "density_kgpm3": float(evaluation.atmosphere.density),
        "pressure_pa": float(evaluation.atmosphere.pressure),
        "temperature_k": float(evaluation.atmosphere.temperature),
        "wind_x_mps": float(evaluation.wind_mps[0]),
        "wind_y_mps": float(evaluation.wind_mps[1]),
        "wind_z_mps": float(evaluation.wind_mps[2]),
        "thrust_n": float(evaluation.propulsion.thrust_n),
        "mass_flow_kgps": float(evaluation.propulsion.mass_flow_kgps),
        "propulsion_throttle_actual": float(evaluation.propulsion.throttle_actual),
        "propulsion_health": evaluation.propulsion.health,
        "energy_j_per_kg": float(evaluation.energy_j_per_kg),
        "target_count": _float(target.get("target_count"), 0.0),
        "target_id": str(target.get("target_id", "")),
        "target_active": _float(target.get("target_active"), 0.0),
        "target_x_m": _float(target.get("target_x_m")),
        "target_y_m": _float(target.get("target_y_m")),
        "target_z_m": _float(target.get("target_z_m")),
        "target_vx_mps": _float(target.get("target_vx_mps")),
        "target_vy_mps": _float(target.get("target_vy_mps")),
        "target_vz_mps": _float(target.get("target_vz_mps")),
        "target_range_m": _float(target.get("target_range_m")),
        "target_range_rate_mps": _float(target.get("target_range_rate_mps")),
        "closing_speed_mps": _float(target.get("closing_speed_mps")),
        "relative_x_m": _float(target.get("relative_x_m")),
        "relative_y_m": _float(target.get("relative_y_m")),
        "relative_z_m": _float(target.get("relative_z_m")),
        "target_distance_m": float(guidance.target_distance_m),
        "guidance_mode": guidance.mode,
        "pitch_command_deg": math.degrees(guidance.pitch_rad),
        "heading_command_deg": math.degrees(guidance.heading_rad),
        "roll_command_deg": math.degrees(guidance.roll_rad),
    }
    controls = {
        "time_s": t,
        "elevator_command_deg": math.degrees(float(commands_rad.get("elevator", 0.0))),
        "aileron_command_deg": math.degrees(float(commands_rad.get("aileron", 0.0))),
        "rudder_command_deg": math.degrees(float(commands_rad.get("rudder", 0.0))),
        "elevator_deg": math.degrees(float(controls_rad.get("elevator", 0.0))),
        "aileron_deg": math.degrees(float(controls_rad.get("aileron", 0.0))),
        "rudder_deg": math.degrees(float(controls_rad.get("rudder", 0.0))),
        "throttle": float(controls_rad.get("throttle", 0.0)),
    }
    controls.update({k: _flag(v) for k, v in actuator_flags.items() if isinstance(v, bool)})
    controls.update({k: v for k, v in actuator_flags.items() if not isinstance(v, bool)})
    sensor_row = {"time_s": t, **sensors}
    history = {**truth, **controls, **sensors}
    return history, truth, controls, sensor_row


def _flag(value: bool) -> float:
    return 1.0 if value else 0.0


def _float(value: Any, default: float = float("nan")) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default
