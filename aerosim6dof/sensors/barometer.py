"""Barometric altitude model."""

from __future__ import annotations

from typing import Any

import numpy as np


class BarometerSensor:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.noise = float(cfg.get("noise_std_m", cfg.get("baro_noise_std_m", 0.7)))
        self.bias = float(cfg.get("bias_m", 0.0))
        self.drift_rate_mps = float(cfg.get("drift_rate_mps", cfg.get("weather_drift_mps", 0.0)))
        self.saturation_min_m = float(cfg.get("saturation_min_m", -1000.0))
        self.saturation_max_m = float(cfg.get("saturation_max_m", 100000.0))

    def sample(
        self,
        rng: np.random.Generator,
        altitude_m: float,
        dt: float = 0.0,
        extra_bias_m: float = 0.0,
        dropout: bool = False,
    ) -> dict[str, float]:
        if dropout:
            return {"baro_valid": 0.0}
        self.bias += self.drift_rate_mps * max(dt, 0.0)
        measured = altitude_m + self.bias + extra_bias_m + float(rng.normal(0.0, self.noise))
        measured = min(self.saturation_max_m, max(self.saturation_min_m, measured))
        return {"baro_valid": 1.0, "baro_alt_m": float(measured), "baro_bias_m": float(self.bias + extra_bias_m)}
