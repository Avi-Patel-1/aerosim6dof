"""Integrator utilities."""

from __future__ import annotations

from typing import Callable

import numpy as np

Derivative = Callable[[float, np.ndarray], np.ndarray]


def euler_step(fn: Derivative, t: float, y: np.ndarray, dt: float) -> np.ndarray:
    return y + fn(t, y) * dt


def rk2_step(fn: Derivative, t: float, y: np.ndarray, dt: float) -> np.ndarray:
    """Second-order midpoint Runge-Kutta step."""

    k1 = fn(t, y)
    k2 = fn(t + 0.5 * dt, y + 0.5 * dt * k1)
    return y + dt * k2


def rk4_step(fn: Derivative, t: float, y: np.ndarray, dt: float) -> np.ndarray:
    k1 = fn(t, y)
    k2 = fn(t + 0.5 * dt, y + 0.5 * dt * k1)
    k3 = fn(t + 0.5 * dt, y + 0.5 * dt * k2)
    k4 = fn(t + dt, y + dt * k3)
    return y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def adaptive_rk45_step(
    fn: Derivative,
    t: float,
    y: np.ndarray,
    dt: float,
    tolerance: float = 1e-6,
    min_dt: float = 1e-5,
    max_rejections: int = 12,
) -> tuple[np.ndarray, float, int]:
    """Advance one requested interval with step-doubling RK4 error control.

    This is an RK45-like adaptive wrapper using one full RK4 step versus two
    half steps as the embedded error estimate. It is deterministic, compact,
    and sufficient for scenario-level step rejection without adding
    dependencies.
    """

    remaining = float(dt)
    current_t = float(t)
    current_y = y.copy()
    max_error = 0.0
    rejections = 0
    h = float(dt)
    while remaining > 1e-12:
        h = min(h, remaining)
        full = rk4_step(fn, current_t, current_y, h)
        half = rk4_step(fn, current_t, current_y, 0.5 * h)
        half = rk4_step(fn, current_t + 0.5 * h, half, 0.5 * h)
        err = float(np.linalg.norm(half - full) / max(1.0, np.linalg.norm(half)))
        if err <= tolerance or h <= min_dt:
            current_y = half
            current_t += h
            remaining -= h
            max_error = max(max_error, err)
            if err < tolerance * 0.1:
                h *= 1.6
        else:
            h *= 0.5
            rejections += 1
            if rejections > max_rejections:
                current_y = half
                current_t += h
                remaining -= h
                max_error = max(max_error, err)
    return current_y, max_error, rejections
