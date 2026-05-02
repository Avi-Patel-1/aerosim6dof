import type { AlarmSummary } from "./types";

export const REPORT_STUDIO_SCHEMA = "aerosim6dof.report_studio.packet.v1";
export const REPORT_STUDIO_REQUEST_SCHEMA = "aerosim6dof.report_studio.request.v1";

export type ReportStudioSectionId = "summary" | "events" | "alarms" | "telemetry" | "engagement" | "artifacts";
export type ReportStudioExportFormat = "json" | "markdown" | "html";

export type ReportStudioSectionDefinition = {
  id: ReportStudioSectionId;
  label: string;
  payloadKey: keyof ReportStudioPacket;
  description: string;
};

export type ReportStudioMetric = {
  key: string;
  label: string;
  value: unknown;
  unit: string;
  source: string;
};

export type ReportStudioSummarySection = {
  available: boolean;
  source: string | null;
  data: Record<string, unknown>;
  scenario_summary?: Record<string, unknown>;
  highlights: ReportStudioMetric[];
};

export type ReportStudioEvent = {
  index: number;
  time_s: number | null;
  type: string;
  description: string;
  severity: string | null;
  details: Record<string, unknown>;
};

export type ReportStudioEventsSection = {
  available: boolean;
  source: string | null;
  count: number;
  truncated: boolean;
  items: ReportStudioEvent[];
};

export type ReportStudioAlarmSection = {
  available: boolean;
  source: string;
  count: number;
  active_count: number;
  counts_by_severity: Record<string, number>;
  items: Array<Partial<AlarmSummary> & Record<string, unknown>>;
};

export type ReportStudioTelemetrySample = {
  time_s: number | null;
  value: number;
};

export type ReportStudioTelemetryHighlight = {
  id: string;
  source: string;
  channel: string;
  label: string;
  unit: string;
  sample_count: number;
  min: ReportStudioTelemetrySample;
  max: ReportStudioTelemetrySample;
  final: ReportStudioTelemetrySample;
};

export type ReportStudioTelemetryChannelRef = {
  id: string;
  source: string;
  channel: string;
  label: string;
  unit: string;
  sample_count: number;
};

export type ReportStudioTelemetrySection = {
  available: boolean;
  sources: Array<{ source: string; path: string; sample_count: number }>;
  selected_channels?: string[];
  available_channels?: ReportStudioTelemetryChannelRef[];
  items: ReportStudioTelemetryHighlight[];
};

export type ReportStudioEngagementMetrics = {
  available: boolean;
  target_count: number;
  target_ids: string[];
  interceptor_count: number;
  interceptor_ids: string[];
  min_target_distance_m?: { value: number; source: string } | null;
  min_target_range_m?: { value: number; time_s: number | null; source: string } | null;
  min_interceptor_range_m?: { value: number; time_s: number | null; source: string } | null;
  first_interceptor_fuze_time_s?: number | null;
  closest_approach_event?: ReportStudioEvent | null;
  [key: string]: unknown;
};

export type ReportStudioArtifactRef = {
  name: string;
  kind: string;
  path: string;
  url: string | null;
  size_bytes: number;
};

export type ReportStudioPacket = {
  schema: string;
  packet_id: string;
  run_dir: string;
  generated_at_utc: string;
  selected_sections: ReportStudioSectionId[];
  source_files: Record<string, string | null>;
  summary?: ReportStudioSummarySection;
  events_timeline?: ReportStudioEventsSection;
  alarm_summaries?: ReportStudioAlarmSection;
  telemetry_highlights?: ReportStudioTelemetrySection;
  engagement_metrics?: ReportStudioEngagementMetrics;
  artifacts?: ReportStudioArtifactRef[];
};

export type ReportStudioSectionDescription = {
  id: ReportStudioSectionId;
  label: string;
  description: string;
  payloadKey: keyof ReportStudioPacket;
  included: boolean;
  available: boolean;
  itemCount: number;
  summary: string;
};

export type ReportStudioExportOptions = {
  include_artifact_refs: boolean;
  include_source_data: boolean;
  max_events: number | null;
  artifact_base_url: string | null;
};

export type ReportStudioExportRequest = {
  kind: "report_studio_packet_export";
  schema: typeof REPORT_STUDIO_REQUEST_SCHEMA;
  run_id: string | null;
  run_dir: string | null;
  packet_id: string | null;
  format: ReportStudioExportFormat;
  sections: ReportStudioSectionId[];
  telemetry_channels: string[];
  options: ReportStudioExportOptions;
};

export type ReportStudioReadySummary = {
  title: string;
  subtitle: string;
  section_count: number;
  available_section_count: number;
  telemetry_channel_count: number;
  artifact_count: number;
  event_count: number;
  alarm_count: number;
  ready: boolean;
};

