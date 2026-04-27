"""Trim and linearization helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from aerosim6dof.core.quaternions import from_euler
from aerosim6dof.environment.atmosphere import isa_atmosphere
from aerosim6dof.vehicle.aerodynamics import AerodynamicModel
from aerosim6dof.vehicle.geometry import ReferenceGeometry


def simple_trim(vehicle_config: dict[str, Any], speed_mps: float, altitude_m: float) -> dict[str, Any]:
    aero = AerodynamicModel(vehicle_config.get("aero", {}))
    geom = ReferenceGeometry.from_config(vehicle_config.get("reference", {}))
    mass = float(vehicle_config.get("mass_kg", 18.0))
    env = isa_atmosphere(altitude_m)
    target_lift = mass * 9.80665
    best: tuple[float, float, float] | None = None
    for alpha_deg in np.linspace(-5.0, 18.0, 93):
        for de_deg in np.linspace(-18.0, 18.0, 73):
            sample = aero.compute(
                env.density,
                env.speed_of_sound,
                np.array([speed_mps * math.cos(math.radians(alpha_deg)), 0.0, speed_mps * math.sin(math.radians(alpha_deg))]),
                np.zeros(3),
                {"elevator": math.radians(de_deg), "aileron": 0.0, "rudder": 0.0},
                geom,
            )
            lift_err = abs(sample.force_body_n[2] - target_lift)
            moment_err = abs(sample.moment_body_nm[1])
            score = lift_err + 8.0 * moment_err
            if best is None or score < best[0]:
                best = (score, alpha_deg, de_deg)
    assert best is not None
    return {
        "speed_mps": float(speed_mps),
        "altitude_m": float(altitude_m),
        "alpha_deg": best[1],
        "pitch_deg": best[1],
        "elevator_deg": best[2],
        "quaternion": from_euler(0.0, math.radians(best[1]), 0.0).tolist(),
        "residual_score": best[0],
    }


def numerical_jacobian(fn: Any, x: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    y0 = np.array(fn(x), dtype=float)
    jac = np.zeros((len(y0), len(x)), dtype=float)
    for i in range(len(x)):
        xp = x.copy()
        xm = x.copy()
        xp[i] += eps
        xm[i] -= eps
        jac[:, i] = (np.array(fn(xp), dtype=float) - np.array(fn(xm), dtype=float)) / (2.0 * eps)
    return jac


def write_trim_result(result: dict[str, Any], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "trim.json").write_text(json.dumps(result, indent=2))

