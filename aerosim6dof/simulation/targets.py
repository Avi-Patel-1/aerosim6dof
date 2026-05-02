"""Independent target object state and relative intercept telemetry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from aerosim6dof.core.vectors import vec3


TARGET_MODES = {"waypoint", "target_intercept", "proportional_navigation"}


@dataclass(frozen=True)
class TargetObject:
    target_id: str
    initial_position_m: np.ndarray
    velocity_mps: np.ndarray
    start_s: float = 0.0
    end_s: float = 1e99

    def active(self, t: float) -> bool:
        return self.start_s <= t <= self.end_s

    def position(self, t: float) -> np.ndarray:
        elapsed = max(0.0, t - self.start_s)
        return self.initial_position_m + self.velocity_mps * elapsed


class TargetSuite:
    """Owns non-vehicle target objects without feeding back into dynamics."""

    def __init__(self, targets: list[TargetObject] | None = None):
        self.targets = targets or []

    @classmethod
    def from_scenario(cls, scenario: Any) -> "TargetSuite":
        raw = getattr(scenario, "raw", {})
        guidance = getattr(scenario, "guidance", {})
        configured_targets = raw.get("targets", []) if isinstance(raw, dict) else []
        targets = [
            target
            for index, item in enumerate(_target_items(configured_targets))
            if (target := _target_from_config(item, index)) is not None
        ]
        if not targets and isinstance(guidance, dict) and (
            "target_position_m" in guidance or str(guidance.get("mode", "")) in TARGET_MODES
        ):
            targets.append(
                TargetObject(
                    target_id=str(guidance.get("target_id", "guidance_target")),
                    initial_position_m=vec3(guidance.get("target_position_m"), (1000.0, 0.0, 0.0)),
                    velocity_mps=vec3(guidance.get("target_velocity_mps"), (0.0, 0.0, 0.0)),
                    start_s=0.0,
                    end_s=1e99,
                )
            )
        return cls(targets)

    def sample(self, t: float, vehicle_position_m: np.ndarray, vehicle_velocity_mps: np.ndarray) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        closest: dict[str, Any] | None = None
        for target in self.targets:
            position = target.position(t)
            rel = position - vehicle_position_m
            rel_vel = target.velocity_mps - vehicle_velocity_mps
            distance = float(np.linalg.norm(rel))
            range_rate = float(rel @ rel_vel / max(distance, 1e-9))
            closing_speed = -range_rate
            active = target.active(t)
            row = {
                "time_s": float(t),
                "target_id": target.target_id,
                "target_active": 1.0 if active else 0.0,
                "target_x_m": float(position[0]),
                "target_y_m": float(position[1]),
                "target_z_m": float(position[2]),
                "target_vx_mps": float(target.velocity_mps[0]),
                "target_vy_mps": float(target.velocity_mps[1]),
                "target_vz_mps": float(target.velocity_mps[2]),
                "target_range_m": distance,
                "target_range_rate_mps": range_rate,
                "closing_speed_mps": closing_speed,
                "relative_x_m": float(rel[0]),
                "relative_y_m": float(rel[1]),
                "relative_z_m": float(rel[2]),
            }
            rows.append(row)
            if active and (closest is None or distance < float(closest["target_range_m"])):
                closest = row
        return self._summary(closest), rows

    def _summary(self, closest: dict[str, Any] | None) -> dict[str, Any]:
        if closest is None:
            nan = float("nan")
            return {
                "target_count": float(len(self.targets)),
                "target_id": "",
                "target_active": 0.0,
                "target_x_m": nan,
                "target_y_m": nan,
                "target_z_m": nan,
                "target_vx_mps": nan,
                "target_vy_mps": nan,
                "target_vz_mps": nan,
                "target_range_m": nan,
                "target_range_rate_mps": nan,
                "closing_speed_mps": nan,
                "relative_x_m": nan,
                "relative_y_m": nan,
                "relative_z_m": nan,
            }
        return {"target_count": float(len(self.targets)), **closest}


def _target_items(configured: Any) -> list[dict[str, Any]]:
    if isinstance(configured, dict):
        return [configured]
    if isinstance(configured, list):
        return [item for item in configured if isinstance(item, dict)]
    return []


def _target_from_config(config: dict[str, Any], index: int) -> TargetObject | None:
    try:
        return TargetObject(
            target_id=str(config.get("id", config.get("name", f"target_{index + 1}"))),
            initial_position_m=vec3(config.get("position_m", config.get("initial_position_m")), (0.0, 0.0, 0.0)),
            velocity_mps=vec3(config.get("velocity_mps"), (0.0, 0.0, 0.0)),
            start_s=_finite(config.get("start_s"), 0.0),
            end_s=_finite(config.get("end_s"), 1e99),
        )
    except (TypeError, ValueError):
        return None


def _finite(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default
