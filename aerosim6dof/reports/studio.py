"""Report Studio packet assembly helpers.

The helpers in this module are intentionally read-only.  They collect existing
run artifacts into a structured packet that a UI or later export command can
consume without adding report-generation dependencies.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aerosim6dof.analysis.alarms import evaluate_run_alarms
from aerosim6dof.reports.csv_writer import read_csv


REPORT_STUDIO_SCHEMA = "aerosim6dof.report_studio.packet.v1"
DEFAULT_PACKET_SECTIONS = ("summary", "events", "alarms", "telemetry", "engagement", "artifacts")

_SUMMARY_HIGHLIGHTS = (
    ("scenario", "Scenario", ""),
    ("duration_s", "Duration", "s"),
    ("max_altitude_m", "Max altitude", "m"),
    ("max_speed_mps", "Max speed", "m/s"),
    ("max_load_factor_g", "Max load factor", "g"),
    ("min_target_distance_m", "Minimum target distance", "m"),
    ("event_count", "Event count", ""),
)

_FINAL_HIGHLIGHTS = (
    ("time_s", "Final time", "s"),
    ("altitude_m", "Final altitude", "m"),
    ("speed_mps", "Final speed", "m/s"),
    ("mass_kg", "Final mass", "kg"),
    ("target_distance_m", "Final target distance", "m"),
)

_TELEMETRY_HIGHLIGHT_CHANNELS = (
    ("history", "altitude_m", "Altitude", "m"),
    ("history", "altitude_agl_m", "Altitude AGL", "m"),
    ("history", "speed_mps", "Speed", "m/s"),
    ("history", "mach", "Mach", ""),
    ("history", "qbar_pa", "Dynamic pressure", "Pa"),
    ("history", "load_factor_g", "Load factor", "g"),
    ("history", "target_range_m", "Target range", "m"),
    ("history", "closing_speed_mps", "Closing speed", "m/s"),
    ("history", "interceptor_range_m", "Interceptor range", "m"),
    ("history", "interceptor_closing_speed_mps", "Interceptor closing speed", "m/s"),
    ("history", "thrust_n", "Thrust", "N"),
    ("history", "mass_kg", "Mass", "kg"),
    ("controls", "throttle", "Throttle", ""),
    ("controls", "elevator_deg", "Elevator", "deg"),
    ("controls", "aileron_deg", "Aileron", "deg"),
    ("controls", "rudder_deg", "Rudder", "deg"),
    ("sensors", "gps_valid", "GPS valid", ""),
    ("sensors", "pitot_airspeed_mps", "Pitot airspeed", "m/s"),
    ("sensors", "baro_alt_m", "Barometer altitude", "m"),
    ("sensors", "radar_agl_m", "Radar altitude AGL", "m"),
)

_PRIORITY_ARTIFACTS = (
    "report.html",
    "engagement_report.html",
    "sensor_report/sensor_report.html",
    "history.csv",
    "truth.csv",
    "controls.csv",
    "sensors.csv",
    "targets.csv",
    "interceptors.csv",
    "summary.json",
    "manifest.json",
    "events.json",
    "scenario_resolved.json",
    "engagement_report.json",
    "sensor_report/sensor_metrics.json",
    "sensor_report/sensor_metrics.csv",
)


def assemble_report_studio_packet(
    run_dir: str | Path,
    *,
    sections: list[str] | tuple[str, ...] | None = None,
    artifact_base_url: str | None = None,
    max_events: int = 60,
    max_artifacts: int = 120,
) -> dict[str, Any]:
    """Assemble a dependency-free mission packet from an existing run directory."""

    run = Path(run_dir)
    if not run.exists():
        raise FileNotFoundError(f"run directory not found: {run}")
    if not run.is_dir():
        raise NotADirectoryError(f"run path is not a directory: {run}")

    selected_sections = _normalize_sections(sections)
    summary = _read_json_object(run / "summary.json")
    events = _read_json_list(run / "events.json")
    packet: dict[str, Any] = {
        "schema": REPORT_STUDIO_SCHEMA,
        "packet_id": run.name,
        "run_dir": str(run),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selected_sections": selected_sections,
        "source_files": _source_files(run),
    }

    if "summary" in selected_sections:
        packet["summary"] = _summary_section(summary)
    if "events" in selected_sections:
        packet["events_timeline"] = _events_timeline(events, max_events=max_events)
    if "alarms" in selected_sections:
        packet["alarm_summaries"] = _alarm_section(run)
    if "telemetry" in selected_sections:
        packet["telemetry_highlights"] = _telemetry_section(run)
    if "engagement" in selected_sections:
        packet["engagement_metrics"] = _engagement_metrics(run, summary, events)
    if "artifacts" in selected_sections:
        packet["artifacts"] = _artifact_refs(run, artifact_base_url=artifact_base_url, max_artifacts=max_artifacts)

    return packet


def assemble_mission_packet(run_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Compatibility alias for callers that name the packet by its mission role."""

    return assemble_report_studio_packet(run_dir, **kwargs)


