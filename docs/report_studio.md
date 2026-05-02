# Report Studio

Report Studio is a dependency-free packet layer for mission review. It assembles existing run artifacts into a structured mission packet that a UI, CLI command, or later HTML/Markdown exporter can consume without adding PDF tooling.

## Backend Packet

Use `assemble_report_studio_packet(run_dir)` from `aerosim6dof.reports.studio` when callers need an in-memory packet only.

```python
from aerosim6dof.reports.studio import assemble_report_studio_packet

packet = assemble_report_studio_packet(
    "outputs/nominal_expanded",
    artifact_base_url="/api/artifacts/nominal_expanded",
    telemetry_channels=("history.altitude_m", "history.speed_mps", "controls.throttle"),
)
```

The packet schema is `aerosim6dof.report_studio.packet.v1` and contains:

- `summary`: raw `summary.json`, a compact scenario summary from `scenario_resolved.json`/`manifest.json`, and mission/final-state highlight metrics.
- `events_timeline`: sorted normalized events from `events.json`.
- `alarm_summaries`: derived alarm payloads from `evaluate_run_alarms` when source data is present.
- `telemetry_highlights`: available telemetry channels, selected channel IDs, and min/max/final samples for selected history/truth/control/sensor channels.
- `engagement_metrics`: existing `engagement_report.json` metrics when available, plus derived target/interceptor IDs, best range metrics, fuze timing, and closest-approach event data.
- `artifacts`: refs for HTML, SVG, CSV, and JSON artifacts inside the run directory.

Selected sections can be limited:

```python
packet = assemble_report_studio_packet(
    "outputs/nominal_expanded",
    sections=("summary", "events", "artifacts"),
)
```

Unknown sections are rejected. PDF is intentionally not a supported section or export format.

To persist a packet, call `write_report_studio_packet(run_dir)`. It writes `reports/report_studio/mission_packet.json` under the run directory by default:

```python
from aerosim6dof.reports.studio import write_report_studio_packet

packet = write_report_studio_packet(
    "outputs/nominal_expanded",
    sections=("summary", "events", "telemetry", "artifacts"),
)
```

The write helper resolves the output path before writing. A custom `report_dir` must stay under the run directory unless the caller also provides an explicit `allowed_root`.

## Frontend Contract

`web/src/reportStudio.ts` defines the TypeScript packet shape and helper functions:

- `describeReportStudioSections(packet, sections)` returns section availability, item counts, labels, and summaries.
- `availableReportStudioTelemetryChannels(packet)` returns channel references suitable for a picker.
- `normalizeReportStudioTelemetryChannels(channels, packet)` path-safely normalizes selected telemetry channel IDs.
- `buildReportStudioReportSummary(packet, sections, channels)` returns title, readiness, section count, artifact count, event count, alarm count, and selected channel count.
- `buildReportStudioExportRequest(...)` creates a stable request payload shape for future API wiring.
- `buildReportStudioExportPayload(packet, request)` extracts selected sections and filters telemetry highlights to the selected channels for JSON, Markdown, or HTML export flows.

`web/src/components/ReportStudio.tsx` is a standalone component. It accepts a packet and optional controlled section, telemetry-channel, and format state. It renders the report summary, section toggles, channel toggles, selected-section preview, and ready payload. Parent/API wiring can use `onSelectionChange`, `onTelemetryChannelsChange`, `onPayloadReady`, and `onExportRequest`.

The current foundation does not edit Workbench or API routing. A future integration can mount the component wherever run detail state is already available and add an endpoint that calls the backend helper.

## Integration Notes

- `assemble_report_studio_packet` is read-only and does not write into the run directory.
- `write_report_studio_packet` only writes the packet JSON under an allowed report directory.
- Artifact refs are relative by default. Pass `artifact_base_url` to populate browser-ready URLs.
- Alarm and engagement sections remain present but empty when their source files are missing.
- Export formats are `json`, `markdown`, and `html`; PDF remains out of scope.
