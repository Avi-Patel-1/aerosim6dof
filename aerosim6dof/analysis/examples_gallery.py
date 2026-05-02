"""Curated gallery cards for public example scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXAMPLES_ROOT = ROOT / "examples"
DEFAULT_EXPECTED_OUTPUTS = [
    "history.csv",
    "truth.csv",
    "controls.csv",
    "sensors.csv",
    "events.json",
    "summary.json",
    "scenario_resolved.json",
    "manifest.json",
    "report.html",
    "plots/*.svg",
]
DEFAULT_PRIMARY_METRICS = ["altitude_m", "speed_mps", "load_factor_g", "qbar_pa"]


def build_examples_gallery(examples_root: str | Path = DEFAULT_EXAMPLES_ROOT) -> list[dict[str, Any]]:
    """Scan ``examples/scenarios`` and return curated gallery card dictionaries.

    The gallery is intentionally tolerant: missing directories, malformed JSON,
    scenario files with unexpected shapes, and unsafe symlink targets produce
    either an empty result or non-runnable fallback cards instead of exceptions.
    """

    examples_path = Path(examples_root)
    scenarios_dir = examples_path / "scenarios"
    try:
        resolved_scenarios_dir = scenarios_dir.resolve(strict=True)
    except OSError:
        return []

    cards: list[dict[str, Any]] = []
    for path in sorted(scenarios_dir.glob("*.json")):
        safe_path = _resolve_safe_scenario_path(path, resolved_scenarios_dir)
        if safe_path is None:
            continue
        cards.append(_card_from_path(path, examples_path))
    return cards


def _card_from_path(path: Path, examples_root: Path) -> dict[str, Any]:
    scenario: dict[str, Any] | None = None
    notes: list[str] = []
    can_run = True

    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        raw = None
        can_run = False
        notes.append("Scenario file disappeared while the gallery was being built.")
    except json.JSONDecodeError as exc:
        raw = None
        can_run = False
        notes.append(f"Invalid JSON at line {exc.lineno}, column {exc.colno}.")
    except OSError as exc:
        raw = None
        can_run = False
        notes.append(f"Unable to read scenario file: {exc.__class__.__name__}.")

    if isinstance(raw, dict):
        scenario = raw
        shape_notes = _scenario_shape_notes(scenario)
        if shape_notes:
            can_run = False
            notes.extend(shape_notes)
    elif raw is not None:
        can_run = False
        notes.append("Scenario JSON should be an object.")

    metadata = _metadata_for(path.stem, scenario)
    notes.extend(metadata.get("notes", []))

    return {
        "id": path.stem,
        "title": metadata["title"],
        "description": metadata["description"],
        "scenario_path": _display_path(path, examples_root),
        "tags": metadata["tags"],
        "difficulty": metadata["difficulty"],
        "expected_outputs": metadata["expected_outputs"],
        "primary_metrics": metadata["primary_metrics"],
        "can_run": can_run,
        "notes": _dedupe(notes),
    }


def _metadata_for(stem: str, scenario: dict[str, Any] | None) -> dict[str, Any]:
    haystack = _haystack(stem, scenario)

    if "nominal" in haystack and "ascent" in haystack:
        return {
            "title": "Nominal Ascent",
            "description": "Baseline climb-out used to confirm vehicle, environment, guidance, and sensor outputs before adding stressors.",
            "tags": ["baseline", "ascent", "guidance", "sensors"],
            "difficulty": "Beginner",
            "expected_outputs": DEFAULT_EXPECTED_OUTPUTS,
            "primary_metrics": ["altitude_m", "speed_mps", "pitch_deg", "qbar_pa", "load_factor_g"],
            "notes": ["Use this as the first clone target when checking a new vehicle or environment edit."],
        }

    if _has_terrain_or_contact(stem, scenario):
        return {
            "title": _title_from_stem(stem, "Terrain Contact"),
            "description": "Range and terrain-aware case for checking altitude margins, contact handling, and termination behavior near the ground.",
            "tags": ["terrain", "contact", "range-safety", "environment"],
            "difficulty": "Advanced",
            "expected_outputs": DEFAULT_EXPECTED_OUTPUTS,
            "primary_metrics": ["altitude_agl_m", "altitude_m", "vertical_speed_mps", "load_factor_g"],
            "notes": ["Clone before changing initial altitude, terrain model, or contact limits."],
        }

    if _has_faults(stem, scenario):
        return {
            "title": _title_from_stem(stem, "Fault Injection"),
            "description": "Failure-mode example for studying degraded sensors, actuators, propulsion, or control authority under a repeatable mission profile.",
            "tags": ["faults", "resilience", "fdir", "validation"],
            "difficulty": "Advanced",
            "expected_outputs": DEFAULT_EXPECTED_OUTPUTS,
            "primary_metrics": ["altitude_m", "speed_mps", "load_factor_g", "actuator_saturation", "alarm_count"],
            "notes": ["Run the nearest non-fault baseline first, then clone this case to isolate one fault at a time."],
        }

    if _has_target_or_intercept(stem, scenario):
        return {
            "title": _title_from_stem(stem, "Target Intercept"),
            "description": "Engagement scenario for validating target tracking, interceptor handoff, miss distance, and guidance stability.",
            "tags": ["target", "intercept", "engagement", "guidance"],
            "difficulty": "Intermediate",
            "expected_outputs": DEFAULT_EXPECTED_OUTPUTS,
            "primary_metrics": ["target_distance_m", "miss_distance_m", "altitude_m", "speed_mps", "load_factor_g"],
            "notes": ["Clone to adjust target geometry, proximity thresholds, or interceptor launch timing."],
        }

    return _fallback_metadata(stem, scenario)


def _fallback_metadata(stem: str, scenario: dict[str, Any] | None) -> dict[str, Any]:
    guidance = _nested_str(scenario, "guidance", "mode")
    tags = ["scenario"]
    if guidance:
        tags.append(guidance.replace("_", "-"))
    if _nested_value(scenario, "environment_config"):
        tags.append("environment")
    if _nested_value(scenario, "vehicle_config"):
        tags.append("vehicle")

    return {
        "title": _title_from_stem(stem),
        "description": _fallback_description(stem, scenario),
        "tags": _dedupe(tags),
        "difficulty": "Intermediate",
        "expected_outputs": DEFAULT_EXPECTED_OUTPUTS,
        "primary_metrics": _fallback_metrics(scenario),
        "notes": ["Metadata is inferred from the scenario file name and available JSON fields."],
    }


def _fallback_description(stem: str, scenario: dict[str, Any] | None) -> str:
    guidance = _nested_str(scenario, "guidance", "mode")
    duration = _nested_value(scenario, "duration")
    if guidance and isinstance(duration, (int, float)):
        return f"{_title_from_stem(stem)} runs {guidance.replace('_', ' ')} guidance for {duration:g} seconds."
    if guidance:
        return f"{_title_from_stem(stem)} exercises {guidance.replace('_', ' ')} guidance with the configured vehicle and environment."
    return f"{_title_from_stem(stem)} is available as a cloneable example scenario."


def _fallback_metrics(scenario: dict[str, Any] | None) -> list[str]:
    metrics = list(DEFAULT_PRIMARY_METRICS)
    if _has_target_or_intercept("", scenario):
        metrics.insert(0, "target_distance_m")
    if _has_faults("", scenario):
        metrics.append("alarm_count")
    return _dedupe(metrics)


def _scenario_shape_notes(scenario: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not isinstance(scenario.get("duration"), (int, float)):
        notes.append("Scenario duration is missing or non-numeric.")
    if not isinstance(scenario.get("dt"), (int, float)):
        notes.append("Scenario timestep dt is missing or non-numeric.")
    if not isinstance(scenario.get("initial"), dict):
        notes.append("Scenario initial state block is missing or not an object.")
    if not isinstance(scenario.get("guidance"), dict):
        notes.append("Scenario guidance block is missing or not an object.")
    return notes


def _has_target_or_intercept(stem: str, scenario: dict[str, Any] | None) -> bool:
    guidance = _nested_str(scenario, "guidance", "mode")
    return (
        "target" in stem.lower()
        or "intercept" in stem.lower()
        or guidance == "target_intercept"
        or bool(_nested_value(scenario, "targets"))
        or bool(_nested_value(scenario, "interceptors"))
    )


def _has_terrain_or_contact(stem: str, scenario: dict[str, Any] | None) -> bool:
    haystack = _haystack(stem, scenario)
    if "terrain" in haystack or "contact" in haystack or "ground" in haystack:
        return True
    events = _nested_value(scenario, "events")
    if isinstance(events, dict):
        return any("terrain" in key.lower() or "contact" in key.lower() for key in events)
    return False


def _has_faults(stem: str, scenario: dict[str, Any] | None) -> bool:
    haystack = _haystack(stem, scenario)
    fault_words = ("fault", "failure", "dropout", "bias", "stuck", "thrust_loss", "misalignment")
    if any(word in haystack for word in fault_words):
        return True
    sensors = _nested_value(scenario, "sensors")
    if isinstance(sensors, dict) and sensors.get("faults"):
        return True
    vehicle = _nested_value(scenario, "vehicle")
    return _contains_key(vehicle, "failure")


def _haystack(stem: str, scenario: dict[str, Any] | None) -> str:
    pieces = [stem]
    if isinstance(scenario, dict):
        for key in ("name", "vehicle_config", "environment_config"):
            value = scenario.get(key)
            if isinstance(value, str):
                pieces.append(value)
        guidance = scenario.get("guidance")
        if isinstance(guidance, dict) and isinstance(guidance.get("mode"), str):
            pieces.append(guidance["mode"])
    return " ".join(pieces).replace("-", "_").lower()


def _contains_key(value: Any, wanted: str) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() == wanted or _contains_key(child, wanted) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_key(item, wanted) for item in value)
    return False


def _nested_value(scenario: dict[str, Any] | None, *keys: str) -> Any:
    value: Any = scenario
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _nested_str(scenario: dict[str, Any] | None, *keys: str) -> str:
    value = _nested_value(scenario, *keys)
    return value if isinstance(value, str) else ""


def _title_from_stem(stem: str, fallback: str | None = None) -> str:
    if not stem:
        return fallback or "Example Scenario"
    title = " ".join(part for part in stem.replace("-", "_").split("_") if part).title()
    return title or fallback or "Example Scenario"


def _display_path(path: Path, examples_root: Path) -> str:
    base = examples_root.parent
    try:
        relative = path.resolve(strict=False).relative_to(base.resolve(strict=False))
    except ValueError:
        relative = Path("examples") / "scenarios" / path.name
    return relative.as_posix()


def _resolve_safe_scenario_path(path: Path, scenarios_dir: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(scenarios_dir)
    except OSError:
        return None
    except ValueError:
        return None
    if not resolved.is_file():
        return None
    return resolved


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = ["build_examples_gallery"]
