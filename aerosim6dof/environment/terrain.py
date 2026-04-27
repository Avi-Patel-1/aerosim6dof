"""Simple terrain model for ground intercept checks."""

from __future__ import annotations

from typing import Any

import numpy as np


class TerrainModel:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.base_altitude_m = float(cfg.get("base_altitude_m", 0.0))
        self.slope_x = float(cfg.get("slope_x", 0.0))
        self.slope_y = float(cfg.get("slope_y", 0.0))

    def elevation(self, position_m: np.ndarray) -> float:
        return self.base_altitude_m + self.slope_x * float(position_m[0]) + self.slope_y * float(position_m[1])

    def above_ground(self, position_m: np.ndarray) -> float:
        return float(position_m[2]) - self.elevation(position_m)

