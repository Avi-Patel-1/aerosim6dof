import type { TelemetryRow } from "./types";

export type ReplayScenePoint = {
  x: number;
  y: number;
  z: number;
};

export type ReplayTelemetryPoint = {
  x_m: number;
  y_m: number;
  altitude_m: number;
};

export type ReplaySceneTransform = {
  center: {
    x_m: number;
    y_m: number;
  };
  scale: number;
  groundY: number;
  viewExtent: number;
  rawExtentM: number;
  maxAltitudeM: number;
};

export type ReplayTransformOptions = {
  groundY?: number;
  viewExtent?: number;
  includeTargets?: boolean;
  includeInterceptors?: boolean;
};

export type ReplayTrajectoryVisuals = {
  points: ReplayScenePoint[];
  terrainPoints: ReplayScenePoint[];
  groundTrackPoints: ReplayScenePoint[];
  targetPoints: Array<ReplayScenePoint | null>;
  interceptorPoints: Array<ReplayScenePoint | null>;
  transform: ReplaySceneTransform;
};

export type TerrainGroundReferenceKind = "terrain-profile" | "ground-track" | "altitude-stem" | "terrain-footprint";

export type TerrainGroundReferenceDescriptor = {
  id: string;
  kind: TerrainGroundReferenceKind;
  label: string;
  visible: boolean;
  terrainTied: true;
  color: string;
  opacity: number;
  dashed?: boolean;
  points?: ReplayScenePoint[];
  start?: ReplayScenePoint;
  end?: ReplayScenePoint;
  anchor?: ReplayScenePoint;
  radiusScene?: number;
  metricLabel?: string;
};

export type ReplayVectorOverlayId = "velocity" | "acceleration" | "wind";

export type ReplayVectorOverlayDescriptor = {
  id: ReplayVectorOverlayId;
  kind: "vector";
  label: string;
  visible: boolean;
  origin: ReplayScenePoint;
  direction: ReplayScenePoint;
  magnitude: number;
  lengthScene: number;
  color: string;
  unit: string;
  valueLabel: string;
  headLengthScene: number;
  headWidthScene: number;
  sourceKeys: string[];
};

export type SensorConeId = "radar-altimeter" | "optical-flow" | "horizon";

export type SensorConeDescriptor = {
  id: SensorConeId;
  kind: "sensor-cone";
  label: string;
  visible: boolean;
  sensorValid: boolean;
  origin: ReplayScenePoint;
  terrainAnchor: ReplayScenePoint;
  direction: ReplayScenePoint;
  rangeM: number | null;
  lengthScene: number;
  radiusScene: number;
  halfAngleDeg: number;
  color: string;
  opacity: number;
  wireframe: boolean;
  quality: number | null;
  statusLabel: string;
  sourceKeys: string[];
};

export type RangeMarkerKind = "ring" | "line" | "miss";

export type RangeMarkerDescriptor = {
  id: string;
  kind: RangeMarkerKind;
  label: string;
  visible: boolean;
  terrainTied: boolean;
  color: string;
  opacity: number;
  metricKey?: string;
  metricValueM?: number | null;
  metricLabel?: string;
  center?: ReplayScenePoint;
  radiusM?: number;
  radiusScene?: number;
  start?: ReplayScenePoint;
  end?: ReplayScenePoint;
  anchor?: ReplayScenePoint;
};

export type ImpactContactKind = "terrain-proximity" | "touchdown" | "impact";

export type ImpactContactDescriptor = {
  id: string;
  kind: ImpactContactKind;
  label: string;
  visible: boolean;
  anchor: ReplayScenePoint;
  terrainAnchor: ReplayScenePoint;
  radiusScene: number;
  color: string;
  opacity: number;
  clearanceM: number | null;
  verticalSpeedMps: number | null;
  severity: "info" | "caution" | "warning" | "critical";
  sourceKeys: string[];
};

export type ReplayTrailColorMode = "plain" | "speed" | "qbar" | "load" | "altitude" | "mach" | "energy";

export type TrailColorProfile = {
  id: ReplayTrailColorMode;
  label: string;
  channel: string | null;
  unit: string;
  colors: readonly [string, string] | readonly [string, string, string];
};

export type TrailColorStop = {
  index: number;
  value: number;
  ratio: number;
  color: string;
};

export type TrailColorLegendStop = {
  ratio: number;
  color: string;
  label: string;
};

export type TrailColorDescriptor = {
  mode: ReplayTrailColorMode;
  profile: TrailColorProfile;
  min: number;
  max: number;
  stops: TrailColorStop[];
  legendStops: TrailColorLegendStop[];
};

export type ReplayCameraPresetId = "chase" | "orbit" | "cockpit" | "map" | "rangeSafety";

