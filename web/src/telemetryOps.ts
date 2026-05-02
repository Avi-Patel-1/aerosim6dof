import type { TelemetryChannelMetadata, TelemetryRow } from "./types";
import { channelLabel, channelUnit, fallbackChannelLabel, formatTelemetryValue, metadataFor } from "./telemetry";

export const TELEMETRY_OPS_GROUPS = [
  "Vehicle State",
  "GNC State",
  "Propulsion",
  "Aerodynamics",
  "Environment",
  "Sensors",
  "Controls/Actuators",
  "Faults/Alarms",
  "Events",
  "Derived Performance",
  "Engagement",
] as const;

export type TelemetryOpsGroup = (typeof TELEMETRY_OPS_GROUPS)[number];

export type TelemetryChannelDescriptor = {
  key: string;
  label: string;
  unit: string;
  description: string;
  group: TelemetryOpsGroup;
  rawGroup: string;
  source: TelemetryChannelMetadata["source"] | "";
  role: TelemetryChannelMetadata["role"] | "";
  derived: boolean;
  metadata?: TelemetryChannelMetadata;
};

export type TelemetryChannelFilter = {
  query?: string;
  groups?: TelemetryOpsGroup[];
  sources?: TelemetryChannelMetadata["source"][];
  roles?: TelemetryChannelMetadata["role"][];
};

export type TelemetryNumericStats = {
  channel: string;
  current: number | null;
  min: number | null;
  max: number | null;
  latest: number | null;
  count: number;
  currentIndex: number;
  latestIndex: number;
};

export type CurrentValueRow = TelemetryChannelDescriptor & {
  value: TelemetryRow[string] | undefined;
  formattedValue: string;
  numeric: TelemetryNumericStats;
  pinned: boolean;
};

export type TelemetryCsvRowSet = {
  id?: string;
  rows: TelemetryRow[];
};

export type TelemetryCsvOptions = {
  includeRunId?: boolean;
  includeRowIndex?: boolean;
  includeSourceColumns?: boolean;
};

export type TelemetryChartLayout = {
  id: string;
  name: string;
  channels: string[];
  createdAt: string;
  updatedAt: string;
  config?: Record<string, unknown>;
};

export type RelatedChannelSuggestion = {
  channel: string;
  label: string;
  score: number;
  reasons: string[];
  metadata?: TelemetryChannelMetadata;
};

export type NearestTelemetryRow = {
  row: TelemetryRow | null;
  index: number;
  time: number | null;
  delta: number | null;
};

const LAYOUTS_STORAGE_KEY = "AeroLab:telemetryOps:chartLayouts";
const PINNED_CHANNELS_STORAGE_KEY = "AeroLab:telemetryOps:pinnedChannels";

const GROUP_ALIASES: Record<string, TelemetryOpsGroup> = {
  vehicle: "Vehicle State",
  "vehicle state": "Vehicle State",
  state: "Vehicle State",
  navigation: "GNC State",
  guidance: "GNC State",
  control: "Controls/Actuators",
  controls: "Controls/Actuators",
  actuator: "Controls/Actuators",
  actuators: "Controls/Actuators",
  "controls/actuators": "Controls/Actuators",
  gnc: "GNC State",
  "gnc state": "GNC State",
  propulsion: "Propulsion",
  engine: "Propulsion",
  motor: "Propulsion",
  aero: "Aerodynamics",
  aerodynamics: "Aerodynamics",
  atmosphere: "Environment",
  environment: "Environment",
  env: "Environment",
  sensor: "Sensors",
  sensors: "Sensors",
  fault: "Faults/Alarms",
  faults: "Faults/Alarms",
  alarm: "Faults/Alarms",
  alarms: "Faults/Alarms",
  "faults/alarms": "Faults/Alarms",
  event: "Events",
  events: "Events",
  derived: "Derived Performance",
  performance: "Derived Performance",
  "derived performance": "Derived Performance",
  engagement: "Engagement",
  intercept: "Engagement",
  target: "Engagement",
};

function browserStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

function safeJsonParse<T>(raw: string | null, fallback: T): T {
  if (!raw) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    return parsed as T;
  } catch {
    return fallback;
  }
}

