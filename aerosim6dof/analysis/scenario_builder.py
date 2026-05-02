"""Advisory helpers for Scenario Builder draft review.

These helpers intentionally avoid constructing a Scenario object. They inspect
raw or partially materialized configuration dictionaries and return summaries,
warnings, and mission-design guidance without changing simulator validation.
"""

from __future__ import annotations

import math
from typing import Any


def scenario_builder_summary(config: dict) -> dict:
    """Return a compact overview of a scenario-builder configuration."""
    cfg = config if isinstance(config, dict) else {}
    initial = _dict(cfg.get("initial"))
    guidance = _dict(cfg.get("guidance"))
    sensors = _dict(cfg.get("sensors"))
    events = _dict(cfg.get("events"))
    position = _vector(initial.get("position_m"))
    velocity = _vector(initial.get("velocity_mps"))
    euler = _vector(initial.get("euler_deg"))

    summary: dict[str, Any] = {
        "name": cfg.get("name", "scenario"),
        "duration": cfg.get("duration"),
        "dt": cfg.get("dt"),
        "vehicle_config": cfg.get("vehicle_config"),
        "environment_config": cfg.get("environment_config"),
        "guidance_mode": guidance.get("mode"),
        "initial": {
            "altitude_m": position[2] if position is not None else None,
            "speed_mps": _norm(velocity),
            "pitch_deg": euler[1] if euler is not None else None,
            "heading_deg": euler[2] if euler is not None else None,
        },
        "counts": {
            "targets": _count_list(cfg.get("targets")),
            "interceptors": _count_list(cfg.get("interceptors")),
            "faults": _count_list(sensors.get("faults")) + _count_list(cfg.get("faults")),
        },
        "termination_limits": _termination_limits(events),
    }
    for key in ("outputs", "output", "report", "reports"):
        if key in cfg:
            summary[key] = cfg[key]
    return summary


def scenario_builder_warnings(config: dict) -> list[dict]:
    """Return structured advisory warnings for draft scenario configs."""
    cfg = config if isinstance(config, dict) else {}
    warnings: list[dict] = []
    initial = _dict(cfg.get("initial"))
    guidance = _dict(cfg.get("guidance"))
    sensors = _dict(cfg.get("sensors"))
    events = _dict(cfg.get("events"))
    environment = _dict(cfg.get("environment"))

    _check_model_links(cfg, warnings)
    _check_timing(cfg, warnings)
    _check_initial_state(initial, warnings)
    _check_guidance(guidance, cfg, warnings)
    _check_sensors(sensors, warnings)
    _check_engagement_links(cfg, guidance, warnings)
    _check_termination(events, cfg, warnings)
    _check_terrain_contact(environment, events, warnings)
    return warnings


def scenario_builder_explanation(config: dict) -> str:
    """Return a concise human-readable description of a scenario draft."""
    summary = scenario_builder_summary(config)
    initial = summary["initial"]
    counts = summary["counts"]
    pieces = [
        f"{summary['name']} runs for {_fmt(summary.get('duration'))} s",
        f"at dt {_fmt(summary.get('dt'))} s",
        f"using {summary.get('guidance_mode') or 'unspecified'} guidance",
    ]
    if initial.get("altitude_m") is not None or initial.get("speed_mps") is not None:
        pieces.append(
            f"from {_fmt(initial.get('altitude_m'))} m altitude and {_fmt(initial.get('speed_mps'))} m/s"
        )
    if counts["targets"] or counts["interceptors"]:
        pieces.append(f"with {counts['targets']} target(s) and {counts['interceptors']} interceptor(s)")
    if counts["faults"]:
        pieces.append(f"including {counts['faults']} sensor fault(s)")
    return "; ".join(pieces) + "."


