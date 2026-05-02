"""Read-only missile engagement comparison packets from existing run outputs."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from aerosim6dof.reports.csv_writer import read_csv


MISSILE_HISTORY_COLUMNS = {
    "missile_mode",
    "seeker_valid",
    "missile_guidance_valid",
    "missile_seeker_range_m",
    "missile_closing_speed_mps",
    "missile_motor_phase",
    "missile_motor_thrust_n",
    "missile_lateral_accel_mps2",
    "missile_control_saturated",
    "missile_fuze_armed",
    "missile_fuzed",
    "missile_fuze_status",
}


def build_missile_engagement_comparison(
    run_dirs: list[str | Path],
    *,
    run_ids: list[str] | None = None,
    max_samples: int = 240,
) -> dict[str, Any]:
    """Assemble a side-by-side packet for missile engagement runs.

    The packet is intentionally derived only from existing artifacts so the API
    can compare showcase runs without rerunning simulations or writing reports.
    """

    ids = run_ids if run_ids is not None else [Path(path).name for path in run_dirs]
    runs = [_run_packet(Path(path), ids[index] if index < len(ids) else Path(path).name, max_samples=max_samples) for index, path in enumerate(run_dirs)]
    runs = [run for run in runs if run["available"]]
    return {
        "schema": "aerosim6dof.missile_engagement_comparison.v1",
        "run_count": len(runs),
        "runs": runs,
        "comparison_table": [_comparison_row(run) for run in runs],
        "timeline_channels": [
            "seeker_locked",
            "range_m",
            "range_rate_mps",
            "closing_speed_mps",
            "motor_phase",
            "motor_thrust_n",
            "lateral_accel_mps2",
            "control_saturated",
            "fuze_armed",
            "fuze_fuzed",
            "miss_distance_m",
        ],
    }


def is_missile_showcase_run(run_dir: str | Path) -> bool:
    run = Path(run_dir)
    summary = _read_json_object(run / "summary.json")
    scenario = str(summary.get("scenario", run.name)).lower()
    if "missile" not in scenario:
        return False
    if "showcase" in scenario:
        return True
    return _has_missile_outputs(run)


def _run_packet(run: Path, run_id: str, *, max_samples: int) -> dict[str, Any]:
    summary = _read_json_object(run / "summary.json")
    events = _read_json_list(run / "events.json")
    history = _read_rows(run / "history.csv")
    interceptors = _read_rows(run / "interceptors.csv")
    source_rows = interceptors if _rows_have_missile_data(interceptors) else history
    available = bool(summary or history or interceptors) and _has_missile_outputs(run)
    scenario = str(summary.get("scenario", run.name))
    samples = _timeline_samples(source_rows, max_samples=max_samples)
    miss_metric = _miss_distance(summary, source_rows, events)
    closest_timeline = _closest_approach_timeline(source_rows, events, max_samples=max_samples)
    return {
        "id": run_id,
        "scenario": scenario,
        "run_dir": str(run),
        "available": available,
        "sample_count": len(source_rows),
        "summary": {
            "miss_distance_m": miss_metric,
            "closest_approach_time_s": _metric_time(miss_metric),
            "first_seeker_lock_time_s": _first_lock_time(source_rows),
            "seeker_lock_fraction": _lock_fraction(source_rows),
            "first_fuze_time_s": _first_flag_time(source_rows, "missile_fuzed") or _event_time(events, "interceptor_fuze"),
            "max_lateral_accel_mps2": _max_abs(source_rows, "missile_lateral_accel_mps2"),
            "max_closing_speed_mps": _finite_max(_series(source_rows, "missile_closing_speed_mps")),
            "actuator_saturation_count": _flag_count(source_rows, "missile_control_saturated"),
            "actuator_saturation_fraction": _flag_fraction(source_rows, "missile_control_saturated"),
            "motor_phases": _ordered_strings(source_rows, "missile_motor_phase"),
            "fuze_states": _ordered_strings(source_rows, "missile_fuze_status"),
            "interceptor_id": _first_string(source_rows, "interceptor_id"),
            "target_id": _first_string(source_rows, "interceptor_target_id") or _first_string(source_rows, "target_id"),
        },
        "seeker_lock": {
            "ever_locked": any(sample["seeker_locked"] for sample in samples),
            "first_lock_time_s": _first_lock_time(source_rows),
            "lock_fraction": _lock_fraction(source_rows),
            "locked_sample_count": sum(1 for row in source_rows if _locked(row)),
            "timeline": [
                {
                    "time_s": sample["time_s"],
                    "locked": sample["seeker_locked"],
                    "status": sample["seeker_status"],
                    "range_m": sample["range_m"],
                }
                for sample in samples
            ],
        },
        "range": {
            "min_range_m": _metric_value(miss_metric),
            "timeline": [
                {
                    "time_s": sample["time_s"],
                    "range_m": sample["range_m"],
                    "range_rate_mps": sample["range_rate_mps"],
                    "closing_speed_mps": sample["closing_speed_mps"],
                }
                for sample in samples
            ],
        },
        "motor": {
            "phase_sequence": _phase_sequence(source_rows),
            "phase_intervals": _phase_intervals(source_rows, "missile_motor_phase"),
            "timeline": [
                {
                    "time_s": sample["time_s"],
                    "phase": sample["motor_phase"],
                    "thrust_n": sample["motor_thrust_n"],
                    "spool_fraction": sample["motor_spool_fraction"],
                }
                for sample in samples
            ],
        },
        "lateral_acceleration": {
            "max_abs_mps2": _max_abs(source_rows, "missile_lateral_accel_mps2"),
            "timeline": [{"time_s": sample["time_s"], "lateral_accel_mps2": sample["lateral_accel_mps2"]} for sample in samples],
        },
        "actuator_saturation": {
            "count": _flag_count(source_rows, "missile_control_saturated"),
            "fraction": _flag_fraction(source_rows, "missile_control_saturated"),
            "first_time_s": _first_flag_time(source_rows, "missile_control_saturated"),
            "events": [
                {
                    "time_s": _number(event.get("time_s")),
                    "type": str(event.get("type", "")),
                    "description": str(event.get("description", event.get("message", ""))),
                }
                for event in events
                if str(event.get("type", "")) == "actuator_saturation"
            ],
            "timeline": [{"time_s": sample["time_s"], "saturated": sample["control_saturated"]} for sample in samples],
        },
        "fuze": {
            "first_armed_time_s": _first_flag_time(source_rows, "missile_fuze_armed"),
            "first_fuzed_time_s": _first_flag_time(source_rows, "missile_fuzed") or _event_time(events, "interceptor_fuze"),
            "state_intervals": _phase_intervals(source_rows, "missile_fuze_status"),
            "timeline": [
                {
                    "time_s": sample["time_s"],
                    "armed": sample["fuze_armed"],
                    "fuzed": sample["fuze_fuzed"],
                    "status": sample["fuze_status"],
                    "closest_range_m": sample["fuze_closest_range_m"],
                }
                for sample in samples
            ],
        },
        "miss_distance": miss_metric,
        "closest_approach_timeline": closest_timeline,
    }


def _timeline_samples(rows: list[dict[str, Any]], *, max_samples: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for row in _sample_rows(rows, max_samples=max_samples):
        closing = _first_number(row, "missile_closing_speed_mps", "interceptor_closing_speed_mps", "closing_speed_mps")
        range_rate = _first_number(row, "interceptor_range_rate_mps", "target_range_rate_mps")
        if range_rate is None and closing is not None:
            range_rate = -closing
        samples.append(
            {
                "time_s": _number(row.get("time_s")),
                "seeker_locked": _locked(row),
                "seeker_status": str(row.get("missile_seeker_status", "")),
                "range_m": _first_number(row, "missile_seeker_range_m", "interceptor_range_m", "target_range_m"),
                "range_rate_mps": range_rate,
                "closing_speed_mps": closing,
                "motor_phase": str(row.get("missile_motor_phase", "")),
                "motor_thrust_n": _number(row.get("missile_motor_thrust_n")),
                "motor_spool_fraction": _number(row.get("missile_motor_spool_fraction")),
                "lateral_accel_mps2": _number(row.get("missile_lateral_accel_mps2")),
                "control_saturated": _flag(row.get("missile_control_saturated")),
                "fuze_armed": _flag(row.get("missile_fuze_armed")),
                "fuze_fuzed": _flag(row.get("missile_fuzed")) or _flag(row.get("interceptor_fuzed")),
                "fuze_status": str(row.get("missile_fuze_status", "")),
                "fuze_closest_range_m": _number(row.get("missile_fuze_closest_range_m")),
                "miss_distance_m": _first_number(row, "interceptor_best_miss_m", "missile_fuze_closest_range_m", "interceptor_range_m"),
            }
        )
    return samples


def _closest_approach_timeline(rows: list[dict[str, Any]], events: list[dict[str, Any]], *, max_samples: int) -> dict[str, Any]:
    candidates = [row for row in rows if _first_number(row, "interceptor_range_m", "missile_seeker_range_m", "target_range_m") is not None]
    if not candidates:
        return {"event": _closest_event(events), "samples": []}
    closest_index = min(
        range(len(candidates)),
        key=lambda index: _first_number(candidates[index], "interceptor_range_m", "missile_seeker_range_m", "target_range_m") or float("inf"),
    )
    window = max(2, min(10, max_samples // 8))
    start = max(0, closest_index - window)
    stop = min(len(candidates), closest_index + window + 1)
    return {
        "event": _closest_event(events),
        "samples": [
            {
                "time_s": _number(row.get("time_s")),
                "range_m": _first_number(row, "interceptor_range_m", "missile_seeker_range_m", "target_range_m"),
                "closing_speed_mps": _first_number(row, "missile_closing_speed_mps", "interceptor_closing_speed_mps", "closing_speed_mps"),
                "fuzed": _flag(row.get("missile_fuzed")) or _flag(row.get("interceptor_fuzed")),
            }
            for row in candidates[start:stop]
        ],
    }


def _comparison_row(run: dict[str, Any]) -> dict[str, Any]:
    summary = run["summary"]
    miss = run["miss_distance"]
    return {
        "id": run["id"],
        "scenario": run["scenario"],
        "miss_distance_m": _metric_value(miss),
        "closest_approach_time_s": _metric_time(miss),
        "first_seeker_lock_time_s": summary.get("first_seeker_lock_time_s"),
        "seeker_lock_fraction": summary.get("seeker_lock_fraction"),
        "first_fuze_time_s": summary.get("first_fuze_time_s"),
        "max_lateral_accel_mps2": summary.get("max_lateral_accel_mps2"),
        "max_closing_speed_mps": summary.get("max_closing_speed_mps"),
        "actuator_saturation_count": summary.get("actuator_saturation_count"),
        "actuator_saturation_fraction": summary.get("actuator_saturation_fraction"),
        "motor_phases": summary.get("motor_phases", []),
        "fuze_states": summary.get("fuze_states", []),
    }


def _miss_distance(summary: dict[str, Any], rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        _metric_with_source(summary.get("min_interceptor_range_m"), None, "summary.min_interceptor_range_m"),
        _series_min(rows, "interceptor_range_m"),
        _series_min(rows, "missile_fuze_closest_range_m"),
        _event_miss(events, "interceptor_fuze"),
        _event_miss(events, "interceptor_closest_approach"),
    ]
    finite = [candidate for candidate in candidates if candidate["value"] is not None]
    if not finite:
        return {"value": None, "time_s": None, "source": "unavailable"}
    return min(finite, key=lambda item: float(item["value"]))


def _phase_sequence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    last = None
    for row in rows:
        phase = str(row.get("missile_motor_phase", ""))
        if not phase or phase == last:
            continue
        sequence.append({"phase": phase, "start_time_s": _number(row.get("time_s"))})
        last = phase
    return sequence


def _phase_intervals(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    intervals: list[dict[str, Any]] = []
    active_value = ""
    active_start: float | None = None
    active_end: float | None = None
    for row in rows:
        value = str(row.get(key, "")).strip()
        time_s = _number(row.get("time_s"))
        if not value or time_s is None:
            continue
        if value != active_value:
            if active_value and active_start is not None:
                intervals.append({"value": active_value, "start_time_s": active_start, "end_time_s": active_end})
            active_value = value
            active_start = time_s
        active_end = time_s
    if active_value and active_start is not None:
        intervals.append({"value": active_value, "start_time_s": active_start, "end_time_s": active_end})
    return intervals


def _sample_rows(rows: list[dict[str, Any]], *, max_samples: int) -> list[dict[str, Any]]:
    if max_samples <= 0 or len(rows) <= max_samples:
        return rows
    step = max(1, math.ceil(len(rows) / max_samples))
    sampled = rows[::step]
    if rows[-1] is not sampled[-1]:
        sampled.append(rows[-1])
    return sampled


def _has_missile_outputs(run: Path) -> bool:
    for name in ("history.csv", "interceptors.csv"):
        path = run / name
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                header = set(handle.readline().strip().split(","))
        except OSError:
            continue
        if MISSILE_HISTORY_COLUMNS.intersection(header):
            return True
    return False


def _rows_have_missile_data(rows: list[dict[str, Any]]) -> bool:
    return any(any(key in row for key in MISSILE_HISTORY_COLUMNS) for row in rows)


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return read_csv(path)
    except (OSError, ValueError):
        return []


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _first_lock_time(rows: list[dict[str, Any]]) -> float | None:
    for row in rows:
        if _locked(row):
            return _number(row.get("time_s"))
    return None


def _first_flag_time(rows: list[dict[str, Any]], key: str) -> float | None:
    for row in rows:
        if _flag(row.get(key)):
            return _number(row.get("time_s"))
    return None


def _event_time(events: list[dict[str, Any]], event_type: str) -> float | None:
    for event in events:
        if str(event.get("type", "")) == event_type:
            return _number(event.get("time_s"))
    return None


def _closest_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event_type in ("interceptor_closest_approach", "interceptor_fuze", "closest_approach"):
        for event in events:
            if str(event.get("type", "")) == event_type:
                return {
                    "time_s": _number(event.get("time_s")),
                    "type": str(event.get("type", "")),
                    "target_id": str(event.get("target_id", "")),
                    "interceptor_id": str(event.get("interceptor_id", "")),
                    "miss_distance_m": _number(event.get("miss_distance_m")),
                    "description": str(event.get("description", event.get("message", ""))),
                }
    return None


def _event_miss(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for event in events:
        if str(event.get("type", "")) == event_type:
            return _metric_with_source(event.get("miss_distance_m"), event.get("time_s"), f"events.{event_type}")
    return {"value": None, "time_s": None, "source": f"events.{event_type}"}


def _series_min(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    best: dict[str, Any] = {"value": None, "time_s": None, "source": key}
    for row in rows:
        value = _number(row.get(key))
        if value is None:
            continue
        if best["value"] is None or value < float(best["value"]):
            best = {"value": value, "time_s": _number(row.get("time_s")), "source": key}
    return best


def _metric_with_source(value: Any, time_s: Any, source: str) -> dict[str, Any]:
    return {"value": _number(value), "time_s": _number(time_s), "source": source}


def _metric_value(metric: dict[str, Any]) -> float | None:
    return _number(metric.get("value"))


def _metric_time(metric: dict[str, Any]) -> float | None:
    return _number(metric.get("time_s"))


def _series(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _number(row.get(key))
        if value is not None:
            values.append(value)
    return values


def _finite_max(values: list[float]) -> float | None:
    return max(values) if values else None


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(value) for value in _series(rows, key)]
    return max(values) if values else None


def _flag_count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(1 for row in rows if _flag(row.get(key)))


def _flag_fraction(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    return _flag_count(rows, key) / len(rows)


def _lock_fraction(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if _locked(row)) / len(rows)


def _ordered_strings(rows: list[dict[str, Any]], key: str) -> list[str]:
    values: list[str] = []
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value and value not in values:
            values.append(value)
    return values


def _first_string(rows: list[dict[str, Any]], key: str) -> str | None:
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value and value.lower() != "nan":
            return value
    return None


def _first_number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _number(row.get(key))
        if value is not None:
            return value
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _flag(value: Any) -> bool:
    number = _number(value)
    if number is not None:
        return number > 0.5
    return str(value).strip().lower() in {"true", "valid", "locked", "armed", "fuzed"}


def _locked(row: dict[str, Any]) -> bool:
    status = str(row.get("missile_seeker_status", "")).strip().lower()
    return _flag(row.get("seeker_valid")) or _flag(row.get("missile_guidance_valid")) or status in {"valid", "locked", "tracking"}