export type ReplayCameraPresetMetadata = {
  id: ReplayCameraPresetId;
  label: string;
  intent: "tracking" | "inspection" | "pilot" | "situational-awareness" | "range-safety";
  description: string;
  targetStrategy: "vehicle" | "vehicle-forward" | "target-aware" | "overhead";
  offsetScene: ReplayScenePoint;
  fovDeg: number;
  damping: number;
  compactOffsetScale: number;
};

export type ReplayVisualFrameOptions = ReplayTransformOptions & {
  currentIndex?: number;
  trailMode?: ReplayTrailColorMode;
  rangeRingRadiiM?: number[];
};

export type ReplayVisualFrameDescriptors = {
  index: number;
  row: TelemetryRow | undefined;
  previousRow: TelemetryRow | undefined;
  currentPoint: ReplayScenePoint;
  terrainPoint: ReplayScenePoint;
  trajectory: ReplayTrajectoryVisuals;
  trail: TrailColorDescriptor;
  groundReferences: TerrainGroundReferenceDescriptor[];
  vectors: ReplayVectorOverlayDescriptor[];
  sensorCones: SensorConeDescriptor[];
  rangeMarkers: RangeMarkerDescriptor[];
  contacts: ImpactContactDescriptor[];
};

export const DEFAULT_REPLAY_GROUND_Y = -10.28;
export const DEFAULT_REPLAY_VIEW_EXTENT = 105;

export const REPLAY_VISUAL_COLORS = {
  starlight: "#ededf3",
  ghostBlue: "#cdddff",
  mercuryBlue: "#5266eb",
  lead: "#70707d",
  graphite: "#272735",
  warning: "#f4c95d",
  critical: "#ff6b6b",
  success: "#7bd88f"
} as const;

export const REPLAY_TRAIL_COLOR_PROFILES: Record<ReplayTrailColorMode, TrailColorProfile> = {
  plain: {
    id: "plain",
    label: "Plain",
    channel: null,
    unit: "",
    colors: [REPLAY_VISUAL_COLORS.starlight, REPLAY_VISUAL_COLORS.starlight]
  },
  speed: {
    id: "speed",
    label: "Speed",
    channel: "speed_mps",
    unit: "m/s",
    colors: [REPLAY_VISUAL_COLORS.lead, REPLAY_VISUAL_COLORS.ghostBlue, REPLAY_VISUAL_COLORS.starlight]
  },
  qbar: {
    id: "qbar",
    label: "Qbar",
    channel: "qbar_pa",
    unit: "Pa",
    colors: [REPLAY_VISUAL_COLORS.mercuryBlue, REPLAY_VISUAL_COLORS.ghostBlue, REPLAY_VISUAL_COLORS.warning]
  },
  load: {
    id: "load",
    label: "Load",
    channel: "load_factor_g",
    unit: "g",
    colors: [REPLAY_VISUAL_COLORS.ghostBlue, REPLAY_VISUAL_COLORS.warning, REPLAY_VISUAL_COLORS.critical]
  },
  altitude: {
    id: "altitude",
    label: "Altitude",
    channel: "altitude_m",
    unit: "m",
    colors: [REPLAY_VISUAL_COLORS.lead, REPLAY_VISUAL_COLORS.ghostBlue, REPLAY_VISUAL_COLORS.starlight]
  },
  mach: {
    id: "mach",
    label: "Mach",
    channel: "mach",
    unit: "",
    colors: [REPLAY_VISUAL_COLORS.lead, REPLAY_VISUAL_COLORS.mercuryBlue, REPLAY_VISUAL_COLORS.warning]
  },
  energy: {
    id: "energy",
    label: "Energy",
    channel: "energy_j_per_kg",
    unit: "J/kg",
    colors: [REPLAY_VISUAL_COLORS.lead, REPLAY_VISUAL_COLORS.success, REPLAY_VISUAL_COLORS.starlight]
  }
};

export const REPLAY_CAMERA_PRESETS: Record<ReplayCameraPresetId, ReplayCameraPresetMetadata> = {
  chase: {
    id: "chase",
    label: "Chase",
    intent: "tracking",
    description: "Offset behind the vehicle with a slight right shoulder bias.",
    targetStrategy: "vehicle",
    offsetScene: { x: -42, y: 20, z: 9 },
    fovDeg: 44,
    damping: 0.18,
    compactOffsetScale: 0.72
  },
  orbit: {
    id: "orbit",
    label: "Orbit",
    intent: "inspection",
    description: "Slow orbit around the active sample for attitude and path inspection.",
    targetStrategy: "vehicle",
    offsetScene: { x: 62, y: 36, z: 0 },
    fovDeg: 44,
    damping: 0.18,
    compactOffsetScale: 0.86
  },
  cockpit: {
    id: "cockpit",
    label: "Cockpit",
    intent: "pilot",
    description: "Forward-looking view from just ahead of the vehicle body.",
    targetStrategy: "vehicle-forward",
    offsetScene: { x: 5.5, y: 2.2, z: 0 },
    fovDeg: 52,
    damping: 0.34,
    compactOffsetScale: 1
  },
  map: {
    id: "map",
    label: "Map",
    intent: "situational-awareness",
    description: "Near-vertical overhead camera for range geometry and ground track.",
    targetStrategy: "overhead",
    offsetScene: { x: 0, y: 118, z: 0.1 },
    fovDeg: 44,
    damping: 0.18,
    compactOffsetScale: 0.78
  },
  rangeSafety: {
    id: "rangeSafety",
    label: "Range Safety",
    intent: "range-safety",
    description: "Oblique standoff view that can bias its look target toward an engagement target.",
    targetStrategy: "target-aware",
    offsetScene: { x: -108, y: 56, z: 112 },
    fovDeg: 44,
    damping: 0.18,
    compactOffsetScale: 0.78
  }
};

