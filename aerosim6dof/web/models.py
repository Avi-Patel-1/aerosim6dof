"""FastAPI response models for the browser dashboard."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtifactRef(BaseModel):
    name: str
    kind: str
    path: str
    url: str
    size_bytes: int = 0


class ScenarioSummary(BaseModel):
    id: str
    name: str
    path: str
    duration_s: float
    dt_s: float
    integrator: str
    vehicle_config: str | None = None
    environment_config: str | None = None
    guidance_mode: str | None = None


class ScenarioDetail(ScenarioSummary):
    raw: dict[str, Any] = Field(default_factory=dict)
    resolved: dict[str, Any] = Field(default_factory=dict)


class ScenarioDraftRequest(BaseModel):
    scenario: dict[str, Any]
    name: str | None = Field(default=None, max_length=80)


class ScenarioDraft(BaseModel):
    id: str
    name: str
    path: str
    valid: bool
    errors: list[str] = Field(default_factory=list)
    scenario: dict[str, Any] = Field(default_factory=dict)


class ConfigSummary(BaseModel):
    id: str
    name: str
    path: str


class RunRequest(BaseModel):
    scenario_id: str
    run_name: str | None = Field(default=None, max_length=80)


class ValidateRequest(BaseModel):
    scenario_id: str | None = None
    scenario: dict[str, Any] | None = None


class ActionRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    action: str
    status: Literal["completed", "failed"] = "completed"
    message: str = ""
    output_id: str | None = None
    output_dir: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)


class RunStatus(BaseModel):
    run_id: str
    status: Literal["completed", "failed", "running"]
    message: str = ""


class JobEvent(BaseModel):
    time_utc: str
    status: str
    message: str
    progress: float = 0.0


class JobSummary(BaseModel):
    id: str
    action: str
    status: Literal["queued", "running", "completed", "failed"]
    message: str = ""
    progress: float = 0.0
    created_at_utc: str
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    events: list[JobEvent] = Field(default_factory=list)
    result: ActionResult | None = None


class RunSummary(BaseModel):
    id: str
    scenario: str
    status: Literal["completed", "failed", "unknown"] = "completed"
    run_dir: str
    created_at_utc: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)


class TelemetryRange(BaseModel):
    min: float | None = None
    max: float | None = None
    label: str = ""


class TelemetryChannelMetadata(BaseModel):
    key: str
    display_name: str
    unit: str = ""
    description: str = ""
    group: str = "Unknown"
    source: Literal["history", "truth", "controls", "sensors", "derived"] = "history"
    role: Literal["truth", "sensor", "command", "actuator_state", "environment", "aero", "gnc", "propulsion", "derived"] = "truth"
    valid_range: TelemetryRange | None = None
    caution_range: TelemetryRange | None = None
    warning_range: TelemetryRange | None = None
    fatal_range: TelemetryRange | None = None
    sample_rate_hz: float | None = None
    derived: bool = False


class TelemetrySeries(BaseModel):
    run_id: str
    stride: int
    sample_count: int
    channels: dict[str, list[str]]
    history: list[dict[str, Any]] = Field(default_factory=list)
    truth: list[dict[str, Any]] = Field(default_factory=list)
    controls: list[dict[str, Any]] = Field(default_factory=list)
    sensors: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, TelemetryChannelMetadata] = Field(default_factory=dict)