export type ReportStudioExportPayload = {
  kind: "report_studio_packet";
  schema: string;
  packet_id: string;
  run_dir: string;
  generated_at_utc: string;
  export_format: ReportStudioExportFormat;
  report_summary: ReportStudioReadySummary;
  telemetry_channels: string[];
  sections: Record<string, unknown>;
  section_descriptions: ReportStudioSectionDescription[];
};

export const REPORT_STUDIO_SECTION_DEFINITIONS: ReportStudioSectionDefinition[] = [
  {
    id: "summary",
    label: "Mission Summary",
    payloadKey: "summary",
    description: "Scenario identity, outcome metrics, and final state."
  },
  {
    id: "events",
    label: "Events Timeline",
    payloadKey: "events_timeline",
    description: "Chronological event markers from the run log."
  },
  {
    id: "alarms",
    label: "Alarm Summary",
    payloadKey: "alarm_summaries",
    description: "Derived alarm state, severity counts, and lifecycle timing."
  },
  {
    id: "telemetry",
    label: "Telemetry Highlights",
    payloadKey: "telemetry_highlights",
    description: "Min, max, and final values for mission-critical channels."
  },
  {
    id: "engagement",
    label: "Engagement Metrics",
    payloadKey: "engagement_metrics",
    description: "Target, interceptor, closest-approach, and fuze metrics."
  },
  {
    id: "artifacts",
    label: "Artifact Refs",
    payloadKey: "artifacts",
    description: "Report, plot, CSV, and JSON artifact references."
  }
];

export const DEFAULT_REPORT_STUDIO_SECTIONS: ReportStudioSectionId[] = REPORT_STUDIO_SECTION_DEFINITIONS.map(
  (section) => section.id
);

const SECTION_BY_ID = REPORT_STUDIO_SECTION_DEFINITIONS.reduce(
  (lookup, section) => ({ ...lookup, [section.id]: section }),
  {} as Record<ReportStudioSectionId, ReportStudioSectionDefinition>
);

const DEFAULT_EXPORT_OPTIONS: ReportStudioExportOptions = {
  include_artifact_refs: true,
  include_source_data: false,
  max_events: null,
  artifact_base_url: null
};

export function isReportStudioSectionId(value: unknown): value is ReportStudioSectionId {
  return typeof value === "string" && value in SECTION_BY_ID;
}

export function isReportStudioExportFormat(value: unknown): value is ReportStudioExportFormat {
  return value === "json" || value === "markdown" || value === "html";
}

export function normalizeReportStudioSections(
  sections?: readonly unknown[] | null,
  fallback: readonly ReportStudioSectionId[] = DEFAULT_REPORT_STUDIO_SECTIONS
): ReportStudioSectionId[] {
  const normalized: ReportStudioSectionId[] = [];
  (sections ?? []).forEach((section) => {
    if (isReportStudioSectionId(section) && !normalized.includes(section)) {
      normalized.push(section);
    }
  });
  return normalized.length ? normalized : [...fallback];
}

export function defaultReportStudioSections(packet?: ReportStudioPacket | null): ReportStudioSectionId[] {
  return normalizeReportStudioSections(packet?.selected_sections, DEFAULT_REPORT_STUDIO_SECTIONS);
}

export function availableReportStudioTelemetryChannels(packet?: ReportStudioPacket | null): ReportStudioTelemetryChannelRef[] {
  const telemetry = packet?.telemetry_highlights;
  if (!telemetry) {
    return [];
  }
  if (Array.isArray(telemetry.available_channels) && telemetry.available_channels.length) {
    return telemetry.available_channels;
  }
  return telemetry.items.map((item) => ({
    id: item.id,
    source: item.source,
    channel: item.channel,
    label: item.label,
    unit: item.unit,
    sample_count: item.sample_count
  }));
}

export function defaultReportStudioTelemetryChannels(packet?: ReportStudioPacket | null): string[] {
  const selected = packet?.telemetry_highlights?.selected_channels;
  if (Array.isArray(selected) && selected.length) {
    return normalizeReportStudioTelemetryChannels(selected, packet);
  }
  return availableReportStudioTelemetryChannels(packet)
    .filter((channel) => packet?.telemetry_highlights?.items.some((item) => item.id === channel.id))
    .map((channel) => channel.id);
}

