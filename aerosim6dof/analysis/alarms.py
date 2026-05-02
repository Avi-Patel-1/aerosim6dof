"""Alarm and limit monitoring derived from simulator output artifacts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from aerosim6dof.reports.csv_writer import read_csv

AlarmSeverity = Literal["info", "caution", "warning", "critical"]

TelemetryRow = dict[str, Any]
AlarmContext = dict[str, Any]
AlarmPredicate = Callable[[TelemetryRow, AlarmContext], bool]


@dataclass(frozen=True)
class AlarmRule:
    id: str
    name: str
    severity: AlarmSeverity
    source: str
    subsystem: str
    message: str
    threshold: str
    channels: tuple[str, ...]
    datasets: tuple[str, ...]
    predicate: AlarmPredicate


def evaluate_run_alarms(run_dir: str | Path) -> list[dict[str, Any]]:
    """Evaluate alarm rules against an output run directory.

    The monitor is intentionally read-only: it consumes existing CSV/JSON
    artifacts and never feeds values back into the simulator.
    """
    path = Path(run_dir)
    datasets = {
        "history": _read_csv_if_present(path / "history.csv"),
        "truth": _read_csv_if_present(path / "truth.csv"),
        "controls": _read_csv_if_present(path / "controls.csv"),
        "sensors": _read_csv_if_present(path / "sensors.csv"),
    }
    summary = _read_json_if_present(path / "summary.json")
    events = _read_json_if_present(path / "events.json")
    scenario = _read_json_if_present(path / "scenario_resolved.json")
    return evaluate_alarms(
        history=datasets["history"],
        truth=datasets["truth"],
        controls=datasets["controls"],
        sensors=datasets["sensors"],
        summary=summary if isinstance(summary, dict) else {},
        events=events if isinstance(events, list) else [],
        scenario=scenario if isinstance(scenario, dict) else {},
    )


def evaluate_alarms(
    *,
    history: list[TelemetryRow] | None = None,
    truth: list[TelemetryRow] | None = None,
    controls: list[TelemetryRow] | None = None,
    sensors: list[TelemetryRow] | None = None,
    summary: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    scenario: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate configured alarms from telemetry rows and summary data."""
    datasets = {
        "history": history or [],
        "truth": truth or [],
        "controls": controls or [],
        "sensors": sensors or [],
    }
    context = {"summary": summary or {}, "events": events or [], "scenario": scenario or {}}
    alarms: list[dict[str, Any]] = []
    for rule in ALARM_RULES:
        rows = _rows_for_rule(rule, datasets)
        if not rows:
            continue
        alarm = _evaluate_rule(rule, rows, context)
        if alarm is not None:
            alarms.append(alarm)
    miss_alarm = _target_miss_alarm(summary or {}, events or [])
    if miss_alarm is not None:
        alarms.append(miss_alarm)
    return sorted(alarms, key=lambda item: (_severity_rank(str(item["severity"])), float(item["first_triggered_time_s"])))


def _evaluate_rule(rule: AlarmRule, rows: list[TelemetryRow], context: AlarmContext) -> dict[str, Any] | None:
    first_time: float | None = None
    last_time: float | None = None
    cleared_time: float | None = None
    active = False
    occurrence_count = 0

    for row in rows:
        if not _has_required_channels(row, rule.channels):
            continue
        time_s = _number(row.get("time_s"))
        if time_s is None:
            continue
        try:
            triggered = bool(rule.predicate(row, context))
        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            continue
        if triggered:
            occurrence_count += 1
            first_time = time_s if first_time is None else first_time
            last_time = time_s
            cleared_time = None
            active = True
        elif active:
            cleared_time = time_s
            active = False

    if first_time is None or last_time is None:
        return None
    return _alarm_payload(
        rule=rule,
        first_time=first_time,
        last_time=last_time,
        cleared_time=cleared_time,
        active=active,
        occurrence_count=occurrence_count,
    )


def _alarm_payload(
    *,
    rule: AlarmRule,
    first_time: float,
    last_time: float,
    cleared_time: float | None,
    active: bool,
    occurrence_count: int,
) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "severity": rule.severity,
        "source": rule.source,
        "subsystem": rule.subsystem,
        "message": rule.message,
        "channel": rule.channels[0] if rule.channels else None,
        "threshold": rule.threshold,
        "rule": rule.threshold,
        "first_triggered_time_s": first_time,
        "last_triggered_time_s": last_time,
        "cleared_time_s": cleared_time,
        "active": active,
        "occurrence_count": occurrence_count,
        "sample_count": occurrence_count,
    }


