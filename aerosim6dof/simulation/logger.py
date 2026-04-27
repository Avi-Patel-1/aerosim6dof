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
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    roll, pitch, yaw = to_euler(state.quaternion)
    truth = {
        "time_s": t,
        "x_m": float(state.position_m[0]),
        "y_m": float(state.position_m[1]),
        "altitude_m": float(state.position_m[2]),
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
