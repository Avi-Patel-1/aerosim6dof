"""Reusable progress primitives for browser job integrations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping


TERMINAL_PHASES = frozenset({"completed", "failed", "cancelled"})
_PHASE_ALIASES = {
    "active": "running",
    "canceled": "cancelled",
    "canceling": "cancelling",
    "done": "completed",
    "error": "failed",
    "errored": "failed",
    "executing": "running",
    "finished": "completed",
    "in_progress": "running",
    "pending": "queued",
    "started": "running",
    "success": "completed",
    "succeeded": "completed",
}
_JSON_TYPES = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class ProgressEvent:
    job_id: str
    action: str
    phase: str
    percent: float
    message: str
    run_id: str | None = None
    artifact: Any | None = None
    cancellable: bool = False
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = utc_now()
        phase = normalize_phase(self.phase)
        object.__setattr__(self, "job_id", str(self.job_id or ""))
        object.__setattr__(self, "action", str(self.action or ""))
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "percent", normalize_percent(self.percent, phase=phase))
        object.__setattr__(self, "message", str(self.message or ""))
        object.__setattr__(self, "run_id", str(self.run_id) if self.run_id is not None else None)
        object.__setattr__(self, "artifact", json_safe(self.artifact))
        object.__setattr__(self, "cancellable", bool(self.cancellable and not is_terminal_phase(phase)))
        object.__setattr__(self, "created_at", normalize_timestamp(self.created_at) or now)
        object.__setattr__(self, "updated_at", normalize_timestamp(self.updated_at) or normalize_timestamp(self.created_at) or now)

    def to_dict(self) -> dict[str, Any]:
        return json_safe(asdict(self))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        text = value.strip()
        return text
    return ""


def normalize_phase(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "", text)
    return _PHASE_ALIASES.get(text, text or "queued")


def normalize_percent(value: Any, *, phase: Any | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if not math.isfinite(number):
        number = 0.0
    if 0.0 <= number <= 1.0:
        number *= 100.0
    number = max(0.0, min(100.0, number))
    if phase is not None and normalize_phase(phase) == "completed":
        return 100.0
    return round(number, 3)


def is_terminal_phase(value: Any) -> bool:
    return normalize_phase(value) in TERMINAL_PHASES


def make_progress_event(
    job_id: str,
    action: str,
    phase: str = "queued",
    percent: Any = 0.0,
    message: str = "",
    *,
    run_id: str | None = None,
    artifact: Any | None = None,
    cancellable: bool | None = None,
    created_at: Any | None = None,
    updated_at: Any | None = None,
) -> ProgressEvent:
    normalized_phase = normalize_phase(phase)
    return ProgressEvent(
        job_id=job_id,
        action=action,
        phase=normalized_phase,
        percent=normalize_percent(percent, phase=normalized_phase),
        message=message,
        run_id=run_id,
        artifact=artifact,
        cancellable=(not is_terminal_phase(normalized_phase)) if cancellable is None else bool(cancellable),
        created_at=normalize_timestamp(created_at) or utc_now(),
        updated_at=normalize_timestamp(updated_at) or normalize_timestamp(created_at) or utc_now(),
    )


def merge_progress_event(
    current: ProgressEvent | Mapping[str, Any] | None,
    update: ProgressEvent | Mapping[str, Any],
    *,
    updated_at: Any | None = None,
) -> ProgressEvent:
    current_data = _event_data(current)
    update_data = _event_data(update)
    merged = {**current_data, **{key: value for key, value in update_data.items() if value is not None}}
    created_at = current_data.get("created_at") or update_data.get("created_at") or utc_now()
    phase = normalize_phase(merged.get("phase"))
    return ProgressEvent(
        job_id=str(merged.get("job_id") or ""),
        action=str(merged.get("action") or ""),
        phase=phase,
        percent=normalize_percent(merged.get("percent", 0.0), phase=phase),
        message=str(merged.get("message") or ""),
        run_id=merged.get("run_id"),
        artifact=merged.get("artifact"),
        cancellable=bool(merged.get("cancellable", not is_terminal_phase(phase))),
        created_at=created_at,
        updated_at=normalize_timestamp(updated_at) or update_data.get("updated_at") or utc_now(),
    )


def progress_from_job_summary(job: Mapping[str, Any]) -> ProgressEvent:
    events = job.get("events")
    last_event = events[-1] if isinstance(events, list) and events and isinstance(events[-1], Mapping) else {}
    result = job.get("result") if isinstance(job.get("result"), Mapping) else {}
    artifacts = result.get("artifacts") if isinstance(result, Mapping) else None
    artifact = artifacts[0] if isinstance(artifacts, list) and artifacts else None
    return make_progress_event(
        str(job.get("id") or job.get("job_id") or ""),
        str(job.get("action") or ""),
        normalize_phase(job.get("status") or job.get("phase")),
        job.get("progress", job.get("percent", 0.0)),
        str(job.get("message") or last_event.get("message") or ""),
        run_id=result.get("output_id") if isinstance(result, Mapping) else None,
        artifact=artifact,
        cancellable=not is_terminal_phase(job.get("status") or job.get("phase")),
        created_at=job.get("created_at") or job.get("created_at_utc"),
        updated_at=job.get("finished_at_utc") or last_event.get("time_utc") or job.get("started_at_utc") or job.get("created_at_utc"),
    )


def cancel_descriptor(event: ProgressEvent | Mapping[str, Any]) -> dict[str, Any]:
    data = _event_data(event)
    phase = normalize_phase(data.get("phase"))
    job_id = str(data.get("job_id") or "")
    return {
        "job_id": job_id,
        "method": "POST",
        "path": f"/api/jobs/{job_id}/cancel",
        "enabled": bool(job_id and not is_terminal_phase(phase) and data.get("cancellable", True)),
        "phase": phase,
    }


def retry_descriptor(event: ProgressEvent | Mapping[str, Any]) -> dict[str, Any]:
    data = _event_data(event)
    action = str(data.get("action") or "")
    phase = normalize_phase(data.get("phase"))
    return {
        "job_id": str(data.get("job_id") or ""),
        "action": action,
        "method": "POST",
        "path": f"/api/jobs/{action}" if action else "",
        "enabled": bool(action and phase in {"failed", "cancelled"}),
        "phase": phase,
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, _JSON_TYPES):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, datetime):
        return normalize_timestamp(value)
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return str(value)


def _event_data(event: ProgressEvent | Mapping[str, Any] | None) -> dict[str, Any]:
    if event is None:
        return {}
    if isinstance(event, ProgressEvent):
        return event.to_dict()
    if isinstance(event, Mapping):
        aliases = {"id": "job_id", "status": "phase", "progress": "percent", "created_at_utc": "created_at"}
        valid = {field.name for field in fields(ProgressEvent)}
        data: dict[str, Any] = {}
        for key, value in event.items():
            mapped = aliases.get(str(key), str(key))
            if mapped in valid:
                data[mapped] = value
        return data
    return {}
