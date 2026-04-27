"""Quaternion math using [w, x, y, z] ordering."""

from __future__ import annotations

import math

import numpy as np


def normalize(q: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(q))
    if n <= 0.0:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return q / n


def multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aw, ax, ay, az = normalize(a)
    bw, bx, by, bz = normalize(b)
    return np.array(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ],
        dtype=float,
    )


def conjugate(q: np.ndarray) -> np.ndarray:
    w, x, y, z = normalize(q)
    return np.array([w, -x, -y, -z], dtype=float)


def from_euler(roll: float, pitch: float, yaw: float) -> np.ndarray:
    # The simulator uses z-up coordinates and reports pitch positive nose-up.
    # A right-handed rotation about +body-y is nose-down in this frame, so the
    # internal quaternion stores the opposite pitch sign.
    pitch = -pitch
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return normalize(
        np.array(
            [
                cr * cp * cy + sr * sp * sy,
                sr * cp * cy - cr * sp * sy,
                cr * sp * cy + sr * cp * sy,
                cr * cp * sy - sr * sp * cy,
            ],
            dtype=float,
        )
    )


def to_euler(q: np.ndarray) -> tuple[float, float, float]:
    w, x, y, z = normalize(q)
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    sinp = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = -math.asin(sinp)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return roll, pitch, yaw


def to_dcm(q: np.ndarray) -> np.ndarray:
    """Direction cosine matrix mapping body-frame vectors into inertial frame."""

    w, x, y, z = normalize(q)
    return np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=float,
    )


def derivative(q: np.ndarray, omega_body_rps: np.ndarray) -> np.ndarray:
    w, x, y, z = normalize(q)
    p, q_rate, r = omega_body_rps
    return 0.5 * np.array(
        [
            -x * p - y * q_rate - z * r,
            w * p + y * r - z * q_rate,
            w * q_rate - x * r + z * p,
            w * r + x * q_rate - y * p,
        ],
        dtype=float,
    )


def integrate(q: np.ndarray, omega_body_rps: np.ndarray, dt: float) -> np.ndarray:
    return normalize(q + derivative(q, omega_body_rps) * dt)