export function normalizeReportStudioTelemetryChannels(
  channels?: readonly unknown[] | null,
  packet?: ReportStudioPacket | null
): string[] {
  const available = availableReportStudioTelemetryChannels(packet);
  const allowed = new Set(available.map((channel) => channel.id));
  const normalized: string[] = [];
  (channels ?? []).forEach((channel) => {
    if (typeof channel !== "string") {
      return;
    }
    const value = channel.trim();
    if (!value || value.includes("/") || value.includes("\\") || value.includes("..")) {
      return;
    }
    if ((allowed.size === 0 || allowed.has(value)) && !normalized.includes(value)) {
      normalized.push(value);
    }
  });
  if (normalized.length) {
    return normalized;
  }
  return available.filter((channel) => packet?.telemetry_highlights?.items.some((item) => item.id === channel.id)).map((channel) => channel.id);
}

export function packetPayloadForSection(packet: ReportStudioPacket | null | undefined, section: ReportStudioSectionId): unknown {
  if (!packet) {
    return undefined;
  }
  return packet[SECTION_BY_ID[section].payloadKey];
}

export function describeReportStudioSections(
  packet: ReportStudioPacket | null | undefined,
  selectedSections?: readonly unknown[] | null
): ReportStudioSectionDescription[] {
  const selected = new Set(normalizeReportStudioSections(selectedSections ?? packet?.selected_sections));
  return REPORT_STUDIO_SECTION_DEFINITIONS.map((definition) => {
    const payload = packetPayloadForSection(packet, definition.id);
    return {
      id: definition.id,
      label: definition.label,
      description: definition.description,
      payloadKey: definition.payloadKey,
      included: selected.has(definition.id),
      available: sectionAvailable(payload),
      itemCount: sectionItemCount(definition.id, payload),
      summary: sectionSummary(definition.id, payload)
    };
  });
}

export function describeSelectedPacketSections(
  packet: ReportStudioPacket | null | undefined,
  selectedSections?: readonly unknown[] | null
): ReportStudioSectionDescription[] {
  return describeReportStudioSections(packet, selectedSections).filter((section) => section.included);
}

export function buildReportStudioExportRequest(input: {
  runId?: string | null;
  runDir?: string | null;
  packet?: ReportStudioPacket | null;
  sections?: readonly unknown[] | null;
  telemetryChannels?: readonly unknown[] | null;
  format?: unknown;
  options?: Partial<ReportStudioExportOptions>;
}): ReportStudioExportRequest {
  const sections = normalizeReportStudioSections(input.sections ?? input.packet?.selected_sections);
  return {
    kind: "report_studio_packet_export",
    schema: REPORT_STUDIO_REQUEST_SCHEMA,
    run_id: input.runId ?? input.packet?.packet_id ?? null,
    run_dir: input.runDir ?? input.packet?.run_dir ?? null,
    packet_id: input.packet?.packet_id ?? null,
    format: isReportStudioExportFormat(input.format) ? input.format : "json",
    sections,
    telemetry_channels: sections.includes("telemetry")
      ? normalizeReportStudioTelemetryChannels(input.telemetryChannels ?? input.packet?.telemetry_highlights?.selected_channels, input.packet)
      : [],
    options: { ...DEFAULT_EXPORT_OPTIONS, ...(input.options ?? {}) }
  };
}

export function buildReportStudioExportPayload(
  packet: ReportStudioPacket,
  request: Partial<ReportStudioExportRequest> = {}
): ReportStudioExportPayload {
  const format = isReportStudioExportFormat(request.format) ? request.format : "json";
  const selected = normalizeReportStudioSections(request.sections ?? packet.selected_sections);
  const selectedTelemetryChannels = selected.includes("telemetry")
    ? normalizeReportStudioTelemetryChannels(request.telemetry_channels, packet)
    : [];
  const sections = selected.reduce<Record<string, unknown>>((payload, section) => {
    if (section === "artifacts" && request.options?.include_artifact_refs === false) {
      return payload;
    }
    const definition = SECTION_BY_ID[section];
    const sectionPayload = packet[definition.payloadKey];
    payload[definition.payloadKey] =
      section === "telemetry" ? filterTelemetrySection(sectionPayload, selectedTelemetryChannels) : sectionPayload;
    return payload;
  }, {});

  return {
    kind: "report_studio_packet",
    schema: packet.schema || REPORT_STUDIO_SCHEMA,
    packet_id: packet.packet_id,
    run_dir: packet.run_dir,
    generated_at_utc: packet.generated_at_utc,
    export_format: format,
    report_summary: buildReportStudioReportSummary(packet, selected, selectedTelemetryChannels),
    telemetry_channels: selectedTelemetryChannels,
    sections,
    section_descriptions: describeSelectedPacketSections(packet, selected)
  };
}

