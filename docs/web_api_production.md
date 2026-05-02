# Web API Production Contract

These routes are the production-facing contract covered by
`tests/test_web_api_production.py`. Tests use `FastAPI` `TestClient`,
temporary output roots, and `AEROSIM_STORAGE_DIR` so they do not depend on or
mutate checked-in generated outputs.

## Jobs

```text
POST /api/jobs/{job_id}/cancel
```

Expected behavior:

- `200` for an existing queued/running job.
- Returns `{ "cancel": ..., "job": ... }`. The nested `cancel` object is the
  progress cancellation-registry payload: `job_id`, `requested`,
  `requested_at`, `reason`, `requested_by`, and `message`.
- The job progress endpoint remains readable after cancellation is requested.
- `404` for a missing job and no cancellation state is created for that id.

## Navigation Telemetry

```text
GET /api/runs/{run_id}/navigation?stride=2
```

Expected behavior:

- Uses the existing run-id rules from `/api/runs/{run_id}`.
- Returns the JSON-safe payload produced by
  `load_navigation_telemetry_from_run(run_dir, stride=stride)`, plus `run_id`
  and channel `metadata`.
- Response shape is `{ "run_id": "...", "rows": [...], "channels": [...],
  "summary": {...}, "metadata": {...} }`.
- Missing runs return `404`.

## Storage Layouts

```text
GET    /api/storage/layouts
POST   /api/storage/layouts/{layout_id}
GET    /api/storage/layouts/{layout_id}
DELETE /api/storage/layouts/{layout_id}
```

Expected behavior:

- Routes use `AEROSIM_STORAGE_DIR` through the file-backed storage helpers.
- Save returns the stamped layout record with `id`, `created_at`, and
  `updated_at`.
- List returns newest-first layout records.
- Get returns `404` when the layout id is absent.
- Delete returns `{ "deleted": true, "id": "<layout_id>" }`.
- Unsafe ids must not write outside the configured storage root.

## Validation Advisories

```text
POST /api/validate
```

Expected behavior:

- The existing validation response keeps `advisories`.
- It also includes `advisory_summary` from
  `summarize_scenario_advisories(advisories)`.
- The summary is returned even when hard `Scenario` validation fails, so the UI
  can explain likely fixes without depending on a successful scenario build.

## Report Studio

```text
GET /api/runs/{run_id}/report-studio?sections=summary,artifacts
```

Expected behavior:

- Returns the read-only packet from `assemble_report_studio_packet`.
- `selected_sections` reflects the requested section order.
- Artifact URLs are rooted at `/api/artifacts/{run_id}`.
- Missing runs return `404`.
- Unknown sections return `400`.

## Examples Gallery

```text
GET /api/examples-gallery
```

Expected behavior:

- Returns cards from the configured examples root.
- Broken scenario JSON is represented as a safe card rather than crashing the
  endpoint.
- A missing examples root returns an empty list.