def scenario_builder_recommendations(config: dict) -> list[str]:
    """Return mission-design recommendations for scenario-builder users."""
    cfg = config if isinstance(config, dict) else {}
    summary = scenario_builder_summary(cfg)
    guidance_mode = str(summary.get("guidance_mode") or "").lower()
    limits = summary.get("termination_limits", {})
    counts = summary["counts"]
    recs: list[str] = []

    recs.append("Keep dt small enough for control and sensor events, then compare one run at half the timestep.")
    if not cfg.get("vehicle_config") and not cfg.get("vehicle"):
        recs.append("Choose a concrete vehicle model before tuning guidance or event limits.")
    if not cfg.get("environment_config") and not cfg.get("environment"):
        recs.append("Select the range environment early so wind, density, terrain, and contact assumptions are explicit.")
    if "target" in guidance_mode or counts["targets"] or counts["interceptors"]:
        recs.append("Give every target a stable id and link each interceptor target_id to the intended primary target.")
        recs.append("Set target_threshold_m and interceptor proximity_fuze_m from the mission miss-distance requirement.")
    if counts["faults"]:
        recs.append("Run the same scenario without sensor faults first, then add one fault at a time for attribution.")
    if not limits:
        recs.append("Add qbar and load-factor termination limits before campaign or Monte Carlo runs.")
    elif "qbar_limit_pa" not in limits or "load_limit_g" not in limits:
        recs.append("Use both qbar_limit_pa and load_limit_g so aerodynamic and structural excursions are visible.")
    if _has_terrain_or_contact(cfg):
        recs.append("For terrain/contact scenarios, start above local terrain and check altitude AGL telemetry in the first dry run.")
    return _dedupe(recs)


def _check_model_links(cfg: dict[str, Any], warnings: list[dict]) -> None:
    if not cfg.get("vehicle_config") and not isinstance(cfg.get("vehicle"), dict):
        _warn(warnings, "warning", "vehicle", "vehicle_config", "Missing vehicle_config or inline vehicle model.")
    if not cfg.get("environment_config") and not isinstance(cfg.get("environment"), dict):
        _warn(warnings, "caution", "environment", "environment_config", "Missing environment_config or inline environment model.")


def _check_timing(cfg: dict[str, Any], warnings: list[dict]) -> None:
    duration = _number(cfg.get("duration"))
    dt = _number(cfg.get("dt"))
    if duration is None or duration <= 0.0:
        _warn(warnings, "warning", "timing", "duration", "Duration should be a positive finite number.")
    elif duration < 1.0:
        _warn(warnings, "caution", "timing", "duration", "Duration is very short for mission-level evaluation.")
    if dt is None or dt <= 0.0:
        _warn(warnings, "warning", "timing", "dt", "Timestep should be a positive finite number.")
    elif dt > 0.1:
        _warn(warnings, "caution", "timing", "dt", "Timestep is coarse for closed-loop 6DOF dynamics.")
    if duration and dt and duration > 0.0 and dt > 0.0:
        steps = duration / dt
        if steps > 500_000:
            _warn(warnings, "warning", "timing", "duration/dt", "Scenario creates more than 500000 integration steps.")
        elif steps < 50:
            _warn(warnings, "caution", "timing", "duration/dt", "Scenario has very few integration steps.")


def _check_initial_state(initial: dict[str, Any], warnings: list[dict]) -> None:
    position = _vector(initial.get("position_m"))
    velocity = _vector(initial.get("velocity_mps"))
    euler = _vector(initial.get("euler_deg"))
    if position is None:
        _warn(warnings, "caution", "initial", "initial.position_m", "Initial position should be a three-element vector.")
    elif position[2] < 0.0:
        _warn(warnings, "warning", "initial", "initial.position_m[2]", "Initial altitude is below zero meters.")
    elif position[2] < 5.0:
        _warn(warnings, "info", "initial", "initial.position_m[2]", "Initial altitude is close to ground level.")
    if velocity is None:
        _warn(warnings, "caution", "initial", "initial.velocity_mps", "Initial velocity should be a three-element vector.")
    else:
        speed = _norm(velocity)
        if speed is not None and speed < 5.0:
            _warn(warnings, "caution", "initial", "initial.velocity_mps", "Initial speed is very low for fixed-wing or missile scenarios.")
    if euler is None:
        _warn(warnings, "info", "initial", "initial.euler_deg", "Initial attitude is not specified.")
    else:
        roll, pitch, heading = euler
        if abs(roll) > 80.0 or abs(pitch) > 60.0:
            _warn(warnings, "caution", "initial", "initial.euler_deg", "Initial attitude is unusually steep.")
        if abs(heading) > 360.0:
            _warn(warnings, "info", "initial", "initial.euler_deg[2]", "Heading is outside the conventional +/-360 degree range.")


