"""Aerodynamic coefficient database interpolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class AeroQuery:
    alpha_deg: float
    beta_deg: float
    mach: float


class AeroCoefficientDatabase:
    """Interpolate coefficient tables over alpha and Mach axes.

    The database format is intentionally JSON-friendly:

    ```json
    {
      "axes": {"alpha_deg": [-10, 0, 10], "mach": [0.2, 0.8]},
      "coefficients": {
        "cl": [[-0.5, -0.45], [0.0, 0.0], [0.6, 0.55]],
        "cd": [[0.16, 0.18], [0.08, 0.09], [0.17, 0.20]]
      }
    }
    ```

    Coefficient arrays may be one-dimensional over `alpha_deg` or two-dimensional
    with shape `(len(alpha_deg), len(mach))`.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        axes = self.config.get("axes", {})
        self.alpha_axis = _axis("alpha_deg", axes.get("alpha_deg", [-30.0, 0.0, 30.0]))
        self.mach_axis = _axis("mach", axes.get("mach", [0.0, 1.0]))
        self.coefficients = self.config.get("coefficients", {})

    def has_coefficients(self) -> bool:
        return bool(self.coefficients)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name, values in self.coefficients.items():
            arr = np.array(values, dtype=float)
            if arr.ndim == 1:
                if arr.shape[0] != len(self.alpha_axis):
                    errors.append(f"{name} 1D table length must match alpha_deg axis")
            elif arr.ndim == 2:
                if arr.shape != (len(self.alpha_axis), len(self.mach_axis)):
                    errors.append(f"{name} 2D table shape must be alpha_deg x mach")
            else:
                errors.append(f"{name} table must be 1D or 2D")
            if not np.all(np.isfinite(arr)):
                errors.append(f"{name} table contains non-finite values")
        return errors

    def interpolate(self, query: AeroQuery) -> dict[str, float]:
        out: dict[str, float] = {}
        for name, values in self.coefficients.items():
            arr = np.array(values, dtype=float)
            if arr.ndim == 1:
                out[name] = float(np.interp(query.alpha_deg, self.alpha_axis, arr))
            elif arr.ndim == 2:
                out[name] = _bilinear(query.alpha_deg, query.mach, self.alpha_axis, self.mach_axis, arr)
        return out


def _axis(name: str, values: Any) -> np.ndarray:
    arr = np.array(values, dtype=float)
    if arr.ndim != 1 or len(arr) < 2:
        raise ValueError(f"aero database axis {name} must contain at least two values")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"aero database axis {name} contains non-finite values")
    if np.any(np.diff(arr) <= 0.0):
        raise ValueError(f"aero database axis {name} must be strictly increasing")
    return arr


def _bilinear(x: float, y: float, xs: np.ndarray, ys: np.ndarray, values: np.ndarray) -> float:
    x_clamped = float(np.clip(x, xs[0], xs[-1]))
    y_clamped = float(np.clip(y, ys[0], ys[-1]))
    ix = int(np.searchsorted(xs, x_clamped, side="right") - 1)
    iy = int(np.searchsorted(ys, y_clamped, side="right") - 1)
    ix = max(0, min(ix, len(xs) - 2))
    iy = max(0, min(iy, len(ys) - 2))
    x0, x1 = xs[ix], xs[ix + 1]
    y0, y1 = ys[iy], ys[iy + 1]
    tx = (x_clamped - x0) / max(x1 - x0, 1e-12)
    ty = (y_clamped - y0) / max(y1 - y0, 1e-12)
    v00 = values[ix, iy]
    v10 = values[ix + 1, iy]
    v01 = values[ix, iy + 1]
    v11 = values[ix + 1, iy + 1]
    return float((1.0 - tx) * (1.0 - ty) * v00 + tx * (1.0 - ty) * v10 + (1.0 - tx) * ty * v01 + tx * ty * v11)

