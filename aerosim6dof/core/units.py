"""Unit conversion helpers."""

from __future__ import annotations

import math


def deg_to_rad(value: float) -> float:
    return math.radians(float(value))


def rad_to_deg(value: float) -> float:
    return math.degrees(float(value))


def ft_to_m(value: float) -> float:
    return float(value) * 0.3048


def knots_to_mps(value: float) -> float:
    return float(value) * 0.514444