def _check_guidance(guidance: dict[str, Any], cfg: dict[str, Any], warnings: list[dict]) -> None:
    if not guidance:
        _warn(warnings, "caution", "guidance", "guidance", "Missing guidance block.")
        return
    if not guidance.get("mode"):
        _warn(warnings, "info", "guidance", "guidance.mode", "Guidance mode is not specified.")
    throttle = guidance.get("throttle")
    if throttle is not None:
        value = _number(throttle)
        if value is None:
            _warn(warnings, "warning", "guidance", "guidance.throttle", "Throttle should be numeric.")
        elif not 0.0 <= value <= 1.0:
            _warn(warnings, "warning", "guidance", "guidance.throttle", "Throttle is outside the 0..1 command range.")
        elif value > 0.95:
            _warn(warnings, "info", "guidance", "guidance.throttle", "Throttle is near maximum; check thrust margin.")
    if str(guidance.get("mode", "")).lower() == "target_intercept" and "target_position_m" not in guidance and not cfg.get("targets"):
        _warn(warnings, "warning", "guidance", "guidance.target_position_m", "Target-intercept guidance needs a target position or target list.")


def _check_sensors(sensors: dict[str, Any], warnings: list[dict]) -> None:
    for key in ("imu_rate_hz", "gps_rate_hz", "baro_rate_hz"):
        if key in sensors:
            _check_rate(sensors[key], f"sensors.{key}", warnings)
    for name, sensor_cfg in sensors.items():
        if name in {"seed", "faults"}:
            continue
        path = f"sensors.{name}"
        if isinstance(sensor_cfg, dict):
            if "rate_hz" in sensor_cfg:
                _check_rate(sensor_cfg["rate_hz"], f"{path}.rate_hz", warnings)
            for key, value in sensor_cfg.items():
                if "noise" in key or "std" in key or "dropout" in key or "latency" in key:
                    _check_nonnegative(value, f"{path}.{key}", warnings)
        elif "noise" in name or "std" in name or "dropout" in name:
            _check_nonnegative(sensor_cfg, path, warnings)
    faults = sensors.get("faults", [])
    if faults in (None, []):
        return
    if not isinstance(faults, list):
        _warn(warnings, "warning", "sensors", "sensors.faults", "Sensor faults should be a list.")
        return
    for idx, fault in enumerate(faults):
        path = f"sensors.faults[{idx}]"
        if not isinstance(fault, dict):
            _warn(warnings, "warning", "sensors", path, "Sensor fault should be an object.")
            continue
        if not (fault.get("sensor") or fault.get("target") or fault.get("name") or fault.get("sensors")):
            _warn(warnings, "warning", "sensors", path, "Sensor fault should identify sensor or sensors.")
        if not fault.get("type"):
            _warn(warnings, "info", "sensors", f"{path}.type", "Sensor fault type defaults in validation; make it explicit for scenario review.")
        start = _number(fault.get("start_s", 0.0))
        end = _number(fault.get("end_s", 1e99))
        if start is None or end is None:
            _warn(warnings, "warning", "sensors", path, "Sensor fault start_s and end_s should be numeric.")
        elif end < start:
            _warn(warnings, "warning", "sensors", f"{path}.end_s", "Sensor fault end_s is before start_s.")


def _check_engagement_links(cfg: dict[str, Any], guidance: dict[str, Any], warnings: list[dict]) -> None:
    targets = cfg.get("targets", [])
    interceptors = cfg.get("interceptors", [])
    target_ids = {
        str(target.get("id"))
        for target in targets
        if isinstance(targets, list) and isinstance(target, dict) and target.get("id")
    }
    if "target" in str(guidance.get("mode", "")).lower() and not targets and "target_position_m" not in guidance:
        _warn(warnings, "warning", "engagement", "targets", "Target-focused guidance has no target list or target_position_m.")
    if interceptors and not isinstance(interceptors, list):
        _warn(warnings, "warning", "engagement", "interceptors", "Interceptors should be a list.")
        return
    if isinstance(interceptors, list):
        for idx, interceptor in enumerate(interceptors):
            path = f"interceptors[{idx}]"
            if not isinstance(interceptor, dict):
                _warn(warnings, "warning", "engagement", path, "Interceptor should be an object.")
                continue
            target_id = interceptor.get("target_id")
            if not target_id:
                _warn(warnings, "warning", "engagement", f"{path}.target_id", "Interceptor is missing target_id.")
            elif target_ids and str(target_id) not in target_ids:
                _warn(warnings, "warning", "engagement", f"{path}.target_id", "Interceptor target_id does not match a configured target.")
            if "proximity_fuze_m" not in interceptor:
                _warn(warnings, "info", "engagement", f"{path}.proximity_fuze_m", "Interceptor has no proximity fuze distance.")
    if targets and not isinstance(targets, list):
        _warn(warnings, "warning", "engagement", "targets", "Targets should be a list.")