def _normalize_sections(sections: list[str] | tuple[str, ...] | None) -> list[str]:
    requested = list(sections or DEFAULT_PACKET_SECTIONS)
    invalid = [section for section in requested if section not in DEFAULT_PACKET_SECTIONS]
    if invalid:
        raise ValueError(f"unknown report studio section(s): {', '.join(invalid)}")
    normalized: list[str] = []
    for section in requested:
        if section not in normalized:
            normalized.append(section)
    return normalized


def _source_files(run: Path) -> dict[str, str | None]:
    return {
        "summary": _rel_if_exists(run, run / "summary.json"),
        "events": _rel_if_exists(run, run / "events.json"),
        "manifest": _rel_if_exists(run, run / "manifest.json"),
        "history": _rel_if_exists(run, run / "history.csv"),
        "truth": _rel_if_exists(run, run / "truth.csv"),
        "controls": _rel_if_exists(run, run / "controls.csv"),
        "sensors": _rel_if_exists(run, run / "sensors.csv"),
        "targets": _rel_if_exists(run, run / "targets.csv"),
        "interceptors": _rel_if_exists(run, run / "interceptors.csv"),
    }


def _summary_section(summary: dict[str, Any]) -> dict[str, Any]:
    highlights = [
        _metric_item(key=key, label=label, value=summary.get(key), unit=unit, source="summary.json")
        for key, label, unit in _SUMMARY_HIGHLIGHTS
        if key in summary
    ]
    final = summary.get("final")
    if isinstance(final, dict):
        highlights.extend(
            _metric_item(key=f"final.{key}", label=label, value=final.get(key), unit=unit, source="summary.json")
            for key, label, unit in _FINAL_HIGHLIGHTS
            if key in final
        )
    return {
        "available": bool(summary),
        "source": "summary.json" if summary else None,
        "data": summary,
        "highlights": highlights,
    }


def _events_timeline(events: list[dict[str, Any]], *, max_events: int) -> dict[str, Any]:
    sorted_events = sorted(enumerate(events), key=lambda item: (_event_sort_time(item[1]), item[0]))
    items = [_event_item(index, event) for index, event in sorted_events[: max(0, max_events)]]
    return {
        "available": bool(events),
        "source": "events.json" if events else None,
        "count": len(events),
        "truncated": len(events) > len(items),
        "items": items,
    }


def _event_item(index: int, event: dict[str, Any]) -> dict[str, Any]:
    core_keys = {"time_s", "type", "description", "severity", "message"}
    event_type = str(event.get("type", "event"))
    description = str(event.get("description") or event.get("message") or event_type.replace("_", " "))
    time_s = _number(event.get("time_s"))
    severity = event.get("severity")
    details = {key: value for key, value in event.items() if key not in core_keys}
    return {
        "index": index,
        "time_s": time_s,
        "type": event_type,
        "description": description,
        "severity": str(severity) if severity is not None else None,
        "details": details,
    }


