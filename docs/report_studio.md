# Report Studio

Report Studio is a dependency-free packet layer for mission review. It assembles existing run artifacts into a structured object that a UI, CLI command, or later HTML/Markdown exporter can consume without adding PDF tooling.

## Backend Packet

Use `assemble_report_studio_packet(run_dir)` from `aerosim6dof.reports.studio`.

```python
from aerosim6dof.reports.studio import assemble_report_studio_packet

packet = assemble_report_studio_packet(
    "outputs/nominal_expanded",
    artifact_base_url="/api/artifacts/nominal_expanded",
)
```

The packet schema is `aerosim6dof.report_studio.packet.v1` and contains:

- `summary`: raw `summary.json` plus mission/final-state highlight metrics.
- `events_timeline`: sorted normalized events from `events.json`.
- `alarm_summaries`: derived alarm payloads from `evaluate_run_alarms` when source data is present.
- `telemetry_highlights`: min, max, and final samples for selected history/control/sensor channels.
- `engagement_metrics`: target/interceptor IDs, best range metrics, fuze timing, and closest-approach event data when available.
- `artifacts`: refs for HTML, SVG, CSV, and JSON artifacts inside the run directory.

Selected sections can be limited:

```python
packet = assemble_report_studio_packet(
    "outputs/nominal_expanded",
    sections=("summary", "events", "artifacts"),
)
```

Unknown sections are rejected. PDF is intentionally not a supported section or export format.

## Frontend Contract

`web/src/reportStudio.ts` defines the TypeScript packet shape and helper functions:

- `describeReportStudioSections(packet, sections)` returns section availability, item counts, labels, and summaries.
- `buildReportStudioExportRequest(...)` creates a stable request payload shape for future API wiring.
- `buildReportStudioExportPayload(packet, request)` extracts selected sections for JSON, Markdown, or HTML export flows.

`web/src/components/ReportStudio.tsx` is a standalone component. It accepts a packet and optional controlled section/format state, renders section toggles, previews selected sections, and emits the export request/payload through `onExportRequest`.

The current foundation does not edit Workbench or API routing. A future integration can mount the component wherever run detail state is already available and add an endpoint that calls the backend helper.

## Integration Notes

- The backend helper is read-only and does not write into the run directory.
- Artifact refs are relative by default. Pass `artifact_base_url` to populate browser-ready URLs.
- Alarm and engagement sections remain present but empty when their source files are missing.
- Export formats are `json`, `markdown`, and `html`; PDF remains out of scope.