def _check_termination(events: dict[str, Any], cfg: dict[str, Any], warnings: list[dict]) -> None:
    if not events:
        _warn(warnings, "caution", "termination", "events", "No termination/event limits are configured.")
        return
    for key in ("qbar_limit_pa", "load_limit_g", "target_threshold_m"):
        if key in events:
            value = _number(events[key])
            if value is None or value <= 0.0:
                _warn(warnings, "warning", "termination", f"events.{key}", f"{key} should be a positive finite number.")
    if "qbar_limit_pa" not in events:
        _warn(warnings, "info", "termination", "events.qbar_limit_pa", "No dynamic-pressure limit is configured.")
    if "load_limit_g" not in events:
        _warn(warnings, "info", "termination", "events.load_limit_g", "No load-factor limit is configured.")
    if (cfg.get("targets") or str(_dict(cfg.get("guidance")).get("mode", "")).lower().find("target") >= 0) and "target_threshold_m" not in events:
        _warn(warnings, "caution", "termination", "events.target_threshold_m", "Targeted scenario has no target miss-distance threshold.")
    qbar = _number(events.get("qbar_limit_pa"))
    load = _number(events.get("load_limit_g"))
    if qbar is not None and qbar > 200_000.0:
        _warn(warnings, "caution", "termination", "events.qbar_limit_pa", "Dynamic-pressure limit is very high.")
    if load is not None and load > 25.0:
        _warn(warnings, "caution", "termination", "events.load_limit_g", "Load-factor limit is very high.")


def _check_terrain_contact(environment: dict[str, Any], events: dict[str, Any], warnings: list[dict]) -> None:
    terrain = _dict(environment.get("terrain"))
    contact = _dict(environment.get("ground_contact"))
    event_contact = _dict(events.get("ground_contact"))
    if terrain and not contact and not event_contact:
        _warn(warnings, "info", "terrain", "environment.terrain", "Terrain is configured without explicit ground_contact settings.")
    for section, path in ((contact, "environment.ground_contact"), (event_contact, "events.ground_contact")):
        if not section:
            continue
        if "enabled" in section and section.get("enabled") and section.get("mode") not in (None, "terminate", "bounce", "slide", "settle"):
            _warn(warnings, "caution", "terrain", f"{path}.mode", "Ground-contact mode is not a common mode.")
        for key in ("touchdown_speed_mps", "impact_speed_mps", "crash_speed_mps"):
            if key in section:
                _check_nonnegative(section[key], f"{path}.{key}", warnings)


def _termination_limits(events: dict[str, Any]) -> dict[str, Any]:
    return {key: events[key] for key in ("qbar_limit_pa", "load_limit_g", "target_threshold_m") if key in events}


def _has_terrain_or_contact(cfg: dict[str, Any]) -> bool:
    env = _dict(cfg.get("environment"))
    events = _dict(cfg.get("events"))
    return bool(env.get("terrain") or env.get("ground_contact") or events.get("ground_contact"))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _vector(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    numbers = [_number(item) for item in value]
    if any(item is None for item in numbers):
        return None
    return (float(numbers[0]), float(numbers[1]), float(numbers[2]))


def _norm(vector: tuple[float, float, float] | None) -> float | None:
    if vector is None:
        return None
    return math.sqrt(sum(component * component for component in vector))


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _check_rate(value: Any, path: str, warnings: list[dict]) -> None:
    rate = _number(value)
    if rate is None:
        _warn(warnings, "warning", "sensors", path, "Sensor rate should be numeric.")
    elif rate < 0.0:
        _warn(warnings, "warning", "sensors", path, "Sensor rate cannot be negative.")
    elif rate == 0.0:
        _warn(warnings, "info", "sensors", path, "Sensor rate is zero; confirm this sensor should be disabled.")
    elif rate < 1.0:
        _warn(warnings, "caution", "sensors", path, "Sensor rate is very low for closed-loop guidance.")


def _check_nonnegative(value: Any, path: str, warnings: list[dict]) -> None:
    number = _number(value)
    if number is None:
        _warn(warnings, "warning", "sensors", path, "Sensor numeric setting should be finite.")
    elif number < 0.0:
        _warn(warnings, "warning", "sensors", path, "Sensor noise/dropout/latency setting cannot be negative.")


def _warn(warnings: list[dict], severity: str, section: str, path: str, message: str) -> None:
    warnings.append({"severity": severity, "section": section, "path": path, "message": message})


def _fmt(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "unknown"
    return f"{number:.3g}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
