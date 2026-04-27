"""Reference geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReferenceGeometry:
    area_m2: float = 0.052
    span_m: float = 0.32
    chord_m: float = 0.48

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "ReferenceGeometry":
        cfg = config or {}
        return cls(
            area_m2=float(cfg.get("area_m2", cls.area_m2)),
            span_m=float(cfg.get("span_m", cls.span_m)),
            chord_m=float(cfg.get("chord_m", cls.chord_m)),
        )

