# Browser Simulator GUI

The browser GUI is an optional layer around the existing Python simulator. It keeps the CLI and NumPy-only core intact while exposing scenarios, runs, telemetry, reports, and artifacts through a local FastAPI service.

## Install

```bash
python3 -m pip install -e ".[web]"
cd web
npm install
```

## Run

Start the API:

```bash
aerosim6dof-web --host 127.0.0.1 --port 8000
```

Start the browser UI:

```bash
cd web
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. If that port is already in use, pass a different
port to Vite and open the printed URL.

For a local demo loop, the helper script starts both services and installs web
dependencies if needed:

```bash
scripts/run_web_demo.sh
```

Override ports without editing files:

```bash
API_PORT=8010 WEB_PORT=5180 scripts/run_web_demo.sh
```

## Browser Experience

- The first screen is a minimal black/white ASCII entry surface.
- The workbench is tabbed: replay, launch, campaigns, engineering, models,
  editor, and reports.
- Replay mode includes environment presets, camera modes, playback speed,
  telemetry charts, events, run metrics, trail/body-axis toggles, and artifact
  links. The scene can also render a wind-vector overlay from the recorded
  `wind_*_mps` telemetry channels.
- Telemetry charts support selectable channels for flight, controls, and sensor
  datasets so report inspection is not limited to the default plotted metrics.
- The editor tab loads example scenarios, supports guided field edits plus raw
  JSON, validates guarded edits, writes drafts under
  `outputs/web_runs/scenario_drafts/`, and can run drafts without modifying
  checked-in examples.
- Long-running browser actions use the job API so the interface can show
  queued/running/completed status, progress, and recent job events while the
  simulator executes. The browser consumes server-sent events when available and
  falls back to polling.

## API Surface

- `GET /api/scenarios`
- `GET /api/scenarios/{id}`
- `POST /api/scenario-drafts`
- `GET /api/vehicles`
- `GET /api/environments`
- `GET /api/capabilities`
- `POST /api/validate`
- `POST /api/runs`
- `POST /api/actions/{action}`
- `POST /api/jobs/{action}`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `GET /api/jobs/{id}/events`
- `GET /api/runs`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/telemetry?stride=N`
- `GET /api/artifacts/{id}/{path}`

Browser-created runs are written to `outputs/web_runs/`, which is ignored by git so packaged examples and checked-in reference outputs remain stable.
