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

CURATED_SCENARIOS: dict[str, dict[str, Any]] = {
    "nominal_ascent": {
        "title": "Nominal Ascent",
        "category": "Baseline",
        "difficulty": "Beginner",
        "description": "Clean pitch-program climb-out for proving the vehicle, environment, guidance, sensors, and report artifacts before adding stressors.",
        "tags": ["baseline", "ascent", "pitch-program", "sensors"],
        "primary_metrics": ["altitude_m", "speed_mps", "pitch_deg", "qbar_pa", "load_factor_g"],
        "suggested_next_edit": "Clone it, then change one pitch-program breakpoint or throttle value to see the baseline response move.",
    },
    "gusted_crossrange": {
        "title": "Gusted Crossrange",
        "category": "Environment",
        "difficulty": "Intermediate",
        "description": "Heading-hold mission in a gusted range environment for checking crossrange drift, roll response, and wind sensitivity.",
        "tags": ["environment", "gusts", "heading-hold", "crossrange"],
        "primary_metrics": ["position_y_m", "heading_deg", "roll_deg", "wind_y_mps", "load_factor_g"],
        "suggested_next_edit": "Clone it and adjust heading_command_deg or swap to calm air to isolate the wind contribution.",
    },
    "sensor_noise_autopilot": {
        "title": "Sensor Noise Autopilot",
        "category": "Sensors and Navigation",
        "difficulty": "Intermediate",
        "description": "Altitude-hold autopilot case with noisy navigation inputs and turbulent air for tuning sensor tolerance and control damping.",
        "tags": ["sensors", "autopilot", "altitude-hold", "turbulence"],
        "primary_metrics": ["altitude_m", "target_altitude_m", "pitch_deg", "gps_altitude_m", "barometer_altitude_m"],
        "suggested_next_edit": "Clone it and change GPS rate, dropout probability, or trim_pitch_deg to compare controller robustness.",
    },
    "gps_dropout_navigation": {
        "title": "GPS Dropout Navigation",
        "category": "Sensors and Navigation",
        "difficulty": "Advanced",
        "description": "Navigation-fault scenario with a timed GPS outage, latency, multipath, barometer drift, and radar altimeter support.",
        "tags": ["gps", "dropout", "navigation", "faults", "radar-altimeter"],
        "primary_metrics": ["gps_valid", "gps_altitude_m", "barometer_altitude_m", "radar_altitude_m", "altitude_m"],
        "expected_outputs": DEFAULT_EXPECTED_OUTPUTS + ["sensor_report.html", "sensor_metrics.json"],
        "suggested_next_edit": "Clone it and move the dropout start/end window to test recovery timing against the same route.",
    },
    "imu_bias_navigation": {
        "title": "IMU Bias Navigation",
        "category": "Sensors and Navigation",
        "difficulty": "Advanced",
        "description": "Heading-hold case with IMU scale, misalignment, and a timed bias jump to exercise attitude and navigation fault handling.",
        "tags": ["imu", "bias-jump", "navigation", "faults", "horizon", "optical-flow"],
        "primary_metrics": ["roll_deg", "pitch_deg", "gyro_bias_rps", "accel_bias_mps2", "heading_deg"],
        "expected_outputs": DEFAULT_EXPECTED_OUTPUTS + ["sensor_report.html", "sensor_metrics.json"],
        "suggested_next_edit": "Clone it and reduce or rotate the bias vector to find the smallest visible attitude error.",
    },
    "waypoint_navigation": {
        "title": "Waypoint Navigation",
        "category": "Guidance",
        "difficulty": "Intermediate",
        "description": "Electric UAV waypoint capture mission in gusted air for validating target geometry, light-vehicle handling, and terminal threshold behavior.",
        "tags": ["waypoint", "uav", "guidance", "gusts"],
        "primary_metrics": ["target_distance_m", "position_y_m", "altitude_m", "speed_mps", "load_factor_g"],
        "suggested_next_edit": "Clone it and move target_position_m or target_threshold_m to tune capture precision.",
    },
    "glide_return": {
        "title": "Glide Return",
        "category": "Guidance",
        "difficulty": "Intermediate",
        "description": "Low-throttle electric UAV return profile aimed at a target point, useful for glide-path and energy-management experiments.",
        "tags": ["glide", "uav", "target-intercept", "energy"],
        "primary_metrics": ["target_distance_m", "altitude_m", "speed_mps", "energy_proxy", "load_factor_g"],
        "suggested_next_edit": "Clone it and lower throttle or move the target altitude to study reachable glide envelopes.",
    },
    "target_intercept": {
        "title": "Target Intercept",
        "category": "Engagement",
        "difficulty": "Intermediate",
        "description": "Target-tracking scenario with a moving primary target, decoy reference, and interceptor handoff for engagement workflow checks.",
        "tags": ["target", "intercept", "engagement", "guidance"],
        "primary_metrics": ["target_distance_m", "miss_distance_m", "altitude_m", "speed_mps", "load_factor_g"],
        "expected_outputs": DEFAULT_EXPECTED_OUTPUTS + ["events.json target/interceptor records"],
        "suggested_next_edit": "Clone it and adjust target velocity or interceptor launch_time_s to compare miss-distance sensitivity.",
    },
    "missile_intercept_demo": {
        "title": "Missile Intercept Demo",
        "category": "Engagement",
        "difficulty": "Advanced",
        "description": "Full missile dynamics demonstration with seeker, motor, actuator, fuze, and self-destruct settings wired into an intercept mission.",
        "tags": ["missile", "intercept", "seeker", "motor", "fuze"],
        "primary_metrics": ["target_distance_m", "miss_distance_m", "missile_speed_mps", "seeker_valid", "fuze_armed"],
        "expected_outputs": DEFAULT_EXPECTED_OUTPUTS + ["events.json missile records"],
        "suggested_next_edit": "Clone it and change navigation_constant, burn_time_s, or proximity_radius_m one at a time.",
    },
    "actuator_saturation": {
        "title": "Actuator Saturation",
        "category": "Control Authority",
        "difficulty": "Intermediate",
        "description": "Aggressive fixed-pitch command with reduced surface limits for exposing actuator saturation and command-tracking margins.",
        "tags": ["actuators", "saturation", "fixed-pitch", "control"],
        "primary_metrics": ["actuator_saturation", "pitch_command_deg", "pitch_deg", "surface_deflection_deg", "load_factor_g"],
        "suggested_next_edit": "Clone it and raise surface_limit_deg or reduce pitch_command_deg to find the recovery point.",
    },
    "stuck_elevator_failure": {
        "title": "Stuck Elevator Failure",
        "category": "Failure Injection",
        "difficulty": "Advanced",
        "description": "Pitch-program ascent with a timed stuck elevator fault for checking failure response, load growth, and report events.",
        "tags": ["failure", "stuck-elevator", "actuators", "pitch-program"],
        "primary_metrics": ["elevator_deflection_deg", "pitch_deg", "altitude_m", "load_factor_g", "alarm_count"],
        "suggested_next_edit": "Clone it and move start_s or value_rad to bracket when the controller loses authority.",
    },
    "engine_thrust_loss": {
        "title": "Engine Thrust Loss",
        "category": "Failure Injection",
        "difficulty": "Advanced",
        "description": "Pitch-program climb with propulsion shutdown after six seconds for studying degraded climb performance and termination behavior.",
        "tags": ["failure", "propulsion", "shutdown", "pitch-program"],
        "primary_metrics": ["thrust_n", "speed_mps", "altitude_m", "vertical_speed_mps", "load_factor_g"],
        "suggested_next_edit": "Clone it and change shutdown_intervals or throttle to compare abort margins.",
    },
    "thrust_misalignment": {
        "title": "Thrust Misalignment",
        "category": "Failure Injection",
        "difficulty": "Intermediate",
        "description": "Fixed-pitch case with propulsion misalignment and nozzle cant moment for evaluating trim and attitude coupling.",
        "tags": ["propulsion", "misalignment", "fixed-pitch", "attitude"],
        "primary_metrics": ["roll_deg", "yaw_deg", "pitch_deg", "thrust_n", "load_factor_g"],
        "suggested_next_edit": "Clone it and reverse one misalignment axis to confirm the sign of the attitude response.",
    },
    "high_aoa_stall": {
        "title": "High AOA Stall",
        "category": "Aerodynamics",
        "difficulty": "Advanced",
        "description": "Low-speed, high-pitch fixed-command case for exercising stall behavior, angle-of-attack growth, and load-limit reporting.",
        "tags": ["aerodynamics", "stall", "high-aoa", "fixed-pitch"],
        "primary_metrics": ["alpha_deg", "speed_mps", "qbar_pa", "load_factor_g", "pitch_deg"],
        "suggested_next_edit": "Clone it and reduce pitch_command_deg or increase initial speed to map the stall boundary.",
    },
    "high_altitude_low_density": {
        "title": "High Altitude Low Density",
        "category": "Atmosphere",
        "difficulty": "Advanced",
        "description": "High-altitude probe case using RK4 integration to inspect low-density performance, dynamic pressure, and sensor noise scaling.",
        "tags": ["atmosphere", "high-altitude", "rk4", "low-density"],
        "primary_metrics": ["altitude_m", "density_kg_m3", "mach", "qbar_pa", "speed_mps"],
        "suggested_next_edit": "Clone it and change initial altitude or vehicle_config to compare atmospheric margin.",
    },
}