export function buildReportStudioReportSummary(
  packet: ReportStudioPacket | null | undefined,
  selectedSections?: readonly unknown[] | null,
  selectedTelemetryChannels?: readonly unknown[] | null
): ReportStudioReadySummary {
  const sections = normalizeReportStudioSections(selectedSections ?? packet?.selected_sections);
  const descriptions = describeReportStudioSections(packet, sections).filter((section) => section.included);
  const scenarioSummary = packet?.summary?.scenario_summary;
  const scenarioName = isRecord(scenarioSummary) && typeof scenarioSummary.name === "string" ? scenarioSummary.name : null;
  const summaryScenario = typeof packet?.summary?.data.scenario === "string" ? packet.summary.data.scenario : null;
  const title = scenarioName || summaryScenario || packet?.packet_id || "No packet loaded";
  const duration = formatNumber(asNumber(packet?.summary?.data.duration_s), "s");
  const subtitle = packet ? `${packet.packet_id}${duration === "-" ? "" : `, ${duration}`}` : "Load a run packet to build an export";
  const telemetryChannels = normalizeReportStudioTelemetryChannels(selectedTelemetryChannels ?? packet?.telemetry_highlights?.selected_channels, packet);
  return {
    title,
    subtitle,
    section_count: descriptions.length,
    available_section_count: descriptions.filter((section) => section.available).length,
    telemetry_channel_count: sections.includes("telemetry") ? telemetryChannels.length : 0,
    artifact_count: Array.isArray(packet?.artifacts) ? packet.artifacts.length : 0,
    event_count: asNumber(packet?.events_timeline?.count) ?? 0,
    alarm_count: asNumber(packet?.alarm_summaries?.count) ?? 0,
    ready: Boolean(packet && descriptions.length > 0)
  };
}

function filterTelemetrySection(payload: unknown, selectedTelemetryChannels: string[]): unknown {
  if (!isRecord(payload) || !Array.isArray(payload.items)) {
    return payload;
  }
  const selected = new Set(selectedTelemetryChannels);
  return {
    ...payload,
    selected_channels: selectedTelemetryChannels,
    items: payload.items.filter((item) => isRecord(item) && typeof item.id === "string" && selected.has(item.id))
  };
}

function sectionAvailable(payload: unknown): boolean {
  if (Array.isArray(payload)) {
    return payload.length > 0;
  }
  if (isRecord(payload)) {
    if (typeof payload.available === "boolean") {
      return payload.available;
    }
    return Object.keys(payload).length > 0;
  }
  return payload !== undefined && payload !== null;
}

function sectionItemCount(section: ReportStudioSectionId, payload: unknown): number {
  if (!payload) {
    return 0;
  }
  if (section === "artifacts" && Array.isArray(payload)) {
    return payload.length;
  }
  if (!isRecord(payload)) {
    return 0;
  }
  if (section === "summary" && isRecord(payload.data)) {
    return Object.keys(payload.data).length;
  }
  if ((section === "events" || section === "alarms" || section === "telemetry") && Array.isArray(payload.items)) {
    return payload.items.length;
  }
  if (section === "engagement") {
    const targetCount = asNumber(payload.target_count) ?? 0;
    const interceptorCount = asNumber(payload.interceptor_count) ?? 0;
    return targetCount + interceptorCount;
  }
  return 0;
}

function sectionSummary(section: ReportStudioSectionId, payload: unknown): string {
  if (!payload) {
    return "Unavailable";
  }
  if (section === "summary" && isRecord(payload) && isRecord(payload.data)) {
    const scenario = typeof payload.data.scenario === "string" ? payload.data.scenario : "Run";
    const duration = formatNumber(asNumber(payload.data.duration_s), "s");
    return duration === "-" ? scenario : `${scenario}, ${duration}`;
  }
  if (section === "events" && isRecord(payload)) {
    return `${asNumber(payload.count) ?? sectionItemCount(section, payload)} events`;
  }
  if (section === "alarms" && isRecord(payload)) {
    return `${asNumber(payload.active_count) ?? 0} active / ${asNumber(payload.count) ?? sectionItemCount(section, payload)} total`;
  }
  if (section === "telemetry") {
    return `${sectionItemCount(section, payload)} channel highlights`;
  }
  if (section === "engagement" && isRecord(payload)) {
    const targetRange = metricText(payload.min_target_range_m, "m");
    return targetRange === "-" ? `${sectionItemCount(section, payload)} tracked objects` : `Best target range ${targetRange}`;
  }
  if (section === "artifacts") {
    return `${sectionItemCount(section, payload)} artifacts`;
  }
  return "Available";
}

function metricText(value: unknown, unit: string): string {
  if (!isRecord(value)) {
    return "-";
  }
  return formatNumber(asNumber(value.value), unit);
}

function formatNumber(value: number | null, unit = ""): string {
  if (value === null) {
    return "-";
  }
  const abs = Math.abs(value);
  const digits = abs >= 1000 ? 0 : abs >= 100 ? 1 : abs >= 10 ? 2 : 3;
  return `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