def _alarm_section(run: Path) -> dict[str, Any]:
    try:
        alarms = evaluate_run_alarms(run)
    except Exception:
        alarms = []
    counts = {severity: 0 for severity in ("critical", "warning", "caution", "info")}
    for alarm in alarms:
        severity = str(alarm.get("severity", "info"))
        counts[severity] = counts.get(severity, 0) + 1
    return {
        "available": bool(alarms),
        "source": "derived:evaluate_run_alarms",
        "count": len(alarms),
        "active_count": sum(1 for alarm in alarms if bool(alarm.get("active"))),
        "counts_by_severity": counts,
        "items": [_alarm_item(alarm) for alarm in alarms],
    }


def _alarm_item(alarm: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "name",
        "severity",
        "source",
        "subsystem",
        "message",
        "channel",
        "threshold",
        "rule",
        "first_triggered_time_s",
        "last_triggered_time_s",
        "cleared_time_s",
        "active",
        "occurrence_count",
        "sample_count",
    )
    return {key: alarm.get(key) for key in keys if key in alarm}


def _telemetry_section(run: Path) -> dict[str, Any]:
    datasets = {
        "history": _read_csv_rows(run / "history.csv"),
        "truth": _read_csv_rows(run / "truth.csv"),
        "controls": _read_csv_rows(run / "controls.csv"),
        "sensors": _read_csv_rows(run / "sensors.csv"),
    }
    items: list[dict[str, Any]] = []
    for source, channel, label, unit in _TELEMETRY_HIGHLIGHT_CHANNELS:
        item = _channel_highlight(datasets.get(source, []), source=source, channel=channel, label=label, unit=unit)
        if item is not None:
            items.append(item)
    sources = [
        {"source": source, "path": f"{source}.csv", "sample_count": len(rows)}
        for source, rows in datasets.items()
        if rows
    ]
    return {
        "available": bool(items),
        "sources": sources,
        "items": items,
    }


def _channel_highlight(
    rows: list[dict[str, Any]],
    *,
    source: str,
    channel: str,
    label: str,
    unit: str,
) -> dict[str, Any] | None:
    samples: list[tuple[float | None, float]] = []
    for row in rows:
        value = _number(row.get(channel))
        if value is None:
            continue
        samples.append((_number(row.get("time_s")), value))
    if not samples:
        return None
    min_sample = min(samples, key=lambda item: item[1])
    max_sample = max(samples, key=lambda item: item[1])
    final_sample = samples[-1]
    return {
        "id": f"{source}.{channel}",
        "source": source,
        "channel": channel,
        "label": label,
        "unit": unit,
        "sample_count": len(samples),
        "min": _sample_value(min_sample),
        "max": _sample_value(max_sample),
        "final": _sample_value(final_sample),
    }


