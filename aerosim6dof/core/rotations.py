"""Frame transform helpers."""

from __future__ import annotations

import numpy as np

from .quaternions import to_dcm


def body_to_inertial(q_body_to_inertial: np.ndarray, value_body: np.ndarray) -> np.ndarray:
    return to_dcm(q_body_to_inertial) @ value_body


def inertial_to_body(q_body_to_inertial: np.ndarray, value_inertial: np.ndarray) -> np.ndarray:
    return to_dcm(q_body_to_inertial).T @ value_inertial


def wind_relative_body_velocity(
    q_body_to_inertial: np.ndarray,
    velocity_inertial_mps: np.ndarray,
    wind_inertial_mps: np.ndarray,
) -> np.ndarray:
    return inertial_to_body(q_body_to_inertial, velocity_inertial_mps - wind_inertial_mps)

