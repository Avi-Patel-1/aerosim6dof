"""Validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aerosim6dof.scenario import validate_scenario_file


def validate(path: str | Path) -> dict[str, Any]:
    return validate_scenario_file(path)