def _engagement_metrics(run: Path, summary: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    history = _read_csv_rows(run / "history.csv")
    targets = _read_csv_rows(run / "targets.csv")
    interceptors = _read_csv_rows(run / "interceptors.csv")
    target_ids = sorted({str(row.get("target_id")) for row in targets if row.get("target_id") not in (None, "")})
    interceptor_ids = sorted(
        {str(row.get("interceptor_id")) for row in interceptors if row.get("interceptor_id") not in (None, "")}
    )
    metrics = {
        "available": bool(history or targets or interceptors or summary),
        "target_count": len(target_ids),
        "target_ids": target_ids,
        "interceptor_count": len(interceptor_ids),
        "interceptor_ids": interceptor_ids,
        "min_target_distance_m": _metric_value(
            _first_number(_number(summary.get("min_target_distance_m")), _nested_number(summary, "final", "target_distance_m")),
            "summary",
        ),
        "min_target_range_m": _series_min_metric(history, "target_range_m"),
        "min_interceptor_range_m": _series_min_metric(history, "interceptor_range_m"),
        "first_interceptor_fuze_time_s": _first_flag_time(history, "interceptor_fuzed"),
        "closest_approach_event": _closest_approach_event(events),
    }
    metrics["available"] = any(
        value
        for key, value in metrics.items()
        if key not in {"available", "target_count", "interceptor_count"}
    ) or bool(metrics["target_count"] or metrics["interceptor_count"])
    return metrics


def _artifact_refs(run: Path, *, artifact_base_url: str | None, max_artifacts: int) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for relative in _PRIORITY_ARTIFACTS:
        path = run / relative
        if path.exists() and path.is_file():
            candidates.append(path)
    plots_dir = run / "plots"
    if plots_dir.exists():
        candidates.extend(sorted(path for path in plots_dir.glob("*.svg") if path.is_file())[:80])
    sensor_plots_dir = run / "sensor_report" / "plots"
    if sensor_plots_dir.exists():
        candidates.extend(sorted(path for path in sensor_plots_dir.glob("*.svg") if path.is_file())[:40])
    for path in sorted(run.rglob("*")):
        if len(candidates) >= max_artifacts:
            break
        if not path.is_file() or path in candidates:
            continue
        if path.suffix.lower() in {".html", ".svg", ".csv", ".json"}:
            candidates.append(path)

    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in candidates:
        if len(refs) >= max_artifacts:
            break
        rel = path.relative_to(run).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        refs.append(
            {
                "name": path.name,
                "kind": _artifact_kind(path),
                "path": rel,
                "url": _artifact_url(rel, artifact_base_url),
                "size_bytes": path.stat().st_size,
            }
        )
    return refs


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "report"
    if suffix == ".svg":
        return "plot"
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    return "file"


def _artifact_url(relative_path: str, artifact_base_url: str | None) -> str | None:
    if not artifact_base_url:
        return None
    return f"{artifact_base_url.rstrip('/')}/{quote(relative_path)}"


def _read_json_object(path: Path) -> dict[str, Any]:
    data = _read_json(path)
    return data if isinstance(data, dict) else {}


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return read_csv(path)
    except (OSError, ValueError):
        return []


def _rel_if_exists(base: Path, path: Path) -> str | None:
    if not path.exists():
        return None
    return path.relative_to(base).as_posix()


def _metric_item(*, key: str, label: str, value: Any, unit: str, source: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "source": source,
    }


def _metric_value(value: float | None, source: str) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"value": value, "source": source}


def _series_min_metric(rows: list[dict[str, Any]], channel: str) -> dict[str, Any] | None:
    samples: list[tuple[float | None, float]] = []
    for row in rows:
        value = _number(row.get(channel))
        if value is not None:
            samples.append((_number(row.get("time_s")), value))
    if not samples:
        return None
    sample = min(samples, key=lambda item: item[1])
    return {"value": sample[1], "time_s": sample[0], "source": f"history.{channel}"}


def _first_flag_time(rows: list[dict[str, Any]], channel: str) -> float | None:
    for row in rows:
        value = _number(row.get(channel))
        if value is not None and value > 0.5:
            return _number(row.get("time_s"))
    return None


def _closest_approach_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in sorted(events, key=_event_sort_time):
        if str(event.get("type", "")) == "closest_approach":
            return _event_item(0, event)
    return None


def _event_sort_time(event: dict[str, Any]) -> float:
    time_s = _number(event.get("time_s"))
    return time_s if time_s is not None else math.inf


def _sample_value(sample: tuple[float | None, float]) -> dict[str, float | None]:
    time_s, value = sample
    return {"time_s": time_s, "value": value}


def _first_number(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _nested_number(data: dict[str, Any], key: str, nested_key: str) -> float | None:
    nested = data.get(key)
    if not isinstance(nested, dict):
        return None
    return _number(nested.get(nested_key))


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        number = 1.0 if value else 0.0
    elif isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


__all__ = [
    "DEFAULT_PACKET_SECTIONS",
    "REPORT_STUDIO_SCHEMA",
    "assemble_mission_packet",
    "assemble_report_studio_packet",
]
