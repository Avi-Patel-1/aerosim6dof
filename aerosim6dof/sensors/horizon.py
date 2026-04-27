"""Horizon sensor approximation."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from aerosim6dof.core.quaternions import to_euler


class HorizonSensor:
    """Roll/pitch attitude aid with noise, bias, field-of-view limit, and dropout."""

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.noise_rad = math.radians(float(cfg.get("noise_std_deg", 0.35)))
        self.roll_bias_rad = math.radians(float(cfg.get("roll_bias_deg", 0.0)))
        self.pitch_bias_rad = math.radians(float(cfg.get("pitch_bias_deg", 0.0)))
        self.max_tilt_rad = math.radians(float(cfg.get("max_tilt_deg", 80.0)))

    def sample(self, rng: np.random.Generator, quaternion: np.ndarray, dropout: bool = False) -> dict[str, float]:
        roll, pitch, _ = to_euler(quaternion)
        if dropout or abs(roll) > self.max_tilt_rad or abs(pitch) > self.max_tilt_rad:
            return {"horizon_valid": 0.0}
        measured_roll = roll + self.roll_bias_rad + float(rng.normal(0.0, self.noise_rad))
        measured_pitch = pitch + self.pitch_bias_rad + float(rng.normal(0.0, self.noise_rad))
        return {
            "horizon_valid": 1.0,
            "horizon_roll_deg": math.degrees(measured_roll),
            "horizon_pitch_deg": math.degrees(measured_pitch),
        }