function asFiniteNumber(value: TelemetryRow[string] | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalized(value: string | undefined): string {
  return (value || "").trim().toLowerCase();
}

function isTelemetryOpsGroup(value: string): value is TelemetryOpsGroup {
  return TELEMETRY_OPS_GROUPS.includes(value as TelemetryOpsGroup);
}

export function collectTelemetryChannels(
  rows: TelemetryRow[] | TelemetryRow[][],
  metadata?: Record<string, TelemetryChannelMetadata>,
): string[] {
  const channels = new Set<string>();
  const rowSets = Array.isArray(rows[0]) ? (rows as TelemetryRow[][]) : [rows as TelemetryRow[]];
  Object.keys(metadata || {}).forEach((key) => channels.add(key));
  rowSets.forEach((rowSet) => {
    rowSet.forEach((row) => Object.keys(row).forEach((key) => channels.add(key)));
  });
  return Array.from(channels).sort((a, b) => fallbackChannelLabel(a).localeCompare(fallbackChannelLabel(b)));
}

export function telemetryOpsGroupForChannel(
  channel: string,
  metadata?: Record<string, TelemetryChannelMetadata>,
): TelemetryOpsGroup {
  const meta = metadataFor(metadata, channel);
  const rawGroup = normalized(meta?.group);
  if (rawGroup) {
    if (isTelemetryOpsGroup(meta?.group || "")) {
      return meta?.group as TelemetryOpsGroup;
    }
    const alias = GROUP_ALIASES[rawGroup];
    if (alias) {
      return alias;
    }
  }

  if (meta?.role === "sensor" || meta?.source === "sensors") return "Sensors";
  if (meta?.role === "command" || meta?.role === "actuator_state" || meta?.source === "controls") return "Controls/Actuators";
  if (meta?.role === "environment") return "Environment";
  if (meta?.role === "aero") return "Aerodynamics";
  if (meta?.role === "gnc") return "GNC State";
  if (meta?.role === "propulsion") return "Propulsion";
  if (meta?.role === "derived" || meta?.source === "derived" || meta?.derived) return "Derived Performance";

  const key = normalized(channel);
  if (/(fault|alarm|warn|caution|critical|fail)/.test(key)) return "Faults/Alarms";
  if (/(event|phase|mode|status)/.test(key)) return "Events";
  if (/(target|interceptor|intercept|miss|range|los|closing|engagement)/.test(key)) return "Engagement";
  if (/(gps|imu|radar|baro|pitot|sensor|measured)/.test(key)) return "Sensors";
  if (/(cmd|command|servo|throttle|gimbal|fin|actuator|control)/.test(key)) return "Controls/Actuators";
  if (/(thrust|engine|motor|propellant|fuel|isp)/.test(key)) return "Propulsion";
  if (/(alpha|beta|qbar|drag|lift|mach|aero)/.test(key)) return "Aerodynamics";
  if (/(wind|density|pressure|temperature|gravity|atmos|environment)/.test(key)) return "Environment";
  if (/(guidance|nav|attitude|roll|pitch|yaw|quat|rate|omega)/.test(key)) return "GNC State";
  if (/(energy|efficiency|margin|error|score|derived|performance)/.test(key)) return "Derived Performance";
  return "Vehicle State";
}

export function describeTelemetryChannel(
  channel: string,
  metadata?: Record<string, TelemetryChannelMetadata>,
): TelemetryChannelDescriptor {
  const meta = metadataFor(metadata, channel);
  return {
    key: channel,
    label: channelLabel(metadata, channel),
    unit: channelUnit(metadata, channel),
    description: meta?.description || "",
    group: telemetryOpsGroupForChannel(channel, metadata),
    rawGroup: meta?.group || "",
    source: meta?.source || "",
    role: meta?.role || "",
    derived: Boolean(meta?.derived || meta?.role === "derived" || meta?.source === "derived"),
    metadata: meta,
  };
}

export function describeTelemetryChannels(
  channels: string[],
  metadata?: Record<string, TelemetryChannelMetadata>,
): TelemetryChannelDescriptor[] {
  return channels.map((channel) => describeTelemetryChannel(channel, metadata));
}

export function groupTelemetryChannels(
  channels: string[],
  metadata?: Record<string, TelemetryChannelMetadata>,
): Record<TelemetryOpsGroup, TelemetryChannelDescriptor[]> {
  const grouped = TELEMETRY_OPS_GROUPS.reduce(
    (acc, group) => ({ ...acc, [group]: [] }),
    {} as Record<TelemetryOpsGroup, TelemetryChannelDescriptor[]>,
  );
  describeTelemetryChannels(channels, metadata).forEach((descriptor) => {
    grouped[descriptor.group].push(descriptor);
  });
  TELEMETRY_OPS_GROUPS.forEach((group) => {
    grouped[group].sort((a, b) => a.label.localeCompare(b.label));
  });
  return grouped;
}

export function filterTelemetryChannels(
  channels: string[],
  metadata?: Record<string, TelemetryChannelMetadata>,
  filter: TelemetryChannelFilter = {},
): TelemetryChannelDescriptor[] {
  const query = normalized(filter.query);
  const groups = new Set(filter.groups || []);
  const sources = new Set(filter.sources || []);
  const roles = new Set(filter.roles || []);
  return describeTelemetryChannels(channels, metadata).filter((descriptor) => {
    if (groups.size > 0 && !groups.has(descriptor.group)) return false;
    if (sources.size > 0 && (!descriptor.source || !sources.has(descriptor.source))) return false;
    if (roles.size > 0 && (!descriptor.role || !roles.has(descriptor.role))) return false;
    if (!query) return true;
    const haystack = [
      descriptor.key,
      descriptor.label,
      descriptor.unit,
      descriptor.description,
      descriptor.group,
      descriptor.rawGroup,
      descriptor.role,
      descriptor.source,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

export function numericStatsForChannel(
  rows: TelemetryRow[],
  channel: string,
  currentIndex = rows.length - 1,
): TelemetryNumericStats {
  let min: number | null = null;
  let max: number | null = null;
  let latest: number | null = null;
  let latestIndex = -1;
  let count = 0;

  rows.forEach((row, index) => {
    const value = asFiniteNumber(row[channel]);
    if (value === null) return;
    count += 1;
    min = min === null ? value : Math.min(min, value);
    max = max === null ? value : Math.max(max, value);
    latest = value;
    latestIndex = index;
  });

  const boundedIndex = rows.length > 0 ? Math.max(0, Math.min(currentIndex, rows.length - 1)) : -1;
  const current = boundedIndex >= 0 ? asFiniteNumber(rows[boundedIndex]?.[channel]) : null;

  return {
    channel,
    current,
    min,
    max,
    latest,
    count,
    currentIndex: boundedIndex,
    latestIndex,
  };
}

export function buildCurrentValueTable(
  rows: TelemetryRow[],
  channels: string[],
  metadata?: Record<string, TelemetryChannelMetadata>,
  currentIndex = rows.length - 1,
  pinnedChannels = listPinnedTelemetryChannels(),
): CurrentValueRow[] {
  const pinned = new Set(pinnedChannels);
  const boundedIndex = rows.length > 0 ? Math.max(0, Math.min(currentIndex, rows.length - 1)) : -1;
  const row = boundedIndex >= 0 ? rows[boundedIndex] : undefined;
  const visibleChannels = Array.from(new Set([...pinnedChannels, ...channels]));
  return visibleChannels.map((channel) => {
    const descriptor = describeTelemetryChannel(channel, metadata);
    return {
      ...descriptor,
      value: row?.[channel],
      formattedValue: formatTelemetryValue(row, channel, metadata),
      numeric: numericStatsForChannel(rows, channel, boundedIndex),
      pinned: pinned.has(channel),
    };
  });
}

function csvEscape(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  const text = String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function telemetryRowsToCsv(
  rowSets: TelemetryRow[] | TelemetryRow[][] | TelemetryCsvRowSet[],
  channels: string[],
  options: TelemetryCsvOptions = {},
): string {
  const normalizedSets: TelemetryCsvRowSet[] =
    Array.isArray(rowSets[0])
      ? (rowSets as TelemetryRow[][]).map((rows, index) => ({ id: `set-${index + 1}`, rows }))
      : isCsvRowSet(rowSets[0])
        ? (rowSets as TelemetryCsvRowSet[])
        : [{ rows: rowSets as TelemetryRow[] }];
  const includeRunId = options.includeRunId ?? normalizedSets.some((set) => Boolean(set.id));
  const includeRowIndex = options.includeRowIndex ?? true;
  const header = [
    ...(includeRunId ? ["run_id"] : []),
    ...(includeRowIndex ? ["row_index"] : []),
    ...(options.includeSourceColumns ? ["row_set_index"] : []),
    ...channels,
  ];
  const lines = [header.map(csvEscape).join(",")];

  normalizedSets.forEach((set, setIndex) => {
    set.rows.forEach((row, rowIndex) => {
      const cells = [
        ...(includeRunId ? [set.id || ""] : []),
        ...(includeRowIndex ? [rowIndex] : []),
        ...(options.includeSourceColumns ? [setIndex] : []),
        ...channels.map((channel) => row[channel]),
      ];
      lines.push(cells.map(csvEscape).join(","));
    });
  });

  return lines.join("\n");
}

function isCsvRowSet(value: unknown): value is TelemetryCsvRowSet {
  return Boolean(value && typeof value === "object" && Array.isArray((value as TelemetryCsvRowSet).rows));
}

export function downloadTelemetryCsv(filename: string, csv: string): boolean {
  if (typeof document === "undefined" || typeof Blob === "undefined" || typeof URL === "undefined") {
    return false;
  }
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
  return true;
}

function readLayouts(): TelemetryChartLayout[] {
  const parsed = safeJsonParse<unknown>(browserStorage()?.getItem(LAYOUTS_STORAGE_KEY) || null, []);
  if (!Array.isArray(parsed)) {
    return [];
  }
  return parsed.filter(isChartLayout);
}

function isChartLayout(value: unknown): value is TelemetryChartLayout {
  if (!value || typeof value !== "object") {
    return false;
  }
  const layout = value as Partial<TelemetryChartLayout>;
  return typeof layout.id === "string" && typeof layout.name === "string" && Array.isArray(layout.channels);
}

export function listTelemetryChartLayouts(): TelemetryChartLayout[] {
  return readLayouts().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function loadTelemetryChartLayout(id: string): TelemetryChartLayout | null {
  return readLayouts().find((layout) => layout.id === id) || null;
}

export function saveTelemetryChartLayout(layout: Omit<Partial<TelemetryChartLayout>, "createdAt" | "updatedAt"> & { name: string; channels: string[] }): TelemetryChartLayout {
  const storage = browserStorage();
  const existing = readLayouts();
  const now = new Date().toISOString();
  const previous = layout.id ? existing.find((item) => item.id === layout.id) : undefined;
  const saved: TelemetryChartLayout = {
    id: layout.id || `layout-${now}-${Math.random().toString(36).slice(2, 8)}`,
    name: layout.name,
    channels: Array.from(new Set(layout.channels)),
    createdAt: previous?.createdAt || now,
    updatedAt: now,
    config: layout.config,
  };
  const next = [saved, ...existing.filter((item) => item.id !== saved.id)];
  storage?.setItem(LAYOUTS_STORAGE_KEY, JSON.stringify(next));
  return saved;
}

export function deleteTelemetryChartLayout(id: string): boolean {
  const storage = browserStorage();
  const existing = readLayouts();
  const next = existing.filter((layout) => layout.id !== id);
  storage?.setItem(LAYOUTS_STORAGE_KEY, JSON.stringify(next));
  return next.length !== existing.length;
}

function readPinnedChannels(): string[] {
  const parsed = safeJsonParse<unknown>(browserStorage()?.getItem(PINNED_CHANNELS_STORAGE_KEY) || null, []);
  return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
}

export function listPinnedTelemetryChannels(): string[] {
  return readPinnedChannels();
}

export function isTelemetryChannelPinned(channel: string): boolean {
  return readPinnedChannels().includes(channel);
}

export function togglePinnedTelemetryChannel(channel: string): string[] {
  const storage = browserStorage();
  const pinned = new Set(readPinnedChannels());
  if (pinned.has(channel)) {
    pinned.delete(channel);
  } else {
    pinned.add(channel);
  }
  const next = Array.from(pinned).sort();
  storage?.setItem(PINNED_CHANNELS_STORAGE_KEY, JSON.stringify(next));
  return next;
}

function channelTokens(channel: string): Set<string> {
  return new Set(
    normalized(channel)
      .split(/[^a-z0-9]+/)
      .filter((token) => token.length > 0),
  );
}

function canonicalChannelTerms(channel: string): Set<string> {
  const key = normalized(channel);
  const terms = channelTokens(channel);
  if (/(altitude|alt|z|height)/.test(key)) terms.add("altitude");
  if (/(speed|airspeed|velocity|vel|mps)/.test(key)) terms.add("speed");
  if (/(^|_)x($|_)/.test(key)) terms.add("x");
  if (/(^|_)y($|_)/.test(key)) terms.add("y");
  if (/(^|_)z($|_)/.test(key)) terms.add("z");
  if (/(gps|gnss)/.test(key)) terms.add("gps");
  if (/radar/.test(key)) terms.add("radar");
  if (/baro/.test(key)) terms.add("baro");
  if (/pitot/.test(key)) terms.add("pitot");
  return terms;
}

export function suggestRelatedTelemetryChannels(
  channel: string,
  channels: string[],
  metadata?: Record<string, TelemetryChannelMetadata>,
  limit = 8,
): RelatedChannelSuggestion[] {
  const baseMeta = metadataFor(metadata, channel);
  const baseTerms = canonicalChannelTerms(channel);
  const suggestions: RelatedChannelSuggestion[] = [];

  channels.forEach((candidate) => {
    if (candidate === channel) return;
    const candidateMeta = metadataFor(metadata, candidate);
    const candidateTerms = canonicalChannelTerms(candidate);
    const reasons: string[] = [];
    let score = 0;

    baseTerms.forEach((term) => {
      if (candidateTerms.has(term)) {
        score += ["altitude", "speed", "x", "y", "z"].includes(term) ? 3 : 1;
        reasons.push(`shared ${term}`);
      }
    });

    if (baseMeta?.role && candidateMeta?.role && baseMeta.role !== candidateMeta.role) {
      score += 2;
      reasons.push(`${baseMeta.role} vs ${candidateMeta.role}`);
    }
    if (baseMeta?.source && candidateMeta?.source && baseMeta.source !== candidateMeta.source) {
      score += 2;
      reasons.push(`${baseMeta.source} vs ${candidateMeta.source}`);
    }
    if (/altitude_m$/.test(channel) && /(gps_z_m|radar_altitude_m|baro_altitude_m)/.test(candidate)) {
      score += 5;
      reasons.push("altitude sensor pairing");
    }
    if (/speed_mps$/.test(channel) && /pitot_airspeed_mps/.test(candidate)) {
      score += 5;
      reasons.push("airspeed sensor pairing");
    }
    if (/(gps_[xyz]_m|gps)/.test(candidate) && /(^|_)[xyz](_|$)/.test(channel)) {
      score += 3;
      reasons.push("position/GPS pairing");
    }
    if (score > 0) {
      suggestions.push({
        channel: candidate,
        label: channelLabel(metadata, candidate),
        score,
        reasons: Array.from(new Set(reasons)),
        metadata: candidateMeta,
      });
    }
  });

  return suggestions.sort((a, b) => b.score - a.score || a.label.localeCompare(b.label)).slice(0, limit);
}

export function findNearestTelemetryRowByTime(
  rows: TelemetryRow[],
  targetTime: number,
  timeKeys: string[] = ["time_s", "t_s", "time", "timestamp_s"],
): NearestTelemetryRow {
  let best: NearestTelemetryRow = { row: null, index: -1, time: null, delta: null };
  rows.forEach((row, index) => {
    const key = timeKeys.find((candidate) => asFiniteNumber(row[candidate]) !== null);
    if (!key) return;
    const time = asFiniteNumber(row[key]);
    if (time === null) return;
    const delta = Math.abs(time - targetTime);
    if (best.delta === null || delta < best.delta) {
      best = { row, index, time, delta };
    }
  });
  return best;
}

export { LAYOUTS_STORAGE_KEY as TELEMETRY_OPS_LAYOUTS_STORAGE_KEY, PINNED_CHANNELS_STORAGE_KEY as TELEMETRY_OPS_PINNED_CHANNELS_STORAGE_KEY };