const VECTOR_STYLE: Record<
  ReplayVectorOverlayId,
  {
    label: string;
    color: string;
    unit: string;
    offset: ReplayScenePoint;
    minMagnitude: number;
    minLengthScene: number;
    maxLengthScene: number;
    lengthPerUnit: number;
    headLengthScene: number;
    headWidthScene: number;
    sourceKeys: string[];
  }
> = {
  velocity: {
    label: "Velocity",
    color: REPLAY_VISUAL_COLORS.ghostBlue,
    unit: "m/s",
    offset: { x: 0, y: 6, z: 0 },
    minMagnitude: 0.01,
    minLengthScene: 8,
    maxLengthScene: 34,
    lengthPerUnit: 0.22,
    headLengthScene: 3.1,
    headWidthScene: 1.4,
    sourceKeys: ["vx_mps", "vy_mps", "vz_mps"]
  },
  acceleration: {
    label: "Acceleration",
    color: REPLAY_VISUAL_COLORS.starlight,
    unit: "m/s2",
    offset: { x: 0, y: 9, z: 0 },
    minMagnitude: 0.01,
    minLengthScene: 6,
    maxLengthScene: 24,
    lengthPerUnit: 2.4,
    headLengthScene: 2.5,
    headWidthScene: 1.2,
    sourceKeys: ["time_s", "vx_mps", "vy_mps", "vz_mps"]
  },
  wind: {
    label: "Wind",
    color: REPLAY_VISUAL_COLORS.starlight,
    unit: "m/s",
    offset: { x: 0, y: 16, z: 0 },
    minMagnitude: 0.01,
    minLengthScene: 6,
    maxLengthScene: 18,
    lengthPerUnit: 1.7,
    headLengthScene: 3.2,
    headWidthScene: 1.5,
    sourceKeys: ["wind_x_mps", "wind_y_mps", "wind_z_mps"]
  }
};

function point(x = 0, y = 0, z = 0): ReplayScenePoint {
  return { x, y, z };
}

function add(a: ReplayScenePoint, b: ReplayScenePoint): ReplayScenePoint {
  return point(a.x + b.x, a.y + b.y, a.z + b.z);
}

function subtract(a: ReplayScenePoint, b: ReplayScenePoint): ReplayScenePoint {
  return point(a.x - b.x, a.y - b.y, a.z - b.z);
}

function scale(a: ReplayScenePoint, scalar: number): ReplayScenePoint {
  return point(a.x * scalar, a.y * scalar, a.z * scalar);
}

function magnitude(vector: ReplayScenePoint): number {
  return Math.hypot(vector.x, vector.y, vector.z);
}

