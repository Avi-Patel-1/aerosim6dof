"""Event detection."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventDetector:
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.max_altitude_m = -1e99
        self.max_altitude_time_s = 0.0
        self.previous_vz_mps: float | None = None
        self.burnout_seen = False
        self.apogee_seen = False
        self.ground_seen = False
        self.qbar_seen = False
        self.load_seen = False
        self.saturation_seen: set[str] = set()
        self.target_seen = False
        self.closest_target_distance_m = float("inf")
        self.closest_target_time_s = 0.0
        self.closest_target_id = ""

    def update(self, row: dict[str, Any], controls: dict[str, Any], above_ground_m: float, contact: dict[str, Any] | None = None) -> bool:
        t = float(row["time_s"])
        alt = float(row["altitude_m"])
        if alt > self.max_altitude_m:
            self.max_altitude_m = alt
            self.max_altitude_time_s = t
        if not self.burnout_seen and float(row.get("thrust_n", 0.0)) <= 1e-6 and t > 0.1:
            self._add(t, "burnout", "Propulsion thrust reached zero.")
            self.burnout_seen = True
        vz = float(row.get("vz_mps", 0.0))
        if self.previous_vz_mps is not None and self.previous_vz_mps > 0.0 and vz <= 0.0 and not self.apogee_seen:
            self._add(t, "apogee", "Vertical velocity crossed through zero.")
            self.apogee_seen = True
        self.previous_vz_mps = vz
        qbar_limit = float(self.config.get("qbar_limit_pa", 80_000.0))
        if not self.qbar_seen and float(row.get("qbar_pa", 0.0)) > qbar_limit:
            self._add(t, "qbar_exceedance", f"Dynamic pressure exceeded {qbar_limit:.0f} Pa.")
            self.qbar_seen = True
        load_limit = float(self.config.get("load_limit_g", 12.0))
        if not self.load_seen and float(row.get("load_factor_g", 0.0)) > load_limit:
            self._add(t, "load_factor_exceedance", f"Load factor exceeded {load_limit:.1f} g.")
            self.load_seen = True
        for surface in ("elevator", "aileron", "rudder"):
            key = f"{surface}_saturated"
            if controls.get(key, False) and surface not in self.saturation_seen:
                self._add(t, "actuator_saturation", f"{surface} reached its command or rate limit.")
                self.saturation_seen.add(surface)
        miss = _target_distance(row)
        threshold = float(self.config.get("target_threshold_m", 25.0))
        if math.isfinite(miss) and miss < self.closest_target_distance_m:
            self.closest_target_distance_m = miss
            self.closest_target_time_s = t
            self.closest_target_id = str(row.get("target_id", ""))
        if math.isfinite(miss) and miss <= threshold and not self.target_seen:
            self._add(t, "target_crossing", f"Target distance fell below {threshold:.1f} m.", target_id=str(row.get("target_id", "")), miss_distance_m=miss)
            self.target_seen = True
        if above_ground_m <= 0.0 and t > 0.0 and not self.ground_seen:
            contact_data = contact or {}
            state = str(contact_data.get("ground_contact_state", "impact"))
            impact_speed = _finite(contact_data.get("impact_speed_mps"), max(0.0, -float(row.get("vz_mps", 0.0))))
            agl_rate = _finite(contact_data.get("altitude_agl_rate_mps"), float(row.get("vz_mps", 0.0)))
            self._add(
                t,
                "ground_impact",
                f"Vehicle contacted terrain: {state} at {impact_speed:.2f} m/s sink rate.",
                classification=state,
                impact_speed_mps=impact_speed,
                altitude_agl_rate_mps=agl_rate,
            )
            self.ground_seen = True
            return bool(contact_data.get("ground_contact_stop", True))
        return False

    def finalize(self) -> list[dict[str, Any]]:
        if math.isfinite(self.closest_target_distance_m):
            self._add(
                self.closest_target_time_s,
                "closest_approach",
                f"Closest target approach was {self.closest_target_distance_m:.2f} m.",
                target_id=self.closest_target_id,
                miss_distance_m=self.closest_target_distance_m,
            )
        self._add(self.max_altitude_time_s, "max_altitude", f"Maximum altitude was {self.max_altitude_m:.2f} m.")
        return sorted(self.events, key=lambda e: float(e["time_s"]))

    def _add(self, t: float, event_type: str, description: str, **extra: Any) -> None:
        self.events.append({"time_s": float(t), "type": event_type, "description": description, **extra})


def _finite(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _target_distance(row: dict[str, Any]) -> float:
    target_range = _finite(row.get("target_range_m"), float("inf"))
    if math.isfinite(target_range):
        return target_range
    return _finite(row.get("target_distance_m"), float("inf"))
