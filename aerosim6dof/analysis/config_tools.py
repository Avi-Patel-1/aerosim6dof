"""Configuration inspection, diffing, and template generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aerosim6dof.config import load_json
from aerosim6dof.reports.json_writer import write_json


def inspect_vehicle(vehicle_path: str | Path) -> dict[str, Any]:
    vehicle = load_json(vehicle_path)
    return {
        "name": vehicle.get("name", Path(vehicle_path).stem),
        "mass_kg": vehicle.get("mass_kg"),
        "dry_mass_kg": vehicle.get("dry_mass_kg"),
        "reference": vehicle.get("reference", {}),
        "has_propulsion": "propulsion" in vehicle,
        "has_aero": "aero" in vehicle,
        "actuator_surfaces": sorted(vehicle.get("actuators", {}).get("surfaces", {}).keys()),
        "warnings": _vehicle_warnings(vehicle),
    }


def config_diff(a_path: str | Path, b_path: str | Path) -> dict[str, Any]:
    a = load_json(a_path)
    b = load_json(b_path)
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    _diff("", a, b, added, removed, changed)
    return {"added": added, "removed": removed, "changed": changed}


def generate_scenario(
    out_path: str | Path,
    name: str,
    vehicle_config: str = "../vehicles/baseline.json",
    environment_config: str = "../environments/calm.json",
    guidance_mode: str = "pitch_program",
) -> dict[str, Any]:
    scenario = {
        "name": name,
        "dt": 0.03,
        "duration": 18.0,
        "integrator": "semi_implicit_euler",
        "vehicle_config": vehicle_config,
        "environment_config": environment_config,
        "initial": {
            "position_m": [0.0, 0.0, 50.0],
            "velocity_mps": [85.0, 0.0, 12.0],
            "euler_deg": [0.0, 8.0, 0.0],
            "body_rates_dps": [0.0, 0.0, 0.0],
        },
        "guidance": {
            "mode": guidance_mode,
            "pitch_program": [[0.0, 14.0], [8.0, 10.0], [16.0, 6.0]],
            "heading_command_deg": 0.0,
            "throttle": 0.85,
        },
        "sensors": {"seed": 1},
        "events": {"qbar_limit_pa": 90000.0, "load_limit_g": 12.0},
    }
    write_json(out_path, scenario)
    return scenario


def _vehicle_warnings(vehicle: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    mass = vehicle.get("mass_kg")
    dry = vehicle.get("dry_mass_kg")
    if mass is not None and dry is not None and float(dry) >= float(mass):
        warnings.append("dry mass should be less than loaded mass")
    for key in ("area_m2", "span_m", "chord_m"):
        if key not in vehicle.get("reference", {}):
            warnings.append(f"reference.{key} is missing")
    if "aero" not in vehicle:
        warnings.append("aero section is missing")
    if "propulsion" not in vehicle:
        warnings.append("propulsion section is missing")
    return warnings


def _diff(path: str, a: Any, b: Any, added: dict[str, Any], removed: dict[str, Any], changed: dict[str, Any]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            child = f"{path}.{key}" if path else str(key)
            if key not in a:
                added[child] = b[key]
            elif key not in b:
                removed[child] = a[key]
            else:
                _diff(child, a[key], b[key], added, removed, changed)
    elif a != b:
        changed[path] = {"from": a, "to": b}

