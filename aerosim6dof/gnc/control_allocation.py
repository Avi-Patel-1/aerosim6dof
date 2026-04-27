"""Control allocation."""

from __future__ import annotations


def allocate(body_axis_commands: dict[str, float], limits: dict[str, float] | None = None) -> dict[str, float]:
    """Map roll/pitch/yaw commands to surface commands."""

    lim = limits or {}
    def sat(name: str, value: float) -> float:
        limit = abs(float(lim.get(name, lim.get("surface", 0.45))))
        return max(-limit, min(limit, float(value)))

    return {
        "elevator": sat("elevator", body_axis_commands.get("pitch", 0.0)),
        "aileron": sat("aileron", body_axis_commands.get("roll", 0.0)),
        "rudder": sat("rudder", body_axis_commands.get("yaw", 0.0)),
    }