def build_examples_gallery(examples_root: str | Path = DEFAULT_EXAMPLES_ROOT) -> list[dict[str, Any]]:
    """Scan ``examples/scenarios`` and return curated gallery card dictionaries.

    The gallery is intentionally tolerant: missing directories, malformed JSON,
    scenario files with unexpected shapes, and unsafe symlink targets produce
    either an empty result or non-runnable fallback cards instead of exceptions.
    It only reads checked-in scenario JSON and never inspects generated outputs.
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
        cards.append(_card_from_path(safe_path, path, examples_path))
    return cards


def _card_from_path(safe_path: Path, display_path: Path, examples_root: Path) -> dict[str, Any]:
    scenario: dict[str, Any] | None = None
    notes: list[str] = []
    can_run = True

    try:
        with safe_path.open(encoding="utf-8") as handle:
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

    scenario_id = display_path.stem
    scenario_path = _display_path(display_path, examples_root)
    metadata = _metadata_for(scenario_id, scenario)
    notes.extend(metadata.get("notes", []))

    return {
        "id": scenario_id,
        "title": metadata["title"],
        "category": metadata["category"],
        "description": metadata["description"],
        "scenario_path": scenario_path,
        "tags": metadata["tags"],
        "difficulty": metadata["difficulty"],
        "expected_outputs": metadata["expected_outputs"],
        "primary_metrics": metadata["primary_metrics"],
        "suggested_next_edit": metadata["suggested_next_edit"],
        "clone_payload": _clone_payload(scenario_id, scenario_path, scenario),
        "edit_payload": _edit_payload(scenario_id, scenario_path, metadata["suggested_next_edit"]),
        "run_payload": _run_payload(scenario_id),
        "can_run": can_run,
        "notes": _dedupe(notes),
    }


def _metadata_for(stem: str, scenario: dict[str, Any] | None) -> dict[str, Any]:
    curated = CURATED_SCENARIOS.get(stem)
    if curated:
        return _with_metadata_defaults(curated)
    return _fallback_metadata(stem, scenario)


def _with_metadata_defaults(metadata: dict[str, Any]) -> dict[str, Any]:
    result = dict(metadata)
    result.setdefault("category", "Scenario")
    result.setdefault("difficulty", "Intermediate")
    result.setdefault("tags", ["scenario"])
    result.setdefault("expected_outputs", DEFAULT_EXPECTED_OUTPUTS)
    result.setdefault("primary_metrics", DEFAULT_PRIMARY_METRICS)
    result.setdefault("suggested_next_edit", "Clone this example and change one mission parameter before rerunning it.")
    result.setdefault("notes", [])
    return result


def _fallback_metadata(stem: str, scenario: dict[str, Any] | None) -> dict[str, Any]:
    guidance = _nested_str(scenario, "guidance", "mode")
    tags = ["scenario"]
    if guidance:
        tags.append(guidance.replace("_", "-"))
    if _nested_value(scenario, "environment_config"):
        tags.append("environment")
    if _nested_value(scenario, "vehicle_config"):
        tags.append("vehicle")
    if _has_target_or_intercept(stem, scenario):
        tags.extend(["target", "intercept"])
    if _has_faults(stem, scenario):
        tags.append("faults")

    return {
        "title": _title_from_stem(stem),
        "category": _fallback_category(stem, scenario),
        "description": _fallback_description(stem, scenario),
        "tags": _dedupe(tags),
        "difficulty": "Intermediate",
        "expected_outputs": DEFAULT_EXPECTED_OUTPUTS,
        "primary_metrics": _fallback_metrics(scenario),
        "suggested_next_edit": _fallback_next_edit(stem, scenario),
        "notes": ["Metadata is inferred from the scenario file name and available JSON fields."],
    }


def _fallback_category(stem: str, scenario: dict[str, Any] | None) -> str:
    if _has_target_or_intercept(stem, scenario):
        return "Engagement"
    if _has_faults(stem, scenario):
        return "Failure Injection"
    if _nested_value(scenario, "sensors"):
        return "Sensors and Navigation"
    if _nested_str(scenario, "guidance", "mode"):
        return "Guidance"
    return "Scenario"


def _fallback_description(stem: str, scenario: dict[str, Any] | None) -> str:
    guidance = _nested_str(scenario, "guidance", "mode")
    duration = _nested_value(scenario, "duration")
    if guidance and isinstance(duration, (int, float)):
        return f"{_title_from_stem(stem)} runs {guidance.replace('_', ' ')} guidance for {duration:g} seconds."
    if guidance:
        return f"{_title_from_stem(stem)} exercises {guidance.replace('_', ' ')} guidance with the configured vehicle and environment."
    return f"{_title_from_stem(stem)} is available as a cloneable example scenario."


def _fallback_next_edit(stem: str, scenario: dict[str, Any] | None) -> str:
    guidance = _nested_str(scenario, "guidance", "mode")
    if guidance == "target_intercept" or _has_target_or_intercept(stem, scenario):
        return "Clone it and adjust target_position_m or target_threshold_m before rerunning the engagement."
    if _has_faults(stem, scenario):
        return "Clone it and move one fault start/end time to isolate the response window."
    if guidance:
        return f"Clone it and change one {guidance.replace('_', ' ')} guidance parameter before rerunning."
    return "Clone it and change one initial condition before rerunning."


def _fallback_metrics(scenario: dict[str, Any] | None) -> list[str]:
    metrics = list(DEFAULT_PRIMARY_METRICS)
    if _has_target_or_intercept("", scenario):
        metrics.insert(0, "target_distance_m")
    if _has_faults("", scenario):
        metrics.append("alarm_count")
    return _dedupe(metrics)


def _clone_payload(scenario_id: str, scenario_path: str, scenario: dict[str, Any] | None) -> dict[str, Any]:
    source_name = _nested_str(scenario, "name") or scenario_id
    clone_name = f"{source_name}_copy"
    return {
        "action": "clone_example",
        "source_scenario_id": scenario_id,
        "scenario_path": scenario_path,
        "suggested_name": clone_name,
        "scenario_patch": {"name": clone_name},
    }


def _edit_payload(scenario_id: str, scenario_path: str, suggested_next_edit: str) -> dict[str, Any]:
    return {
        "action": "edit_example",
        "scenario_id": scenario_id,
        "scenario_path": scenario_path,
        "focus": suggested_next_edit,
    }


def _run_payload(scenario_id: str) -> dict[str, Any]:
    return {
        "action": "run",
        "params": {"scenario_id": scenario_id},
    }


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


def _title_from_stem(stem: str) -> str:
    if not stem:
        return "Example Scenario"
    title = " ".join(part for part in stem.replace("-", "_").split("_") if part).title()
    return title or "Example Scenario"


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
