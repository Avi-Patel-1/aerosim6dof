"""Terrain height queries for ground-relative simulation quantities."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


class TerrainModel:
    """Configurable terrain model with a flat default.

    Supported config stays backward compatible with the original plane model:
    ``base_altitude_m``, ``slope_x``, and ``slope_y``. New terrain can be added
    with inline grid data or analytic features without changing the integrator.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config if isinstance(config, dict) else {}
        self.enabled = _bool(cfg.get("enabled", True))
        self.base_altitude_m = _float(cfg.get("base_altitude_m"), 0.0)
        self.slope_x = _float(cfg.get("slope_x"), 0.0)
        self.slope_y = _float(cfg.get("slope_y"), 0.0)
        self.features = [feature for feature in cfg.get("features", []) if isinstance(feature, dict)]
        grid = cfg.get("grid", {})
        if not isinstance(grid, dict):
            grid = {}
        self.grid_x = _array(grid.get("x_m", cfg.get("grid_x_m")))
        self.grid_y = _array(grid.get("y_m", cfg.get("grid_y_m")))
        elevations = grid.get("elevation_m", grid.get("elevations_m", cfg.get("grid_elevation_m")))
        self.grid_z = _grid(elevations)
        self.grid_extrapolate = str(grid.get("extrapolate", cfg.get("grid_extrapolate", "clamp"))).lower()
        has_valid_grid = self.grid_x is not None and self.grid_y is not None and self.grid_z is not None
        default_kind = "grid" if has_valid_grid else "plane"
        self.kind = str(cfg.get("type", cfg.get("model", default_kind))).lower()

    def elevation(self, position_m: np.ndarray) -> float:
        if not self.enabled:
            return 0.0
        x = float(position_m[0])
        y = float(position_m[1])
        value = self.base_altitude_m + self.slope_x * x + self.slope_y * y
        if self.kind == "grid":
            grid_value = self._grid_elevation(x, y)
            if grid_value is not None:
                value += grid_value
        for feature in self.features:
            value += self._feature_elevation(feature, x, y)
        return float(value)

    def above_ground(self, position_m: np.ndarray) -> float:
        return float(position_m[2]) - self.elevation(position_m)

    def gradient(self, position_m: np.ndarray, step_m: float = 1.0) -> tuple[float, float]:
        """Return terrain height gradients dZ/dX and dZ/dY at a position."""
        if not self.enabled:
            return 0.0, 0.0
        step = max(float(step_m), 1e-3)
        x_forward = np.array(position_m, dtype=float)
        x_back = np.array(position_m, dtype=float)
        y_forward = np.array(position_m, dtype=float)
        y_back = np.array(position_m, dtype=float)
        x_forward[0] += step
        x_back[0] -= step
        y_forward[1] += step
        y_back[1] -= step
        dz_dx = (self.elevation(x_forward) - self.elevation(x_back)) / (2.0 * step)
        dz_dy = (self.elevation(y_forward) - self.elevation(y_back)) / (2.0 * step)
        return float(dz_dx), float(dz_dy)

    def query(self, position_m: np.ndarray, velocity_mps: np.ndarray | None = None) -> dict[str, float]:
        elevation = self.elevation(position_m)
        slope_x, slope_y = self.gradient(position_m)
        terrain_rate = 0.0
        agl_rate = float("nan")
        if velocity_mps is not None:
            terrain_rate = slope_x * float(velocity_mps[0]) + slope_y * float(velocity_mps[1])
            agl_rate = float(velocity_mps[2]) - terrain_rate
        return {
            "terrain_elevation_m": elevation,
            "altitude_agl_m": float(position_m[2]) - elevation,
            "terrain_slope_x": slope_x,
            "terrain_slope_y": slope_y,
            "terrain_slope_deg": math.degrees(math.atan((slope_x * slope_x + slope_y * slope_y) ** 0.5)),
            "terrain_rate_mps": float(terrain_rate),
            "altitude_agl_rate_mps": agl_rate,
        }

    def _grid_elevation(self, x: float, y: float) -> float | None:
        if self.grid_x is None or self.grid_y is None or self.grid_z is None:
            return None
        if len(self.grid_x) < 2 or len(self.grid_y) < 2:
            return None
        if self.grid_z.shape != (len(self.grid_y), len(self.grid_x)):
            return None
        if self.grid_extrapolate == "flat" and (
            x < self.grid_x[0] or x > self.grid_x[-1] or y < self.grid_y[0] or y > self.grid_y[-1]
        ):
            return 0.0
        xq = float(np.clip(x, self.grid_x[0], self.grid_x[-1]))
        yq = float(np.clip(y, self.grid_y[0], self.grid_y[-1]))
        ix = int(np.searchsorted(self.grid_x, xq, side="right") - 1)
        iy = int(np.searchsorted(self.grid_y, yq, side="right") - 1)
        ix = max(0, min(ix, len(self.grid_x) - 2))
        iy = max(0, min(iy, len(self.grid_y) - 2))
        x0, x1 = float(self.grid_x[ix]), float(self.grid_x[ix + 1])
        y0, y1 = float(self.grid_y[iy]), float(self.grid_y[iy + 1])
        tx = 0.0 if abs(x1 - x0) < 1e-12 else (xq - x0) / (x1 - x0)
        ty = 0.0 if abs(y1 - y0) < 1e-12 else (yq - y0) / (y1 - y0)
        z00 = float(self.grid_z[iy, ix])
        z10 = float(self.grid_z[iy, ix + 1])
        z01 = float(self.grid_z[iy + 1, ix])
        z11 = float(self.grid_z[iy + 1, ix + 1])
        return (
            (1.0 - tx) * (1.0 - ty) * z00
            + tx * (1.0 - ty) * z10
            + (1.0 - tx) * ty * z01
            + tx * ty * z11
        )

    def _feature_elevation(self, feature: dict[str, Any], x: float, y: float) -> float:
        kind = str(feature.get("type", "hill")).lower()
        if kind in {"hill", "gaussian_hill"}:
            center = feature.get("center_m", [0.0, 0.0])
            has_center = isinstance(center, (list, tuple))
            default_x = _float(feature.get("x_m"), 0.0)
            default_y = _float(feature.get("y_m"), 0.0)
            cx = _float(center[0], default_x) if has_center and len(center) > 0 else default_x
            cy = _float(center[1], default_y) if has_center and len(center) > 1 else default_y
            height = _float(feature.get("height_m", feature.get("amplitude_m")), 0.0)
            radius = max(_float(feature.get("radius_m"), 1.0), 1e-6)
            r2 = (x - cx) ** 2 + (y - cy) ** 2
            return height * math.exp(-0.5 * r2 / (radius * radius))
        if kind == "ridge":
            axis = str(feature.get("axis", "y")).lower()
            coordinate = y if axis == "y" else x
            center = _float(feature.get("center_m"), 0.0)
            height = _float(feature.get("height_m", feature.get("amplitude_m")), 0.0)
            half_width = max(_float(feature.get("half_width_m", feature.get("width_m")), 1.0), 1e-6)
            distance = abs(coordinate - center)
            return height * max(0.0, 1.0 - distance / half_width)
        if kind in {"sinusoid", "sine"}:
            amplitude = _float(feature.get("amplitude_m"), 0.0)
            wavelength = max(_float(feature.get("wavelength_m"), 1.0), 1e-6)
            axis = str(feature.get("axis", "x")).lower()
            coordinate = y if axis == "y" else x
            phase = _float(feature.get("phase_rad"), 0.0)
            return amplitude * math.sin((2.0 * math.pi * coordinate / wavelength) + phase)
        return 0.0


def _float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        array = np.array(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        return None
    if np.any(np.diff(array) <= 0.0):
        return None
    return array


def _grid(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        array = np.array(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim != 2 or array.size == 0 or not np.all(np.isfinite(array)):
        return None
    return array
