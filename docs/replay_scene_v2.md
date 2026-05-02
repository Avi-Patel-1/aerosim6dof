# Replay Scene v2 Overlay Foundation

This document describes the additive overlay helpers owned by Worker 2. The current `ReplayScene` can keep its existing implementation; the v2 utilities expose plain descriptors that the scene integrator can translate into Three.js objects when ready.

## Files

- `web/src/replayVisuals.ts`: render-agnostic telemetry transforms, overlay descriptors, trail color profiles, contact descriptors, range markers, and camera preset metadata.
- `web/src/components/ReplaySceneOverlayLegend.tsx`: optional HUD legend component for the descriptors emitted by `replayVisuals.ts`.

No heavy dependencies are added. The helper module only imports the shared `TelemetryRow` type.

## Coordinate Contract

The helpers preserve the current replay coordinate mapping:

- telemetry `x_m` maps to scene `x`
- telemetry `altitude_m` maps to scene vertical `y`
- telemetry `y_m` maps to scene `-z`
- terrain elevation is scaled with the same scene transform as the vehicle
- default scene ground offset is `DEFAULT_REPLAY_GROUND_Y`

Use `createReplaySceneTransform(rows)` once for a row set, then pass that transform into other helpers if you need stable geometry across frames.

```ts
import {
  buildReplayOverlayState,
  buildReplayTrajectoryVisuals,
  buildReplayVisualFrame,
  buildTrailColorLegendDescriptor,
  createReplaySceneTransform
} from "../replayVisuals";

const transform = createReplaySceneTransform(rows);
const trajectory = buildReplayTrajectoryVisuals(rows, transform);
const trailLegend = buildTrailColorLegendDescriptor(rows, trailColorMode);
const frame = buildReplayVisualFrame(rows, {
  currentIndex,
  trailMode: trailColorMode
});
const overlayState = buildReplayOverlayState(rows, currentIndex, {
  transform,
  trailLegend,
  trailMode: trailColorMode,
  cameraMode
});
```

## Descriptor Groups

`buildReplayVisualFrame` returns a grouped object for the active sample:

- `trajectory`: vehicle path, terrain profile, ground track, target points, and interceptor points.
- `groundReferences`: terrain profile, ground track, altitude stem, and terrain footprint descriptors.
- `vectors`: velocity, acceleration, and wind vector descriptors with origin, direction, scene length, color, and value label.
- `sensorCones`: radar altimeter, optical flow, and horizon descriptors with validity, range, cone angle, color, and status text.
- `rangeMarkers`: static range rings plus target/interceptor range line and best-miss descriptors when telemetry is present.
- `trail`: trail color stops and legend stops for `plain`, `speed`, `qbar`, `load`, `altitude`, `mach`, and `energy`.
- `contacts`: terrain proximity, touchdown, and impact descriptors derived from `ground_contact`, clearance, and vertical speed.

Each descriptor has a stable `id`, `visible` flag, colors, and source telemetry keys where useful. The intent is for `ReplayScene` to own actual Three.js meshes, while these helpers own the telemetry-to-visual decisions.

## Current-Frame Overlay State

Use `buildReplayOverlayState(rows, currentIndex, options)` for HUD and overlay UI that only needs the active frame. It returns:

- `altitudeReference`: current vehicle point, terrain point, clearance, and display label.
- `vectors`: velocity, acceleration, and wind descriptors for the current sample.
- `sensorCones`: active sensor cone descriptors only.
- `engagementMarkers`: active target/interceptor marker descriptors only.
- `contacts`: current impact/contact status descriptor.
- `trailLegend`: trail profile, min/max, and legend stops without per-sample trail stops.
- `cameraMode` and `cameraLabel`: resolved camera metadata for compact UI labels.

The helper does not build full trajectory arrays. For production mounting, compute row-set data once with `useMemo` and pass it back:

```tsx
const replayTransform = useMemo(() => createReplaySceneTransform(rows), [rows]);
const trailLegend = useMemo(() => buildTrailColorLegendDescriptor(rows, trailColorMode), [rows, trailColorMode]);

const overlayState = useMemo(
  () =>
    buildReplayOverlayState(rows, currentIndex, {
      transform: replayTransform,
      trailLegend,
      trailMode: trailColorMode,
      cameraMode,
      showVelocity,
      showAcceleration,
      showWind,
      showSensors
    }),
  [cameraMode, currentIndex, replayTransform, rows, showAcceleration, showSensors, showVelocity, showWind, trailColorMode, trailLegend]
);
```

If `transform` or `trailLegend` is omitted, the helper can derive them from `rows`; that is useful for simple callers, but parents with frame-by-frame playback should memoize those values so the per-frame call stays bounded to the current row and previous row.

## Legend Integration

The legend component is optional and can be layered over the canvas by a parent that already has positioning.

```tsx
import { ReplaySceneOverlayLegend } from "./ReplaySceneOverlayLegend";
import { buildReplayOverlayState } from "../replayVisuals";

const overlayState = buildReplayOverlayState(rows, currentIndex, {
  transform: replayTransform,
  trailLegend,
  trailMode: trailColorMode,
  cameraMode
});

<ReplaySceneOverlayLegend
  overlayState={overlayState}
/>;
```

The component also accepts individual props (`altitudeReference`, `vectors`, `sensorCones`, `engagementMarkers`, `contacts`, `trailLegend`, and `cameraLabel`) if the parent wants to keep its own state shape. `rangeMarkers` remains supported for callers that still use the broader `buildReplayVisualFrame` output.

The component uses inline styles only, so it does not require edits to `styles.css`. If the integrator wants the legend inside the current replay stage, the stage container needs `position: relative` or equivalent.

## Camera Metadata

`REPLAY_CAMERA_PRESETS` mirrors the current camera modes:

- `chase`
- `orbit`
- `cockpit`
- `map`
- `rangeSafety`

Each preset includes a label, intent, target strategy, scene offset, field of view, damping, and compact scale. This lets `Workbench` render camera controls from metadata later without hardcoding button labels.

## Integration Notes

- The utilities intentionally do not import Three.js. Convert `ReplayScenePoint` into `THREE.Vector3` at the scene boundary.
- Existing `ReplayScene` internals can be migrated incrementally: start with `createReplaySceneTransform` and `buildReplayTrajectoryVisuals`, then replace vector, sensor, range, and impact decisions one group at a time.
- `buildReplayVisualFrame` is convenient for broad debug snapshots. For production HUD/legend data, prefer `buildReplayOverlayState` with memoized `transform` and `trailLegend`.
- The helpers keep invalid sensor descriptors with `visible: false`. This is useful for legends and toggles because the descriptor IDs are stable.
