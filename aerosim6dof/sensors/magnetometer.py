"""Magnetometer heading model."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from aerosim6dof.core.quaternions import to_dcm
from aerosim6dof.core.quaternions import to_euler
from aerosim6dof.core.vectors import vec3, wrap_pi


class MagnetometerSensor:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.noise_rad = math.radians(float(cfg.get("noise_std_deg", 1.0)))
        self.bias_rad = math.radians(float(cfg.get("bias_deg", 0.0)))
        self.field_strength_ut = float(cfg.get("field_strength_ut", 48.0))
        self.inclination_rad = math.radians(float(cfg.get("inclination_deg", 60.0)))
        self.declination_rad = math.radians(float(cfg.get("declination_deg", 0.0)))
        self.hard_iron_ut = vec3(cfg.get("hard_iron_ut"), (0.0, 0.0, 0.0))
        self.soft_iron = _soft_iron_matrix(cfg.get("soft_iron"), cfg.get("soft_iron_scale"))
        self.saturation_ut = float(cfg.get("saturation_ut", 200.0))

    def sample(self, rng: np.random.Generator, quaternion: np.ndarray, dropout: bool = False) -> dict[str, float]:
        if dropout:
            return {"mag_valid": 0.0}
        _, _, yaw = to_euler(quaternion)
        heading = wrap_pi(yaw + self.bias_rad + float(rng.normal(0.0, self.noise_rad)))
        field_inertial = self._field_inertial()
        field_body = to_dcm(quaternion).T @ field_inertial
        field_body = self.soft_iron @ field_body + self.hard_iron_ut
        field_body = field_body + rng.normal(0.0, self.field_strength_ut * self.noise_rad * 0.05, 3)
        field_body = np.clip(field_body, -self.saturation_ut, self.saturation_ut)
        return {
            "mag_valid": 1.0,
            "mag_heading_deg": math.degrees(heading),
            "mag_x_ut": float(field_body[0]),
            "mag_y_ut": float(field_body[1]),
            "mag_z_ut": float(field_body[2]),
        }

    def _field_inertial(self) -> np.ndarray:
        h = self.field_strength_ut * math.cos(self.inclination_rad)
        return np.array(
            [
                h * math.cos(self.declination_rad),
                h * math.sin(self.declination_rad),
                -self.field_strength_ut * math.sin(self.inclination_rad),
            ],
            dtype=float,
        )


def _soft_iron_matrix(matrix: Any, scale: Any) -> np.ndarray:
    if matrix is not None:
        arr = np.asarray(matrix, dtype=float)
        if arr.shape == (3, 3):
            return arr
    if scale is not None:
        values = vec3(scale, (1.0, 1.0, 1.0))
        return np.diag(values)
    return np.eye(3)
