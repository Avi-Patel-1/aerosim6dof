"""IMU sensor model."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from aerosim6dof.core.vectors import vec3


class IMUSensor:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.accel_noise = float(cfg.get("accel_noise_std_mps2", cfg.get("imu_noise_std", 0.04)))
        self.gyro_noise = float(cfg.get("gyro_noise_std_rps", self.accel_noise * 0.05))
        self.accel_bias = vec3(cfg.get("accel_bias_mps2"), (0.0, 0.0, 0.0))
        self.gyro_bias = vec3(cfg.get("gyro_bias_rps"), (0.0, 0.0, 0.0))
        self.accel_walk = vec3(cfg.get("accel_random_walk_mps2"), (0.0, 0.0, 0.0))
        self.gyro_walk = vec3(cfg.get("gyro_random_walk_rps"), (0.0, 0.0, 0.0))
        self.accel_scale = _scale_vector(cfg.get("accel_scale_factor"), 1.0)
        self.gyro_scale = _scale_vector(cfg.get("gyro_scale_factor"), 1.0)
        self.accel_transform = _misalignment_matrix(vec3(cfg.get("accel_misalignment_deg"), (0.0, 0.0, 0.0)))
        self.gyro_transform = _misalignment_matrix(vec3(cfg.get("gyro_misalignment_deg"), (0.0, 0.0, 0.0)))
        self.accel_saturation = float(cfg.get("accel_saturation_mps2", cfg.get("saturation_mps2", 500.0)))
        self.gyro_saturation = float(cfg.get("gyro_saturation_rps", cfg.get("saturation_rps", 20.0)))

    def sample(
        self,
        rng: np.random.Generator,
        accel_body_mps2: np.ndarray,
        rates_rps: np.ndarray,
        dt: float,
        extra_accel_bias_mps2: np.ndarray | None = None,
        extra_gyro_bias_rps: np.ndarray | None = None,
        dropout: bool = False,
    ) -> dict[str, float]:
        if dropout:
            return {"imu_valid": 0.0}
        self.accel_bias += rng.normal(0.0, self.accel_walk * math.sqrt(max(dt, 0.0)), 3)
        self.gyro_bias += rng.normal(0.0, self.gyro_walk * math.sqrt(max(dt, 0.0)), 3)
        accel_bias = self.accel_bias + (extra_accel_bias_mps2 if extra_accel_bias_mps2 is not None else 0.0)
        gyro_bias = self.gyro_bias + (extra_gyro_bias_rps if extra_gyro_bias_rps is not None else 0.0)
        accel = self.accel_transform @ (accel_body_mps2 * self.accel_scale + accel_bias)
        gyro = self.gyro_transform @ (rates_rps * self.gyro_scale + gyro_bias)
        accel = accel + rng.normal(0.0, self.accel_noise, 3)
        gyro = gyro + rng.normal(0.0, self.gyro_noise, 3)
        accel = np.clip(accel, -self.accel_saturation, self.accel_saturation)
        gyro = np.clip(gyro, -self.gyro_saturation, self.gyro_saturation)
        return {
            "imu_valid": 1.0,
            "imu_ax_mps2": float(accel[0]),
            "imu_ay_mps2": float(accel[1]),
            "imu_az_mps2": float(accel[2]),
            "gyro_p_rps": float(gyro[0]),
            "gyro_q_rps": float(gyro[1]),
            "gyro_r_rps": float(gyro[2]),
            "imu_accel_norm_mps2": float(np.linalg.norm(accel)),
            "imu_gyro_norm_rps": float(np.linalg.norm(gyro)),
        }


def _scale_vector(value: Any, default: float) -> np.ndarray:
    if value is None:
        return np.full(3, default, dtype=float)
    if isinstance(value, (int, float)):
        return np.full(3, float(value), dtype=float)
    return vec3(value, (default, default, default))


def _misalignment_matrix(deg: np.ndarray) -> np.ndarray:
    rx, ry, rz = np.deg2rad(deg)
    return np.array(
        [
            [1.0, -rz, ry],
            [rz, 1.0, -rx],
            [-ry, rx, 1.0],
        ],
        dtype=float,
    )
