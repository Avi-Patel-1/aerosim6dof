"""Radar altimeter model."""

from __future__ import annotations

from typing import Any

import numpy as np


class RadarAltimeterSensor:
    """Range-to-ground sensor with max range, noise, and dropout."""

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.noise_m = float(cfg.get("noise_std_m", 0.25))
        self.bias_m = float(cfg.get("bias_m", 0.0))
        self.max_range_m = float(cfg.get("max_range_m", 2500.0))
        self.dropout_probability = float(cfg.get("dropout_probability", 0.0))

    def sample(self, rng: np.random.Generator, agl_m: float, extra_bias_m: float = 0.0, dropout: bool = False) -> dict[str, float]:
        if dropout or agl_m < 0.0 or agl_m > self.max_range_m or rng.random() < self.dropout_probability:
            return {"radar_valid": 0.0}
        value = agl_m + self.bias_m + extra_bias_m + float(rng.normal(0.0, self.noise_m))
        return {"radar_valid": 1.0, "radar_agl_m": float(max(0.0, value))}
