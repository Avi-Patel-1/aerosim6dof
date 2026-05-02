"""Defensive scenario advisory validation.

This module inspects raw scenario dictionaries and JSON files without building
or mutating a :class:`aerosim6dof.scenario.Scenario`. The advisories are meant
to explain why a scenario may fail later, not to replace hard validation.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScenarioAdvisory:
    code: str
    severity: str
    path: str
    message: str
    suggestion: str | None = None
    resolved_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def validate_scenario_advisories(scenario: Any, *, base_dir: str | Path | None = None) -> list[ScenarioAdvisory]:
    """Return non-fatal advisory warnings for a raw scenario JSON/dict.

    ``scenario`` may be a dictionary, a path to a JSON file, JSON text, or an
    object with a ``raw`` scenario dictionary. The function never constructs a
    simulator ``Scenario`` object and never raises for malformed scenario data.
    """

    advisories: list[ScenarioAdvisory] = []
    cfg, inferred_base_dir = _coerce_scenario(scenario, advisories)
    if cfg is None:
        return advisories

    reference_base = Path(base_dir) if base_dir is not None else inferred_base_dir
    _check_references(cfg, reference_base, advisories)
    _check_model_visibility(cfg, advisories)
    _check_timing(cfg, advisories)
    _check_initial_state(cfg, advisories)
    _check_guidance_and_schema(cfg, advisories)
    _check_termination_and_outputs(cfg, advisories)
    _check_terrain_radar(cfg, advisories)
    _check_engagement_links(cfg, advisories)
    _check_preset_compatibility(cfg, advisories)
    return advisories


def _coerce_scenario(value: Any, advisories: list[ScenarioAdvisory]) -> tuple[dict[str, Any] | None, Path | None]:
    if isinstance(value, Mapping):
        return dict(value), None
    raw = getattr(value, "raw", None)
    if isinstance(raw, Mapping):
        source_path = getattr(value, "source_path", None)
        base_dir = Path(source_path).parent if source_path else None
        return dict(raw), base_dir
    if isinstance(value, (str, os.PathLike)):
        text = str(value)
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                _add(
                    advisories,
                    "SCENARIO_JSON_INVALID",
                    "error",
                    "$",
                    f"Scenario JSON could not be parsed at line {exc.lineno}, column {exc.colno}.",
                    "Fix the JSON syntax before running hard validation.",
                )
                return None, None
            if not isinstance(parsed, dict):
                _add(
                    advisories,
                    "SCENARIO_TOP_LEVEL_NOT_OBJECT",
                    "error",
                    "$",
                    "Scenario JSON must be a top-level object.",
                    "Wrap scenario fields in a JSON object.",
                )
                return None, None
            return parsed, None
        path = Path(value)
        if not path.exists():
            _add(
                advisories,
                "SCENARIO_FILE_MISSING",
                "warning",
                "$",
                f"Scenario file does not exist: {path}",
                "Check the scenario path or pass a scenario dictionary.",
                str(path),
            )
            return None, path.parent
        try:
            parsed = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            _add(
                advisories,
                "SCENARIO_JSON_INVALID",
                "error",
                "$",
                f"Scenario JSON could not be parsed at line {exc.lineno}, column {exc.colno}.",
                "Fix the JSON syntax before running hard validation.",
                str(path),
            )
            return None, path.parent
        if not isinstance(parsed, dict):
            _add(
                advisories,
                "SCENARIO_TOP_LEVEL_NOT_OBJECT",
                "error",
                "$",
                "Scenario JSON must be a top-level object.",
                "Wrap scenario fields in a JSON object.",
                str(path),
            )
            return None, path.parent
        return parsed, path.parent
    _add(
        advisories,
        "SCENARIO_INPUT_UNSUPPORTED",
        "error",
        "$",
        "Scenario advisories require a mapping, JSON text, JSON file path, or object with raw scenario data.",
        "Pass the raw scenario dict before materializing a Scenario.",
    )
    return None, None


def _check_references(cfg: dict[str, Any], base_dir: Path | None, advisories: list[ScenarioAdvisory]) -> None:
    for path, value in _iter_reference_fields(cfg):
        if not isinstance(value, (str, os.PathLike)):
            _add(
                advisories,
                "REFERENCE_NOT_STRING",
                "warning",
                path,
                "Configuration reference should be a file path string.",
                "Use a relative JSON path or inline the configuration object.",
            )
            continue
        ref = str(value)
        if base_dir is None:
            _add(
                advisories,
                "REFERENCE_UNCHECKED",
                "info",
                path,
                "Configuration reference was found but no base_dir was provided for existence checks.",
                "Pass base_dir set to the scenario file directory to verify this reference.",
                ref,
            )
            continue
        resolved, exists = _resolve_reference(ref, base_dir)
        if exists:
            _add(
                advisories,
                "REFERENCE_RESOLVED",
                "info",
                path,
                "Configuration reference exists.",
                None,
                str(resolved),
            )
        else:
            _add(
                advisories,
                "REFERENCE_MISSING",
                "warning",
                path,
                "Configuration reference could not be found.",
                "Check the relative path from the scenario file or repository root.",
                str(resolved),
            )


def _iter_reference_fields(cfg: dict[str, Any]) -> list[tuple[str, Any]]:
    refs: list[tuple[str, Any]] = []
    for key in ("extends", "vehicle_config", "environment_config", "autopilot_config", "sensor_config", "sensors_config"):
        if key in cfg:
            refs.append((key, cfg[key]))
    for section_name in ("autopilot", "sensors"):
        section = _dict(cfg.get(section_name))
        for key, value in section.items():
            if _looks_like_reference_key(key):
                refs.append((f"{section_name}.{key}", value))
            if isinstance(value, Mapping):
                for nested_key, nested_value in value.items():
                    if _looks_like_reference_key(nested_key):
                        refs.append((f"{section_name}.{key}.{nested_key}", nested_value))
    return refs


def _looks_like_reference_key(key: str) -> bool:
    return key in {"config", "config_path", "model_path"} or key.endswith("_config") or key.endswith("_config_path")


def _check_model_visibility(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    if not cfg.get("vehicle_config") and not isinstance(cfg.get("vehicle"), Mapping):
        _add(
            advisories,
            "MISSING_VEHICLE_MODEL",
            "warning",
            "vehicle_config",
            "No vehicle_config or inline vehicle model is present.",
            "Add vehicle_config or an inline vehicle object so mass, geometry, propulsion, and aero assumptions are visible.",
        )
    if not cfg.get("environment_config") and not isinstance(cfg.get("environment"), Mapping):
        _add(
            advisories,
            "MISSING_ENVIRONMENT_MODEL",
            "info",
            "environment_config",
            "No environment_config or inline environment model is present.",
            "Add environment_config or an inline environment object when wind, density, gravity, or terrain assumptions matter.",
        )
    if "autopilot_config" not in cfg and "autopilot" not in cfg:
        _add(
            advisories,
            "AUTOPILOT_DEFAULTS_IMPLICIT",
            "info",
            "autopilot",
            "Autopilot tuning is implicit.",
            "Inline autopilot gains or reference a preset when comparing control behavior across scenarios.",
        )


def _check_timing(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    dt = _number(cfg.get("dt", 0.02))
    duration = _number(cfg.get("duration", 20.0))
    if "dt" in cfg and (dt is None or dt <= 0.0):
        _add(advisories, "TIMESTEP_INVALID", "warning", "dt", "dt should be a positive finite number.", "Hard validation will reject non-positive dt.")
    elif dt is not None and dt > 0.1:
        _add(advisories, "TIMESTEP_COARSE", "warning", "dt", "dt is coarse for closed-loop 6DOF dynamics.", "Try a smaller dt or compare with a half-step run.")
    if "duration" in cfg and (duration is None or duration <= 0.0):
        _add(advisories, "DURATION_INVALID", "warning", "duration", "duration should be a positive finite number.", "Hard validation will reject non-positive duration.")
    if dt is not None and duration is not None and dt > 0.0 and duration > 0.0:
        steps = duration / dt
        if steps > 500_000:
            _add(advisories, "STEP_COUNT_EXTREME", "warning", "duration/dt", "duration/dt creates more than 500000 integration steps.", "Reduce duration or increase dt before interactive runs.")
        elif steps < 50:
            _add(advisories, "STEP_COUNT_LOW", "info", "duration/dt", "Scenario has very few integration steps.", "Confirm the run is intended as a short smoke test.")


def _check_initial_state(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    initial = _dict(cfg.get("initial"))
    if not initial:
        _add(advisories, "MISSING_INITIAL_SECTION", "warning", "initial", "Initial state is missing or not an object.", "Specify initial position, velocity, and attitude to avoid relying on defaults.")
        return
    position = _vector(initial.get("position_m"))
    velocity = _vector(initial.get("velocity_mps"))
    euler = _vector(initial.get("euler_deg"))
    if "position_m" in initial and position is None:
        _add(advisories, "INITIAL_POSITION_INVALID", "warning", "initial.position_m", "initial.position_m should be a three-element finite numeric vector.", "Use [x_m, y_m, altitude_m].")
    if position is not None:
        altitude = position[2]
        if altitude < 0.0:
            _add(advisories, "INITIAL_ALTITUDE_BELOW_ZERO", "warning", "initial.position_m[2]", "Initial altitude is below zero meters.", "Start above local terrain unless this is a contact test.")
        elif altitude < 5.0:
            _add(advisories, "INITIAL_ALTITUDE_NEAR_GROUND", "info", "initial.position_m[2]", "Initial altitude is very close to ground level.", "Check ground-contact and terrain settings before running campaigns.")
        elif altitude > 30_000.0:
            _add(advisories, "INITIAL_ALTITUDE_EXTREME", "warning", "initial.position_m[2]", "Initial altitude is outside the usual aircraft scenario range.", "Confirm atmosphere, vehicle, and control presets are valid at this altitude.")
    if "velocity_mps" in initial and velocity is None:
        _add(advisories, "INITIAL_VELOCITY_INVALID", "warning", "initial.velocity_mps", "initial.velocity_mps should be a three-element finite numeric vector.", "Use [vx, vy, vz] in meters per second.")
    if velocity is not None:
        speed = _norm(velocity)
        if speed < 5.0:
            _add(advisories, "INITIAL_SPEED_LOW", "warning", "initial.velocity_mps", "Initial speed is very low for flight dynamics.", "Confirm this is a launch, hover, or ground-contact case.")
        elif speed > 1_000.0:
            _add(advisories, "INITIAL_SPEED_EXTREME", "warning", "initial.velocity_mps", "Initial speed is extremely high for the packaged vehicle presets.", "Confirm aerodynamic tables, integration timestep, and control limits for this speed.")
        elif speed > 350.0:
            _add(advisories, "INITIAL_SPEED_HIGH", "info", "initial.velocity_mps", "Initial speed is high for baseline aircraft-style presets.", "Check dynamic pressure and actuator saturation margins.")
    if "euler_deg" in initial and euler is None:
        _add(advisories, "INITIAL_ATTITUDE_INVALID", "warning", "initial.euler_deg", "initial.euler_deg should be a three-element finite numeric vector.", "Use [roll_deg, pitch_deg, heading_deg].")
    elif euler is not None and (abs(euler[0]) > 80.0 or abs(euler[1]) > 60.0):
        _add(advisories, "INITIAL_ATTITUDE_STEEP", "info", "initial.euler_deg", "Initial roll or pitch is unusually steep.", "Check that this is intentional before blaming controller behavior.")


def _check_guidance_and_schema(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    integrator = cfg.get("integrator")
    if integrator is not None and str(integrator) not in {"semi_implicit_euler", "euler", "rk2", "rk4", "adaptive_rk45"}:
        _add(advisories, "INTEGRATOR_UNKNOWN", "warning", "integrator", "Integrator name is not supported by current hard validation.", "Use semi_implicit_euler, euler, rk2, rk4, or adaptive_rk45.")
    guidance = _dict(cfg.get("guidance"))
    if "guidance" in cfg and not isinstance(cfg.get("guidance"), Mapping):
        _add(advisories, "GUIDANCE_NOT_OBJECT", "warning", "guidance", "guidance should be an object.", "Replace guidance with a JSON object.")
    if not guidance:
        _add(advisories, "MISSING_GUIDANCE", "info", "guidance", "Guidance block is missing or empty.", "Add guidance.mode and commands for closed-loop scenarios.")
    elif not guidance.get("mode"):
        _add(advisories, "GUIDANCE_MODE_MISSING", "info", "guidance.mode", "Guidance mode is not explicit.", "Set guidance.mode to make scenario intent visible.")
    throttle = guidance.get("throttle")
    if throttle is not None:
        value = _number(throttle)
        if value is None or not 0.0 <= value <= 1.0:
            _add(advisories, "THROTTLE_OUT_OF_RANGE", "warning", "guidance.throttle", "Throttle should be numeric and between 0 and 1.", "Hard validation will reject throttle outside the command range.")
    vehicle = _dict(cfg.get("vehicle"))
    mass = _number(vehicle.get("mass_kg"))
    dry_mass = _number(vehicle.get("dry_mass_kg"))
    if mass is not None and dry_mass is not None and (mass <= 0.0 or dry_mass <= 0.0 or dry_mass > mass):
        _add(advisories, "VEHICLE_MASS_INCONSISTENT", "warning", "vehicle.mass_kg", "Vehicle mass settings are inconsistent.", "Use positive mass values with dry_mass_kg <= mass_kg.")
    sensors = _dict(cfg.get("sensors"))
    faults = sensors.get("faults")
    if faults not in (None, []) and not isinstance(faults, list):
        _add(advisories, "SENSOR_FAULTS_NOT_LIST", "warning", "sensors.faults", "Sensor faults should be a list.", "Use an array of fault objects.")


def _check_termination_and_outputs(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    events = _dict(cfg.get("events"))
    if not events:
        _add(
            advisories,
            "MISSING_TERMINATION_SECTION",
            "warning",
            "events",
            "No termination/event limits are configured.",
            "Add qbar_limit_pa, load_limit_g, and target_threshold_m when applicable so failures stop clearly.",
        )
    else:
        for key in ("qbar_limit_pa", "load_limit_g", "target_threshold_m"):
            if key in events:
                value = _number(events[key])
                if value is None or value <= 0.0:
                    _add(advisories, "TERMINATION_LIMIT_INVALID", "warning", f"events.{key}", f"{key} should be a positive finite number.", "Hard validation will reject non-positive event limits.")
        if "qbar_limit_pa" not in events:
            _add(advisories, "QBAR_LIMIT_MISSING", "info", "events.qbar_limit_pa", "No dynamic-pressure event limit is configured.", "Add qbar_limit_pa before high-speed campaigns.")
        if "load_limit_g" not in events:
            _add(advisories, "LOAD_LIMIT_MISSING", "info", "events.load_limit_g", "No load-factor event limit is configured.", "Add load_limit_g before aggressive maneuver campaigns.")
    if not any(key in cfg for key in ("output", "outputs", "report", "reports")):
        _add(
            advisories,
            "MISSING_OUTPUT_SECTION",
            "info",
            "outputs",
            "No output/report preference section is present.",
            "This is runnable, but UI and batch tooling may need explicit output/report intent for review workflows.",
        )


def _check_terrain_radar(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    environment = _dict(cfg.get("environment"))
    terrain = _dict(environment.get("terrain"))
    contact = _dict(environment.get("ground_contact"))
    sensors = _dict(cfg.get("sensors"))
    radar = _dict(sensors.get("radar_altimeter") or sensors.get("radar"))
    terrain_enabled = _enabled(terrain, default=bool(terrain))
    contact_enabled = _enabled(contact, default=False)
    radar_enabled = _enabled(radar, default=bool(radar))
    if terrain and terrain.get("enabled") is False and len(terrain) > 1:
        _add(advisories, "TERRAIN_DISABLED_WITH_SETTINGS", "info", "environment.terrain.enabled", "Terrain settings are present while terrain is disabled.", "Enable terrain or remove stale terrain details to avoid review confusion.")
    if contact_enabled and terrain and not terrain_enabled:
        _add(advisories, "GROUND_CONTACT_WITH_DISABLED_TERRAIN", "warning", "environment.ground_contact.enabled", "Ground contact is enabled while terrain is disabled.", "Confirm contact should use flat ground or enable terrain explicitly.")
    if radar and radar_enabled and terrain and not terrain_enabled:
        _add(advisories, "RADAR_WITH_DISABLED_TERRAIN", "warning", "sensors.radar_altimeter", "Radar altimeter is enabled while terrain is disabled.", "Confirm radar altitude should be measured against flat ground.")
    if terrain_enabled and radar and not radar_enabled:
        _add(advisories, "TERRAIN_WITH_DISABLED_RADAR", "info", "sensors.radar_altimeter.enabled", "Terrain is enabled but radar altimeter is disabled.", "Confirm guidance and reports do not rely on AGL sensing.")
    minimum = _number(radar.get("min_altitude_m"))
    maximum = _number(radar.get("max_altitude_m"))
    if minimum is not None and maximum is not None and minimum > maximum:
        _add(advisories, "RADAR_RANGE_INVERTED", "warning", "sensors.radar_altimeter", "Radar altitude range has min_altitude_m greater than max_altitude_m.", "Swap or correct the radar range limits.")


def _check_engagement_links(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    targets = cfg.get("targets")
    interceptors = cfg.get("interceptors")
    guidance_mode = str(_dict(cfg.get("guidance")).get("mode", "")).lower()
    if targets is not None and not isinstance(targets, list):
        _add(advisories, "TARGETS_NOT_LIST", "warning", "targets", "targets should be a list.", "Use an array of target objects.")
        targets_list: list[Any] = []
    else:
        targets_list = targets or []
    if interceptors is not None and not isinstance(interceptors, list):
        _add(advisories, "INTERCEPTORS_NOT_LIST", "warning", "interceptors", "interceptors should be a list.", "Use an array of interceptor objects.")
        return
    interceptors_list = interceptors or []
    target_ids: set[str] = set()
    for idx, target in enumerate(targets_list):
        if not isinstance(target, Mapping):
            _add(advisories, "TARGET_NOT_OBJECT", "warning", f"targets[{idx}]", "Target entry should be an object.", "Use target objects with id and state fields.")
            continue
        target_id = target.get("id")
        if not target_id:
            _add(advisories, "TARGET_ID_MISSING", "info", f"targets[{idx}].id", "Target has no stable id.", "Add id so interceptors and reports can link to this target.")
            continue
        target_id_text = str(target_id)
        if target_id_text in target_ids:
            _add(advisories, "TARGET_ID_DUPLICATE", "warning", f"targets[{idx}].id", "Target id is duplicated.", "Use unique target ids.")
        target_ids.add(target_id_text)
    if interceptors_list and not targets_list:
        _add(advisories, "INTERCEPTORS_WITHOUT_TARGETS", "warning", "interceptors", "Interceptors are configured but no targets are present.", "Add targets or remove interceptor entries.")
    for idx, interceptor in enumerate(interceptors_list):
        path = f"interceptors[{idx}]"
        if not isinstance(interceptor, Mapping):
            _add(advisories, "INTERCEPTOR_NOT_OBJECT", "warning", path, "Interceptor entry should be an object.", "Use interceptor objects with target_id and dynamics settings.")
            continue
        target_id = interceptor.get("target_id")
        if not target_id:
            _add(advisories, "INTERCEPTOR_TARGET_MISSING", "warning", f"{path}.target_id", "Interceptor is missing target_id.", "Set target_id to a configured target id.")
        elif target_ids and str(target_id) not in target_ids:
            _add(advisories, "INTERCEPTOR_TARGET_UNKNOWN", "warning", f"{path}.target_id", "Interceptor target_id does not match any configured target.", "Use a target_id from the targets list.")
    if ("target" in guidance_mode or "proportional" in guidance_mode) and not targets_list and "target_position_m" not in _dict(cfg.get("guidance")):
        _add(advisories, "TARGET_GUIDANCE_WITHOUT_TARGET", "warning", "guidance", "Target-focused guidance has no target list or target_position_m.", "Add a target or target_position_m before running.")
    if (targets_list or interceptors_list or "target" in guidance_mode) and "target_threshold_m" not in _dict(cfg.get("events")):
        _add(advisories, "TARGET_THRESHOLD_MISSING", "warning", "events.target_threshold_m", "Targeted scenario has no target miss-distance threshold.", "Add events.target_threshold_m to make intercept success/failure explicit.")


def _check_preset_compatibility(cfg: dict[str, Any], advisories: list[ScenarioAdvisory]) -> None:
    initial = _dict(cfg.get("initial"))
    altitude = (_vector(initial.get("position_m")) or (0.0, 0.0, None))[2]
    velocity = _vector(initial.get("velocity_mps"))
    speed = _norm(velocity) if velocity is not None else None
    vehicle_preset = str(cfg.get("vehicle_config", "")).lower()
    environment_preset = str(cfg.get("environment_config", "")).lower()
    if altitude is not None and altitude > 15_000.0 and ("baseline" in vehicle_preset or "electric_uav" in vehicle_preset):
        _add(
            advisories,
            "PRESET_ALTITUDE_COMPATIBILITY",
            "warning",
            "vehicle_config",
            "Initial altitude is high for the selected vehicle preset name.",
            "Consider a high-altitude vehicle preset or verify aero/propulsion tables at this altitude.",
        )
    if speed is not None and speed > 120.0 and "electric_uav" in vehicle_preset:
        _add(
            advisories,
            "PRESET_SPEED_COMPATIBILITY",
            "warning",
            "vehicle_config",
            "Initial speed is high for an electric UAV preset.",
            "Confirm the vehicle preset supports this speed envelope.",
        )
    if "terrain" in environment_preset and altitude is not None and altitude < 20.0:
        _add(
            advisories,
            "PRESET_TERRAIN_LOW_ALTITUDE",
            "warning",
            "environment_config",
            "Terrain preset is selected with low initial altitude.",
            "Check local terrain elevation and ground-contact settings before running.",
        )
    if "calm" in environment_preset and ("wind" in cfg or _dict(cfg.get("environment")).get("wind")):
        _add(
            advisories,
            "PRESET_ENVIRONMENT_OVERRIDE",
            "info",
            "environment_config",
            "A calm environment preset is selected while scenario wind overrides are present.",
            "Confirm the override is intentional for comparisons against calm baselines.",
        )


def _resolve_reference(value: str, base_dir: Path) -> tuple[Path, bool]:
    ref = Path(value).expanduser()
    if ref.is_absolute():
        return ref, ref.exists()
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [base_dir / ref, repo_root / ref]
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved, True
    return candidates[0].resolve(strict=False), False


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _vector(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    numbers = [_number(item) for item in value]
    if any(number is None for number in numbers):
        return None
    return (float(numbers[0]), float(numbers[1]), float(numbers[2]))


def _norm(vector: tuple[float, float, float] | None) -> float:
    if vector is None:
        return 0.0
    return math.sqrt(sum(component * component for component in vector))


def _enabled(section: dict[str, Any], *, default: bool) -> bool:
    if "enabled" not in section:
        return default
    return bool(section.get("enabled"))


def _add(
    advisories: list[ScenarioAdvisory],
    code: str,
    severity: str,
    path: str,
    message: str,
    suggestion: str | None = None,
    resolved_reference: str | None = None,
) -> None:
    advisories.append(
        ScenarioAdvisory(
            code=code,
            severity=severity,
            path=path,
            message=message,
            suggestion=suggestion,
            resolved_reference=resolved_reference,
        )
    )
