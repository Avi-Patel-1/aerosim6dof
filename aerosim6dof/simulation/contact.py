"""Terrain-coupled ground contact helpers."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from aerosim6dof.environment.terrain import TerrainModel
from aerosim6dof.vehicle.state import VehicleState


class GroundContactModel:
    """Classify terrain contact and optionally apply guarded contact response."""

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config if isinstance(config, dict) else {}
        self.enabled = _bool(cfg.get("enabled", False))
        self.mode = str(cfg.get("mode", "terminate")).lower()
        self.stop_on_contact = _bool(cfg.get("stop_on_contact", True))
        self.stop_on_crash = _bool(cfg.get("stop_on_crash", True))
        self.ground_tolerance_m = max(_float(cfg.get("ground_tolerance_m"), 0.0), 0.0)
        self.ground_clearance_m = max(_float(cfg.get("ground_clearance_m"), 0.0), 0.0)
        self.touchdown_speed_mps = max(_float(cfg.get("touchdown_speed_mps"), 2.0), 0.0)
        self.impact_speed_mps = max(_float(cfg.get("impact_speed_mps"), 8.0), self.touchdown_speed_mps)
        self.crash_speed_mps = max(_float(cfg.get("crash_speed_mps"), 25.0), self.impact_speed_mps)
        self.restitution = min(max(_float(cfg.get("restitution", cfg.get("bounce_restitution")), 0.18), 0.0), 0.9)
        self.friction = min(max(_float(cfg.get("friction", 0.35), 0.35), 0.0), 1.0)

    def evaluate(self, terrain_state: dict[str, float]) -> dict[str, Any]:
        agl = _float(terrain_state.get("altitude_agl_m"), 0.0)
        agl_rate = _float(terrain_state.get("altitude_agl_rate_mps"), 0.0)
        sink_rate = max(0.0, -agl_rate)
        in_contact = agl <= self.ground_tolerance_m
        state, severity = self._classification(in_contact, sink_rate)
        return {
            "terrain_slope_x": _float(terrain_state.get("terrain_slope_x"), 0.0),
            "terrain_slope_y": _float(terrain_state.get("terrain_slope_y"), 0.0),
            "terrain_slope_deg": _float(terrain_state.get("terrain_slope_deg"), 0.0),
            "terrain_rate_mps": _float(terrain_state.get("terrain_rate_mps"), 0.0),
            "altitude_agl_rate_mps": agl_rate,
            "ground_contact": 1.0 if in_contact else 0.0,
            "ground_contact_state": state,
            "ground_contact_severity": float(severity),
            "impact_speed_mps": sink_rate if in_contact else 0.0,
            "ground_contact_stop": self._should_stop(in_contact, state),
            "ground_contact_mode": self.mode if self.enabled else "event_only",
        }

    def apply(self, state: VehicleState, terrain: TerrainModel) -> tuple[VehicleState, dict[str, Any]]:
        """Clamp or bounce a post-step state only when contact response is enabled."""
        if not self.enabled or self.mode not in {"bounce", "slide", "settle"}:
            return state, {"ground_contact_action": "none"}
        terrain_state = terrain.query(state.position_m, state.velocity_mps)
        contact = self.evaluate(terrain_state)
        if not contact["ground_contact"] or contact["ground_contact_state"] == "crash":
            return state, {"ground_contact_action": "none"}

        nxt = state.copy()
        terrain_height = terrain_state["terrain_elevation_m"] + self.ground_clearance_m
        nxt.position_m[2] = max(float(nxt.position_m[2]), terrain_height)

        normal = np.array([-terrain_state["terrain_slope_x"], -terrain_state["terrain_slope_y"], 1.0], dtype=float)
        norm = float(np.linalg.norm(normal))
        if norm <= 1e-12:
            normal = np.array([0.0, 0.0, 1.0], dtype=float)
        else:
            normal = normal / norm
        normal_speed = float(nxt.velocity_mps @ normal)
        normal_velocity = normal_speed * normal
        tangential_velocity = nxt.velocity_mps - normal_velocity
        damped_tangent = tangential_velocity * (1.0 - self.friction)

        if self.mode == "bounce" and normal_speed < 0.0:
            nxt.velocity_mps = damped_tangent - self.restitution * normal_speed * normal
            action = "bounce"
        elif self.mode in {"slide", "settle"}:
            nxt.velocity_mps = damped_tangent
            action = self.mode
        else:
            nxt.velocity_mps = state.velocity_mps
            action = "none"
        return nxt, {"ground_contact_action": action}

    def _classification(self, in_contact: bool, sink_rate_mps: float) -> tuple[str, int]:
        if not in_contact:
            return "airborne", 0
        if sink_rate_mps <= self.touchdown_speed_mps:
            return "touchdown", 1
        if sink_rate_mps <= self.impact_speed_mps:
            return "impact", 2
        if sink_rate_mps <= self.crash_speed_mps:
            return "hard_impact", 2
        return "crash", 3

    def _should_stop(self, in_contact: bool, state: str) -> bool:
        if not in_contact:
            return False
        if state == "crash" and self.stop_on_crash:
            return True
        if self.enabled and self.mode in {"bounce", "slide", "settle"}:
            return False
        return self.stop_on_contact


def ground_contact_config(scenario: Any) -> dict[str, Any]:
    """Merge environment and event-level ground contact config."""
    environment = getattr(scenario, "environment", {})
    events = getattr(scenario, "events", {})
    env_cfg = environment.get("ground_contact", {}) if isinstance(environment, dict) else {}
    event_cfg = events.get("ground_contact", {}) if isinstance(events, dict) else {}
    merged: dict[str, Any] = {}
    if isinstance(env_cfg, dict):
        merged.update(env_cfg)
    if isinstance(event_cfg, dict):
        merged.update(event_cfg)
    return merged


def _float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)