def _target_miss_alarm(summary: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any] | None:
    distance = _number(summary.get("min_target_distance_m"))
    if distance is None:
        final = summary.get("final")
        if isinstance(final, dict):
            distance = _number(final.get("target_distance_m"))
    if distance is None or distance <= TARGET_MISS_DISTANCE_M:
        return None

    final = summary.get("final")
    time_s = _number(final.get("time_s")) if isinstance(final, dict) else None
    if time_s is None:
        time_s = _last_event_time(events) or 0.0
    rule = AlarmRule(
        id="TARGET_MISS_DISTANCE_HIGH",
        name="Target Miss Distance High",
        severity="caution",
        source="summary",
        subsystem="GNC",
        message=f"Minimum target miss distance exceeded {TARGET_MISS_DISTANCE_M:.0f} m.",
        threshold=f"min_target_distance_m > {TARGET_MISS_DISTANCE_M:.0f} m",
        channels=("target_distance_m",),
        datasets=("history",),
        predicate=lambda _row, _context: False,
    )
    return _alarm_payload(
        rule=rule,
        first_time=time_s,
        last_time=time_s,
        cleared_time=None,
        active=True,
        occurrence_count=1,
    )


def _rows_for_rule(rule: AlarmRule, datasets: dict[str, list[TelemetryRow]]) -> list[TelemetryRow]:
    for name in rule.datasets:
        rows = datasets.get(name, [])
        if rows and any(_has_required_channels(row, rule.channels) for row in rows):
            return rows
    return []


def _has_required_channels(row: TelemetryRow, channels: tuple[str, ...]) -> bool:
    return all(channel in row for channel in channels)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    return number


def _flag(row: TelemetryRow, key: str) -> bool:
    value = _number(row.get(key))
    return value is not None and value > 0.5


def _greater(row: TelemetryRow, key: str, threshold: float) -> bool:
    value = _number(row.get(key))
    return value is not None and value > threshold


def _less(row: TelemetryRow, key: str, threshold: float) -> bool:
    value = _number(row.get(key))
    return value is not None and value < threshold


def _low_altitude_descent(row: TelemetryRow) -> bool:
    altitude = _number(row.get("altitude_agl_m"))
    if altitude is None:
        altitude = _number(row.get("altitude_m"))
    vertical_speed = _number(row.get("vz_mps"))
    return altitude is not None and vertical_speed is not None and altitude < 100.0 and vertical_speed < -20.0


def _engine_thrust_loss(row: TelemetryRow, context: AlarmContext) -> bool:
    thrust = _number(row.get("thrust_n"))
    throttle = _number(row.get("throttle"))
    time_s = _number(row.get("time_s"))
    burn_time = _scenario_propulsion_number(context.get("scenario"), "burn_time_s")
    if time_s is not None and burn_time is not None and time_s >= burn_time - 0.05:
        return False
    dry_mass = _scenario_vehicle_number(context.get("scenario"), "dry_mass_kg")
    mass = _number(row.get("mass_kg"))
    if dry_mass is not None and mass is not None and mass <= dry_mass + 0.2:
        return False
    return thrust is not None and throttle is not None and throttle > 0.2 and thrust < 1.0


def _actuator_saturated(row: TelemetryRow) -> bool:
    return any(_flag(row, channel) for channel in ACTUATOR_SATURATION_CHANNELS)


def _scenario_vehicle_number(scenario: Any, key: str) -> float | None:
    if not isinstance(scenario, dict):
        return None
    vehicle = scenario.get("vehicle")
    if not isinstance(vehicle, dict):
        return None
    return _number(vehicle.get(key))


def _scenario_propulsion_number(scenario: Any, key: str) -> float | None:
    if not isinstance(scenario, dict):
        return None
    vehicle = scenario.get("vehicle")
    if not isinstance(vehicle, dict):
        return None
    propulsion = vehicle.get("propulsion")
    if not isinstance(propulsion, dict):
        return None
    return _number(propulsion.get(key))


def _read_csv_if_present(path: Path) -> list[TelemetryRow]:
    if not path.exists():
        return []
    try:
        return list(read_csv(path))
    except (OSError, ValueError):
        return []