function normalize(vector: ReplayScenePoint): ReplayScenePoint {
  const length = magnitude(vector);
  return length > 1e-9 ? scale(vector, 1 / length) : point(1, 0, 0);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function formatMetric(value: number | null, unit: string, digits = 1): string {
  if (value === null || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}

function colorComponent(hex: string, start: number): number {
  return Number.parseInt(hex.slice(start, start + 2), 16);
}

function lerp(a: number, b: number, ratio: number): number {
  return a + (b - a) * ratio;
}

function lerpHexColor(start: string, end: string, ratio: number): string {
  const cleanStart = start.startsWith("#") ? start : `#${start}`;
  const cleanEnd = end.startsWith("#") ? end : `#${end}`;
  const t = clamp(ratio, 0, 1);
  const red = Math.round(lerp(colorComponent(cleanStart, 1), colorComponent(cleanEnd, 1), t));
  const green = Math.round(lerp(colorComponent(cleanStart, 3), colorComponent(cleanEnd, 3), t));
  const blue = Math.round(lerp(colorComponent(cleanStart, 5), colorComponent(cleanEnd, 5), t));
  return `#${[red, green, blue].map((part) => part.toString(16).padStart(2, "0")).join("")}`;
}

export function telemetryNumber(row: TelemetryRow | undefined, key: string, fallback = 0): number {
  const value = row?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function telemetryOptionalNumber(row: TelemetryRow | undefined, key: string): number | null {
  const value = row?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function telemetryString(row: TelemetryRow | undefined, key: string): string {
  const value = row?.[key];
  return typeof value === "string" ? value : "";
}

export function sceneDistanceFromMeters(distanceM: number, transform: ReplaySceneTransform): number {
  return Math.max(0, distanceM * transform.scale);
}

export function telemetryPointToScene(pointM: ReplayTelemetryPoint, transform: ReplaySceneTransform): ReplayScenePoint {
  return {
    x: (pointM.x_m - transform.center.x_m) * transform.scale,
    y: transform.groundY + Math.max(0, pointM.altitude_m) * transform.scale,
    z: -(pointM.y_m - transform.center.y_m) * transform.scale
  };
}

export function telemetryVectorToScene(vectorM: { x: number; y: number; z: number }): ReplayScenePoint {
  return point(vectorM.x, vectorM.z, -vectorM.y);
}

export function createReplaySceneTransform(rows: TelemetryRow[], options: ReplayTransformOptions = {}): ReplaySceneTransform {
  const groundY = options.groundY ?? DEFAULT_REPLAY_GROUND_Y;
  const viewExtent = options.viewExtent ?? DEFAULT_REPLAY_VIEW_EXTENT;
  const includeTargets = options.includeTargets ?? true;
  const includeInterceptors = options.includeInterceptors ?? true;
  const extents: ReplayTelemetryPoint[] = [];

  rows.forEach((row) => {
    extents.push({
      x_m: telemetryNumber(row, "x_m"),
      y_m: telemetryNumber(row, "y_m"),
      altitude_m: telemetryNumber(row, "altitude_m")
    });
    extents.push({
      x_m: telemetryNumber(row, "x_m"),
      y_m: telemetryNumber(row, "y_m"),
      altitude_m: telemetryNumber(row, "terrain_elevation_m")
    });
    if (includeTargets) {
      const target = optionalPointFromRow(row, "target_x_m", "target_y_m", "target_z_m");
      if (target) {
        extents.push(target);
      }
    }
    if (includeInterceptors) {
      const interceptor = optionalPointFromRow(row, "interceptor_x_m", "interceptor_y_m", "interceptor_z_m");
      if (interceptor) {
        extents.push(interceptor);
      }
    }
  });

  if (!extents.length) {
    return {
      center: { x_m: 0, y_m: 0 },
      scale: 1,
      groundY,
      viewExtent,
      rawExtentM: 1,
      maxAltitudeM: 1
    };
  }

  const xs = extents.map((rawPoint) => rawPoint.x_m);
  const ys = extents.map((rawPoint) => rawPoint.y_m);
  const altitudes = extents.map((rawPoint) => Math.max(0, rawPoint.altitude_m));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const maxAltitudeM = Math.max(...altitudes, 1);
  const rawExtentM = Math.max(maxX - minX, maxY - minY, maxAltitudeM, 1);

  return {
    center: {
      x_m: (minX + maxX) * 0.5,
      y_m: (minY + maxY) * 0.5
    },
    scale: viewExtent / rawExtentM,
    groundY,
    viewExtent,
    rawExtentM,
    maxAltitudeM
  };
}

export function buildReplayTrajectoryVisuals(rows: TelemetryRow[], transform = createReplaySceneTransform(rows)): ReplayTrajectoryVisuals {
  const points = rows.map((row) =>
    telemetryPointToScene(
      {
        x_m: telemetryNumber(row, "x_m"),
        y_m: telemetryNumber(row, "y_m"),
        altitude_m: telemetryNumber(row, "altitude_m")
      },
      transform
    )
  );
  const terrainPoints = rows.map((row) =>
    telemetryPointToScene(
      {
        x_m: telemetryNumber(row, "x_m"),
        y_m: telemetryNumber(row, "y_m"),
        altitude_m: telemetryNumber(row, "terrain_elevation_m")
      },
      transform
    )
  );
  const groundTrackPoints = points.map((vehiclePoint, index) => point(vehiclePoint.x, terrainPoints[index]?.y ?? transform.groundY, vehiclePoint.z));
  const targetPoints = rows.map((row) => {
    const target = optionalPointFromRow(row, "target_x_m", "target_y_m", "target_z_m");
    return target ? telemetryPointToScene(target, transform) : null;
  });
  const interceptorPoints = rows.map((row) => {
    const interceptor = optionalPointFromRow(row, "interceptor_x_m", "interceptor_y_m", "interceptor_z_m");
    return interceptor ? telemetryPointToScene(interceptor, transform) : null;
  });

  return {
    points: points.length ? points : [point()],
    terrainPoints: terrainPoints.length ? terrainPoints : [point(0, transform.groundY, 0)],
    groundTrackPoints: groundTrackPoints.length ? groundTrackPoints : [point(0, transform.groundY, 0)],
    targetPoints: targetPoints.length ? targetPoints : [null],
    interceptorPoints: interceptorPoints.length ? interceptorPoints : [null],
    transform
  };
}

export function clampReplayIndex(index: number, sampleCount: number): number {
  return Math.trunc(clamp(index, 0, Math.max(sampleCount - 1, 0)));
}

export function buildTerrainGroundReferences(
  trajectory: ReplayTrajectoryVisuals,
  currentIndex: number,
  options: { compact?: boolean } = {}
): TerrainGroundReferenceDescriptor[] {
  const index = clampReplayIndex(currentIndex, trajectory.points.length);
  const current = trajectory.points[index] ?? point();
  const terrain = trajectory.terrainPoints[index] ?? point(current.x, trajectory.transform.groundY, current.z);
  const clearanceM = Math.max(0, (current.y - terrain.y) / Math.max(trajectory.transform.scale, 1e-9));

  return [
    {
      id: "terrain-profile",
      kind: "terrain-profile",
      label: "Terrain profile",
      visible: trajectory.terrainPoints.length > 1,
      terrainTied: true,
      color: REPLAY_VISUAL_COLORS.ghostBlue,
      opacity: 0.34,
      points: trajectory.terrainPoints
    },
    {
      id: "ground-track",
      kind: "ground-track",
      label: "Ground track",
      visible: trajectory.groundTrackPoints.length > 1,
      terrainTied: true,
      color: REPLAY_VISUAL_COLORS.lead,
      opacity: 0.42,
      dashed: true,
      points: trajectory.groundTrackPoints
    },
    {
      id: "altitude-stem",
      kind: "altitude-stem",
      label: "Altitude stem",
      visible: !options.compact,
      terrainTied: true,
      color: REPLAY_VISUAL_COLORS.starlight,
      opacity: 0.32,
      start: terrain,
      end: current,
      metricLabel: formatMetric(clearanceM, "m", 1)
    },
    {
      id: "terrain-footprint",
      kind: "terrain-footprint",
      label: "Terrain footprint",
      visible: true,
      terrainTied: true,
      color: REPLAY_VISUAL_COLORS.ghostBlue,
      opacity: 0.52,
      anchor: terrain,
      radiusScene: 1.8
    }
  ];
}

export function buildReplayVectorOverlays(
  row: TelemetryRow | undefined,
  previousRow: TelemetryRow | undefined,
  currentPoint: ReplayScenePoint,
  options: Partial<Record<ReplayVectorOverlayId, boolean>> = {}
): ReplayVectorOverlayDescriptor[] {
  const velocityVector = telemetryVectorToScene({
    x: telemetryNumber(row, "vx_mps"),
    y: telemetryNumber(row, "vy_mps"),
    z: telemetryNumber(row, "vz_mps")
  });
  const windVector = telemetryVectorToScene({
    x: telemetryNumber(row, "wind_x_mps"),
    y: telemetryNumber(row, "wind_y_mps"),
    z: telemetryNumber(row, "wind_z_mps")
  });
  const accelerationVector = accelerationFromRows(row, previousRow);

  return [
    vectorDescriptor("velocity", velocityVector, currentPoint, options.velocity ?? true),
    vectorDescriptor("acceleration", accelerationVector, currentPoint, options.acceleration ?? false),
    vectorDescriptor("wind", windVector, currentPoint, options.wind ?? true)
  ];
}

export function buildSensorConeDescriptors(
  row: TelemetryRow | undefined,
  currentPoint: ReplayScenePoint,
  terrainPoint: ReplayScenePoint,
  transform: ReplaySceneTransform
): SensorConeDescriptor[] {
  const altitudeM = telemetryOptionalNumber(row, "altitude_m");
  const terrainM = telemetryOptionalNumber(row, "terrain_elevation_m") ?? 0;
  const clearanceM = altitudeM === null ? null : Math.max(0, altitudeM - terrainM);
  const radarRangeM = telemetryOptionalNumber(row, "radar_agl_m") ?? clearanceM;
  const opticalQuality = telemetryOptionalNumber(row, "optical_flow_quality");
  const horizonDirection = forwardVectorFromAttitude(row);

  const descriptors: SensorConeDescriptor[] = [
    {
      id: "radar-altimeter",
      kind: "sensor-cone",
      label: "Radar altimeter",
      visible: telemetryNumber(row, "radar_valid") > 0.5,
      sensorValid: telemetryNumber(row, "radar_valid") > 0.5,
      origin: currentPoint,
      terrainAnchor: terrainPoint,
      direction: point(0, -1, 0),
      rangeM: radarRangeM,
      lengthScene: clamp(sceneDistanceFromMeters(radarRangeM ?? 0, transform), 5, 44),
      radiusScene: coneRadius(sceneDistanceFromMeters(radarRangeM ?? 0, transform), 14),
      halfAngleDeg: 14,
      color: REPLAY_VISUAL_COLORS.ghostBlue,
      opacity: 0.14,
      wireframe: true,
      quality: null,
      statusLabel: formatMetric(radarRangeM, "m", 1),
      sourceKeys: ["radar_valid", "radar_agl_m"]
    },
    {
      id: "optical-flow",
      kind: "sensor-cone",
      label: "Optical flow",
      visible: telemetryNumber(row, "optical_flow_valid") > 0.5,
      sensorValid: telemetryNumber(row, "optical_flow_valid") > 0.5,
      origin: currentPoint,
      terrainAnchor: terrainPoint,
      direction: point(0, -1, 0),
      rangeM: clearanceM,
      lengthScene: clamp(sceneDistanceFromMeters(clearanceM ?? 0, transform), 6, 36),
      radiusScene: coneRadius(sceneDistanceFromMeters(clearanceM ?? 0, transform), 22),
      halfAngleDeg: 22,
      color: REPLAY_VISUAL_COLORS.success,
      opacity: 0.12,
      wireframe: true,
      quality: opticalQuality,
      statusLabel: opticalQuality === null ? "valid" : `quality ${opticalQuality.toFixed(2)}`,
      sourceKeys: ["optical_flow_valid", "optical_flow_quality", "optical_flow_x_radps", "optical_flow_y_radps"]
    },
    {
      id: "horizon",
      kind: "sensor-cone",
      label: "Horizon",
      visible: telemetryNumber(row, "horizon_valid") > 0.5,
      sensorValid: telemetryNumber(row, "horizon_valid") > 0.5,
      origin: add(currentPoint, point(0, 2.8, 0)),
      terrainAnchor: terrainPoint,
      direction: horizonDirection,
      rangeM: null,
      lengthScene: 28,
      radiusScene: coneRadius(28, 32),
      halfAngleDeg: 32,
      color: REPLAY_VISUAL_COLORS.starlight,
      opacity: 0.1,
      wireframe: true,
      quality: null,
      statusLabel: horizonStatusLabel(row),
      sourceKeys: ["horizon_valid", "horizon_roll_deg", "horizon_pitch_deg"]
    }
  ];

  return descriptors;
}

export function buildRangeRingMarkers(
  transform: ReplaySceneTransform,
  radiiM: number[] = [500, 1000, 2500, 5000],
  center: ReplayScenePoint = point(0, transform.groundY + 0.08, 0)
): RangeMarkerDescriptor[] {
  return radiiM
    .filter((radiusM) => Number.isFinite(radiusM) && radiusM > 0)
    .map((radiusM) => ({
      id: `range-ring-${radiusM}`,
      kind: "ring",
      label: `${formatCompactNumber(radiusM)} m ring`,
      visible: true,
      terrainTied: true,
      color: REPLAY_VISUAL_COLORS.starlight,
      opacity: radiusM <= 1000 ? 0.16 : 0.1,
      center,
      radiusM,
      radiusScene: sceneDistanceFromMeters(radiusM, transform),
      metricValueM: radiusM,
      metricLabel: formatMetric(radiusM, "m", 0)
    }));
}

export function buildEngagementRangeMarkers(
  row: TelemetryRow | undefined,
  currentPoint: ReplayScenePoint,
  terrainPoint: ReplayScenePoint,
  targetPoint: ReplayScenePoint | null,
  interceptorPoint: ReplayScenePoint | null,
  transform: ReplaySceneTransform
): RangeMarkerDescriptor[] {
  const targetRangeM = telemetryOptionalNumber(row, "target_range_m");
  const interceptorRangeM = telemetryOptionalNumber(row, "interceptor_range_m");
  const bestMissM = telemetryOptionalNumber(row, "interceptor_best_miss_m");
  const markers: RangeMarkerDescriptor[] = [];

  if (targetPoint) {
    markers.push({
      id: "target-range-line",
      kind: "line",
      label: "Target range",
      visible: true,
      terrainTied: false,
      color: REPLAY_VISUAL_COLORS.ghostBlue,
      opacity: 0.5,
      metricKey: "target_range_m",
      metricValueM: targetRangeM,
      metricLabel: formatMetric(targetRangeM, "m", 1),
      start: currentPoint,
      end: targetPoint
    });
  }

  if (targetRangeM !== null) {
    markers.push({
      id: "target-range-ring",
      kind: "ring",
      label: "Target range ring",
      visible: true,
      terrainTied: true,
      color: REPLAY_VISUAL_COLORS.ghostBlue,
      opacity: 0.14,
      metricKey: "target_range_m",
      metricValueM: targetRangeM,
      metricLabel: formatMetric(targetRangeM, "m", 1),
      center: terrainPoint,
      radiusM: targetRangeM,
      radiusScene: sceneDistanceFromMeters(targetRangeM, transform)
    });
  }

  if (targetPoint && interceptorPoint && telemetryNumber(row, "interceptor_launched") > 0.5) {
    const midpoint = scale(add(targetPoint, interceptorPoint), 0.5);
    markers.push({
      id: "interceptor-range-line",
      kind: "line",
      label: "Interceptor range",
      visible: true,
      terrainTied: false,
      color: REPLAY_VISUAL_COLORS.starlight,
      opacity: 0.42,
      metricKey: "interceptor_range_m",
      metricValueM: interceptorRangeM,
      metricLabel: formatMetric(interceptorRangeM, "m", 1),
      start: interceptorPoint,
      end: targetPoint
    });
    markers.push({
      id: "interceptor-best-miss",
      kind: "miss",
      label: "Best miss",
      visible: bestMissM !== null,
      terrainTied: false,
      color: REPLAY_VISUAL_COLORS.warning,
      opacity: 0.72,
      metricKey: "interceptor_best_miss_m",
      metricValueM: bestMissM,
      metricLabel: formatMetric(bestMissM, "m", 1),
      anchor: midpoint,
      radiusM: bestMissM ?? undefined,
      radiusScene: bestMissM === null ? undefined : clamp(sceneDistanceFromMeters(bestMissM, transform), 1.8, 18)
    });
  }

  return markers;
}

export function buildImpactContactDescriptors(
  row: TelemetryRow | undefined,
  currentPoint: ReplayScenePoint,
  terrainPoint: ReplayScenePoint
): ImpactContactDescriptor[] {
  const altitudeM = telemetryOptionalNumber(row, "altitude_m");
  const terrainM = telemetryOptionalNumber(row, "terrain_elevation_m") ?? 0;
  const clearanceM = altitudeM === null ? null : altitudeM - terrainM;
  const verticalSpeedMps = telemetryOptionalNumber(row, "vz_mps");
  const downwardSpeedMps = Math.max(0, -(verticalSpeedMps ?? 0));
  const groundContact = telemetryNumber(row, "ground_contact") > 0.5;
  const nearTerrain = clearanceM !== null && clearanceM <= 10;
  const impactKind: ImpactContactKind = groundContact ? (downwardSpeedMps > 8 ? "impact" : "touchdown") : "terrain-proximity";
  const severity = impactKind === "impact" ? "critical" : impactKind === "touchdown" ? "warning" : "caution";

  return [
    {
      id: "ground-contact",
      kind: impactKind,
      label: impactKind === "terrain-proximity" ? "Terrain proximity" : impactKind === "touchdown" ? "Touchdown" : "Impact",
      visible: groundContact || nearTerrain,
      anchor: currentPoint,
      terrainAnchor: terrainPoint,
      radiusScene: clamp(4.8 + downwardSpeedMps * 0.22, 3.6, 16),
      color: severity === "critical" ? REPLAY_VISUAL_COLORS.critical : severity === "warning" ? REPLAY_VISUAL_COLORS.warning : REPLAY_VISUAL_COLORS.ghostBlue,
      opacity: severity === "critical" ? 0.86 : 0.68,
      clearanceM,
      verticalSpeedMps,
      severity,
      sourceKeys: ["ground_contact", "altitude_m", "terrain_elevation_m", "vz_mps"]
    }
  ];
}

export function getTrailColorProfile(mode: ReplayTrailColorMode): TrailColorProfile {
  return REPLAY_TRAIL_COLOR_PROFILES[mode] ?? REPLAY_TRAIL_COLOR_PROFILES.plain;
}

export function colorForTrailRatio(profile: TrailColorProfile, ratio: number): string {
  const colors = profile.colors;
  if (colors.length === 2) {
    return lerpHexColor(colors[0], colors[1], ratio);
  }
  if (ratio <= 0.5) {
    return lerpHexColor(colors[0], colors[1], ratio * 2);
  }
  return lerpHexColor(colors[1], colors[2], (ratio - 0.5) * 2);
}

export function buildTrailColorDescriptor(rows: TelemetryRow[], mode: ReplayTrailColorMode = "plain"): TrailColorDescriptor {
  const profile = getTrailColorProfile(mode);
  const values = profile.channel ? rows.map((row) => telemetryNumber(row, profile.channel ?? "", 0)) : rows.map(() => 0);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  const span = Math.max(max - min, 1e-9);
  const stops = values.map((value, index) => {
    const ratio = profile.channel ? clamp((value - min) / span, 0, 1) : 0;
    return {
      index,
      value,
      ratio,
      color: colorForTrailRatio(profile, ratio)
    };
  });
  const legendStops: TrailColorLegendStop[] = [0, 0.5, 1].map((ratio) => ({
    ratio,
    color: colorForTrailRatio(profile, ratio),
    label: profile.channel ? formatMetric(min + span * ratio, profile.unit, profile.unit === "Pa" || profile.unit === "m" ? 0 : 1) : profile.label
  }));

  return {
    mode,
    profile,
    min,
    max,
    stops,
    legendStops
  };
}

export function getReplayCameraPreset(id: ReplayCameraPresetId): ReplayCameraPresetMetadata {
  return REPLAY_CAMERA_PRESETS[id] ?? REPLAY_CAMERA_PRESETS.chase;
}

export function replayCameraPresetOptions(): ReplayCameraPresetMetadata[] {
  return Object.values(REPLAY_CAMERA_PRESETS);
}

export function buildReplayVisualFrame(rows: TelemetryRow[], options: ReplayVisualFrameOptions = {}): ReplayVisualFrameDescriptors {
  const transform = createReplaySceneTransform(rows, options);
  const trajectory = buildReplayTrajectoryVisuals(rows, transform);
  const index = clampReplayIndex(options.currentIndex ?? 0, rows.length);
  const row = rows[index];
  const previousRow = rows[Math.max(index - 1, 0)];
  const currentPoint = trajectory.points[index] ?? point();
  const terrainPoint = trajectory.terrainPoints[index] ?? point(currentPoint.x, transform.groundY, currentPoint.z);
  const targetPoint = trajectory.targetPoints[index] ?? null;
  const interceptorPoint = trajectory.interceptorPoints[index] ?? null;

  return {
    index,
    row,
    previousRow,
    currentPoint,
    terrainPoint,
    trajectory,
    trail: buildTrailColorDescriptor(rows, options.trailMode ?? "plain"),
    groundReferences: buildTerrainGroundReferences(trajectory, index),
    vectors: buildReplayVectorOverlays(row, previousRow, currentPoint),
    sensorCones: buildSensorConeDescriptors(row, currentPoint, terrainPoint, transform),
    rangeMarkers: [
      ...buildRangeRingMarkers(transform, options.rangeRingRadiiM),
      ...buildEngagementRangeMarkers(row, currentPoint, terrainPoint, targetPoint, interceptorPoint, transform)
    ],
    contacts: buildImpactContactDescriptors(row, currentPoint, terrainPoint)
  };
}

function optionalPointFromRow(row: TelemetryRow, xKey: string, yKey: string, altitudeKey: string): ReplayTelemetryPoint | null {
  const x = telemetryOptionalNumber(row, xKey);
  const y = telemetryOptionalNumber(row, yKey);
  const altitude = telemetryOptionalNumber(row, altitudeKey);
  return x === null || y === null || altitude === null ? null : { x_m: x, y_m: y, altitude_m: altitude };
}

function vectorDescriptor(
  id: ReplayVectorOverlayId,
  vector: ReplayScenePoint,
  currentPoint: ReplayScenePoint,
  enabled: boolean
): ReplayVectorOverlayDescriptor {
  const style = VECTOR_STYLE[id];
  const vectorMagnitude = magnitude(vector);
  return {
    id,
    kind: "vector",
    label: style.label,
    visible: enabled && vectorMagnitude > style.minMagnitude,
    origin: add(currentPoint, style.offset),
    direction: normalize(vector),
    magnitude: vectorMagnitude,
    lengthScene: clamp(vectorMagnitude * style.lengthPerUnit, style.minLengthScene, style.maxLengthScene),
    color: style.color,
    unit: style.unit,
    valueLabel: formatMetric(vectorMagnitude, style.unit, id === "acceleration" ? 2 : 1),
    headLengthScene: style.headLengthScene,
    headWidthScene: style.headWidthScene,
    sourceKeys: style.sourceKeys
  };
}

function accelerationFromRows(row: TelemetryRow | undefined, previousRow: TelemetryRow | undefined): ReplayScenePoint {
  if (!row || !previousRow || row === previousRow) {
    return point();
  }
  const dt = Math.max(telemetryNumber(row, "time_s") - telemetryNumber(previousRow, "time_s"), 1e-3);
  return telemetryVectorToScene({
    x: (telemetryNumber(row, "vx_mps") - telemetryNumber(previousRow, "vx_mps")) / dt,
    y: (telemetryNumber(row, "vy_mps") - telemetryNumber(previousRow, "vy_mps")) / dt,
    z: (telemetryNumber(row, "vz_mps") - telemetryNumber(previousRow, "vz_mps")) / dt
  });
}

function coneRadius(lengthScene: number, halfAngleDeg: number): number {
  return Math.max(1.2, lengthScene * Math.tan((halfAngleDeg * Math.PI) / 180));
}

function forwardVectorFromAttitude(row: TelemetryRow | undefined): ReplayScenePoint {
  const pitch = (telemetryNumber(row, "pitch_deg") * Math.PI) / 180;
  const yaw = (telemetryNumber(row, "yaw_deg") * Math.PI) / 180;
  return normalize({
    x: Math.cos(pitch) * Math.cos(yaw),
    y: Math.sin(pitch),
    z: -Math.cos(pitch) * Math.sin(yaw)
  });
}

function horizonStatusLabel(row: TelemetryRow | undefined): string {
  const roll = telemetryOptionalNumber(row, "horizon_roll_deg");
  const pitch = telemetryOptionalNumber(row, "horizon_pitch_deg");
  if (roll === null && pitch === null) {
    return "valid";
  }
  return `roll ${formatMetric(roll, "deg", 1)} / pitch ${formatMetric(pitch, "deg", 1)}`;
}

function formatCompactNumber(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `${Number((value / 1000).toFixed(1))}k`;
  }
  return value.toFixed(0);
}
