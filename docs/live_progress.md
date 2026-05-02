# Live Run Progress Foundation

This module adds reusable progress primitives for the existing FastAPI job flow. It does not add a new server or replace the current routes.

## Backend Primitives

Use `aerosim6dof.web.progress.ProgressEvent` for normalized progress snapshots:

- `job_id`
- `action`
- `phase`
- `percent`
- `message`
- `run_id`
- `artifact`
- `cancellable`
- `created_at`
- `updated_at`

The helpers are defensive and return JSON-serializable data:

- `normalize_phase(value)`: normalizes aliases such as `in progress`, `done`, `success`, and `canceled`.
- `normalize_percent(value, phase=...)`: accepts existing 0.0-1.0 job progress values or 0-100 percentages and clamps invalid values.
- `merge_progress_event(current, update)`: applies partial lifecycle updates while preserving `created_at`.
- `is_terminal_phase(value)`: treats `completed`, `failed`, and `cancelled` as terminal.
- `cancel_descriptor(event)` and `retry_descriptor(event)`: create route descriptors for parent integration.
- `progress_from_job_summary(job)`: adapts the current `JobSummary` dictionary into a `ProgressEvent`.
- `JobCancellationRegistry`: thread-safe in-memory cancellation state for background jobs.
- `request_cancel(job_id, ...)`, `clear_cancel(job_id)`, `is_cancel_requested(job_id)`, and `cancellation_payload(job_id)`: module-level helpers backed by the default registry for `web/api.py` wiring.

The registry stores request state only; it does not terminate a thread by itself. The job runner should poll `is_cancel_requested(job_id)` between long-running work units, emit a `cancelled` progress event when it exits early, and call `clear_cancel(job_id)` during cleanup.

Example backend flow:

```py
from aerosim6dof.web.progress import clear_cancel, is_cancel_requested, request_cancel

def cancel_job(job_id: str) -> dict:
    return request_cancel(job_id, reason="operator").to_dict()

def run_job(job_id: str) -> None:
    try:
        for step in steps:
            if is_cancel_requested(job_id):
                emit_progress(job_id, phase="cancelled", message="Cancelled by operator")
                return
            run_step(step)
    finally:
        clear_cancel(job_id)
```

## Existing SSE Integration

The current API already exposes server-sent events at:

```text
GET /api/jobs/{job_id}/events
```

That endpoint streams full job snapshots as `data: {...}` messages. Parent integration can keep the existing route unchanged and adapt each streamed `JobSummary` with `progress_from_job_summary(...)` on the backend or `parseLiveProgressPayload(...)` in the browser.

Example browser flow:

```ts
import { jobEventsUrl } from "./api";
import { updateLiveProgressMap, type LiveProgressMap } from "./liveProgress";

let progress: LiveProgressMap = {};
const source = new EventSource(jobEventsUrl(jobId));
source.onmessage = (event) => {
  progress = updateLiveProgressMap(progress, event.data);
};
```

## Frontend Primitives

`web/src/liveProgress.ts` provides stable state helpers:

- `parseLiveProgressPayload(data)`: parses either the current SSE `JobSummary` payload or a future `ProgressEvent` payload.
- `updateLiveProgressMap(map, data)`: merges streamed updates by job id.
- `collectLiveProgressStates(jobs, progress)`: combines polled job summaries and streamed progress maps.
- `activeLiveProgressJobs(states)` and `sortLiveProgressJobs(states)`: filter and order job state for UI rendering.
- `canCancel(state)` and `canRetry(state)`: centralize control availability rules.
- `buildCancelRequest(state)` and `buildRetryRequest(state)`: return the request method, route path, enabled state, phase, and JSON body expected by parent wiring.
- `formatElapsedLabel(...)` and `formatLiveProgressLabel(...)`: consistent labels for compact panels.

`LiveProgressPanel` is a reusable React panel that accepts `jobs`, `progress`, `onCancel`, and `onRetry` props. It uses the shared helper rules for button availability and presents the controls with larger icon/text targets so cancel and retry actions remain clear in compact job lists.

## Cancel And Retry

Cancel and retry are descriptors only in this foundation. The helpers currently point at route shapes that parent integration can wire later:

```text
POST /api/jobs/{job_id}/cancel
POST /api/jobs/{action}
```

Until a cancel route exists, callers should pass `onCancel` only when the parent has implemented cancellation semantics for the backing job runner. Retry still depends on the parent preserving enough request context to start a new job for the same action.