def _read_json_if_present(path: Path) -> Any:
    if not path.exists():
        return {} if path.name == "summary.json" else []
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {} if path.name == "summary.json" else []


def _last_event_time(events: list[dict[str, Any]]) -> float | None:
    times = [_number(event.get("time_s")) for event in events]
    finite_times = [time for time in times if time is not None]
    return max(finite_times) if finite_times else None


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "warning": 1, "caution": 2, "info": 3}.get(severity, 4)


QBAR_HIGH_PA = 60000.0
LOAD_FACTOR_LIMIT_G = 6.0
STALL_ALPHA_DEG = 18.0
TARGET_MISS_DISTANCE_M = 100.0
ACTUATOR_SATURATION_CHANNELS = ("elevator_saturated", "aileron_saturated", "rudder_saturated")

ALARM_RULES: tuple[AlarmRule, ...] = (
    AlarmRule(
        id="QBAR_HIGH",
        name="Dynamic Pressure High",
        severity="warning",
        source="history",
        subsystem="Aerodynamics",
        message="Dynamic pressure exceeded the warning ceiling.",
        threshold=f"qbar_pa > {QBAR_HIGH_PA:.0f} Pa",
        channels=("qbar_pa",),
        datasets=("history", "truth"),
        predicate=lambda row, _context: _greater(row, "qbar_pa", QBAR_HIGH_PA),
    ),
    AlarmRule(
        id="LOAD_FACTOR_LIMIT",
        name="Load Factor Limit",
        severity="warning",
        source="history",
        subsystem="Aerodynamics",
        message="Vehicle load factor exceeded the configured warning limit.",
        threshold=f"load_factor_g > {LOAD_FACTOR_LIMIT_G:.1f} g",
        channels=("load_factor_g",),
        datasets=("history", "truth"),
        predicate=lambda row, _context: _greater(row, "load_factor_g", LOAD_FACTOR_LIMIT_G),
    ),
    AlarmRule(
        id="GPS_DROPOUT",
        name="GPS Dropout",
        severity="caution",
        source="sensors",
        subsystem="Sensors",
        message="GPS validity flag dropped out during the run.",
        threshold="gps_valid <= 0",
        channels=("gps_valid",),
        datasets=("history", "sensors"),
        predicate=lambda row, _context: _less(row, "gps_valid", 0.5),
    ),
    AlarmRule(
        id="ACTUATOR_SATURATION",
        name="Actuator Saturation",
        severity="caution",
        source="controls",
        subsystem="Actuators",
        message="One or more control effectors reached a saturation limit.",
        threshold="any actuator_saturated flag > 0",
        channels=ACTUATOR_SATURATION_CHANNELS,
        datasets=("history", "controls"),
        predicate=lambda row, _context: _actuator_saturated(row),
    ),
    AlarmRule(
        id="LOW_ALTITUDE_HIGH_DESCENT_RATE",
        name="Low Altitude High Descent Rate",
        severity="critical",
        source="history",
        subsystem="Flight Safety",
        message="Vehicle descended rapidly below the low-altitude safety gate.",
        threshold="altitude_agl_m < 100 m and vz_mps < -20 m/s",
        channels=("altitude_m", "vz_mps"),
        datasets=("history", "truth"),
        predicate=lambda row, _context: _low_altitude_descent(row),
    ),
    AlarmRule(
        id="ENGINE_THRUST_LOSS",
        name="Engine Thrust Loss",
        severity="critical",
        source="history",
        subsystem="Propulsion",
        message="Commanded throttle remained high while delivered thrust collapsed.",
        threshold="throttle > 0.2 and thrust_n < 1 N",
        channels=("thrust_n", "throttle"),
        datasets=("history",),
        predicate=_engine_thrust_loss,
    ),
    AlarmRule(
        id="STALL_MARGIN_LOW",
        name="Stall Margin Low",
        severity="warning",
        source="history",
        subsystem="Aerodynamics",
        message="Angle of attack moved outside the nominal stall-margin envelope.",
        threshold=f"abs(alpha_deg) > {STALL_ALPHA_DEG:.0f} deg",
        channels=("alpha_deg",),
        datasets=("history", "truth"),
        predicate=lambda row, _context: (value := _number(row.get("alpha_deg"))) is not None and abs(value) > STALL_ALPHA_DEG,
    ),
)
