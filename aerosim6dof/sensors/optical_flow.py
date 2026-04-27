"""Optical-flow style ground motion sensor."""

from __future__ import annotations

from typing import Any

import numpy as np


class OpticalFlowSensor:
    """Small-angle optical flow derived from body-frame translational velocity."""

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.noise_radps = float(cfg.get("noise_std_radps", 0.01))
        self.max_rate_radps = float(cfg.get("max_rate_radps", 6.0))
        self.min_agl_m = float(cfg.get("min_agl_m", 0.5))
        self.max_agl_m = float(cfg.get("max_agl_m", 400.0))

    def sample(self, rng: np.random.Generator, velocity_body_mps: np.ndarray, agl_m: float, dropout: bool = False) -> dict[str, float]:
        if dropout or agl_m < self.min_agl_m or agl_m > self.max_agl_m:
            return {"optical_flow_valid": 0.0}
        denom = max(self.min_agl_m, agl_m)
        flow_x = -float(velocity_body_mps[1]) / denom
        flow_y = float(velocity_body_mps[0]) / denom
        flow = np.array([flow_x, flow_y], dtype=float) + rng.normal(0.0, self.noise_radps, 2)
        flow = np.clip(flow, -self.max_rate_radps, self.max_rate_radps)
        quality = max(0.0, min(1.0, 1.0 - agl_m / max(self.max_agl_m, 1.0)))
        return {
            "optical_flow_valid": 1.0,
            "optical_flow_x_radps": float(flow[0]),
            "optical_flow_y_radps": float(flow[1]),
            "optical_flow_quality": float(quality),
        }
