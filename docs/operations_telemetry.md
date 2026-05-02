# Operations Telemetry Console

The operations telemetry page is the dedicated mission-control view for run telemetry. It consumes the existing `TelemetrySeries` payload passed by the workbench and does not require backend or simulation-math changes.

## Channel handling

- Channels are discovered from telemetry metadata first, then from the merged run rows.
- Missing or partial metadata is treated as optional. Labels and units fall back to raw channel keys when display metadata is unavailable.
- Subsystem tabs use metadata group/source/role fields when present, then channel-name heuristics for unannotated runs.
- Current/min/max readouts are numeric where possible and tolerate sparse row sets. If the cursor row is missing a channel value, the panel shows the nearest available sample and keeps min/max based on finite numeric samples only.

## CSV export

The page supports two selected-channel CSV paths:

- `Export selected` downloads the selected chart channels plus `time_s` when available.
- `Copy CSV text` writes the same CSV payload to the clipboard and exposes a read-only text preview for environments where clipboard access is blocked.

CSV output includes `run_id` and `row_index` columns so selected channels can be copied into operations notes without losing sample provenance.

## Saved layouts

Operations layouts are saved through `telemetryOps.ts` helper payloads under the existing local-storage chart-layout key. The payload stores:

- payload kind and version
- active subsystem
- selected chart channels
- pinned channels
- selected detail channel
- current query text
- save timestamp

Older operations layouts with only `kind`, `subsystem`, and `pinned` fields continue to load through the parser.

## Truth / Sensor / Estimate grouping

The comparison panel groups related channels into truth, sensor, and estimate roles when matching channels exist. Metadata role/source fields are preferred, with name-based fallbacks for common flight-test channels such as GPS, IMU, barometer, pitot, radar, estimates, filters, and history state.

This grouping is intentionally opportunistic: missing roles render as disabled "No close match" buttons rather than throwing or hiding the panel.
