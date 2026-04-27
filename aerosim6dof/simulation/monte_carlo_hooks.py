"""Small hooks for repeatable scenario perturbations."""

from __future__ import annotations

from typing import Any

import numpy as np

from aerosim6dof.config import deep_merge


def perturb_scenario(data: dict[str, Any], seed: int, dispersions: dict[str, float] | None = None) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    disp = dispersions or {}
    patch: dict[str, Any] = {}
    if "mass_sigma_kg" in disp:
        vehicle = data.get("vehicle", {})
        dry_mass = float(vehicle.get("dry_mass_kg", float(vehicle.get("mass_kg", 18.0)) * 0.75))
        sampled_mass = float(vehicle.get("mass_kg", 18.0)) + float(rng.normal(0.0, disp["mass_sigma_kg"]))
        patch.setdefault("vehicle", {})["mass_kg"] = max(dry_mass + 0.05, sampled_mass)
    if "wind_sigma_mps" in disp:
        wind = np.array(data.get("wind", {}).get("steady_mps", [0.0, 0.0, 0.0]), dtype=float)
        wind += rng.normal(0.0, float(disp["wind_sigma_mps"]), 3)
        patch.setdefault("wind", {})["steady_mps"] = wind.tolist()
    patch.setdefault("sensors", {})["seed"] = int(seed)
    return deep_merge(data, patch)
