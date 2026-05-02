export type ArtifactRef = {
  name: string;
  kind: string;
  path: string;
  url: string;
  size_bytes: number;
};

export type ScenarioSummary = {
  id: string;
  name: string;
  path: string;
  duration_s: number;
  dt_s: number;
  integrator: string;
  vehicle_config: string | null;
  environment_config: string | null;
  guidance_mode: string | null;
};

export type ScenarioDetail = ScenarioSummary & {
  raw: Record<string, unknown>;
  resolved: Record<string, unknown>;
};

export type ScenarioDraft = {
  id: string;
  name: string;
  path: string;
  valid: boolean;
  errors: string[];
  scenario: Record<string, unknown>;
};

export type ScenarioBuilderWarning = {
  severity: "info" | "caution" | "warning" | "critical" | string;
  section: string;
  path: string;
  message: string;
};

export type ScenarioAdvisory = {
  code: string;
  severity: "info" | "warning" | "error" | "caution" | "critical" | string;
  path: string;
  message: string;
  suggestion?: string | null;
  resolved_reference?: string | null;
};

export type ScenarioValidation = {
  valid: boolean;
  errors?: string[];
  scenario?: string;
  dt?: number;
  duration?: number;
  integrator?: string;
  summary?: Record<string, unknown>;
  warnings?: Array<string | ScenarioBuilderWarning>;
  advisories?: ScenarioAdvisory[];
  explanation?: string;
  recommendations?: string[];
  [key: string]: unknown;
};

export type ConfigSummary = {
  id: string;
  name: string;
  path: string;
};

export type RunSummary = {
  id: string;
  scenario: string;
  status: "completed" | "failed" | "unknown";
  run_dir: string;
  created_at_utc: string | null;
  summary: Record<string, unknown>;
  manifest: Record<string, unknown> | null;
  events: Record<string, unknown>[];
  artifacts: ArtifactRef[];
};

export type Capability = {
  id: string;
  group: string;
  label: string;
  faults?: string[];
};

export type ActionResult = {
  action: string;
  status: "completed" | "failed";
  message: string;
  output_id: string | null;
  output_dir: string | null;
  data: Record<string, unknown>;
  artifacts: ArtifactRef[];
};

export type JobEvent = {
  time_utc: string;
  status: string;
  message: string;
  progress: number;
};

export type JobSummary = {
  id: string;
  action: string;
  status: "queued" | "running" | "completed" | "failed";
  message: string;
  progress: number;
  created_at_utc: string;
  started_at_utc: string | null;
  finished_at_utc: string | null;
  events: JobEvent[];
  result: ActionResult | null;
};

export type StorageStatus = {
  ok: boolean;
  backend: string;
  root: string;
  env_var: string;
  env_backed: boolean;
  persistent: boolean;
  writable: boolean;
  namespaces: string[];
  manifest_exists: boolean;
  error?: string | null;
  [key: string]: unknown;
};

export type TelemetryRow = Record<string, number | string | null>;

export type AlarmSeverity = "info" | "caution" | "warning" | "critical";

export type AlarmSummary = {
  id: string;
  name: string;
  severity: AlarmSeverity;
  source: string;
  subsystem: string;
  message: string;
  channel: string | null;
  threshold: string;
  rule: string;
  first_triggered_time_s: number;
  last_triggered_time_s: number;
  cleared_time_s: number | null;
  active: boolean;
  occurrence_count: number;
  sample_count: number;
};

export type TelemetryRange = {
  min: number | null;
  max: number | null;
  label: string;
};

export type TelemetryChannelMetadata = {
  key: string;
  display_name: string;
  unit: string;
  description: string;
  group: string;
  source: "history" | "truth" | "controls" | "sensors" | "derived";
  role: "truth" | "sensor" | "command" | "actuator_state" | "environment" | "aero" | "gnc" | "propulsion" | "derived";
  valid_range: TelemetryRange | null;
  caution_range: TelemetryRange | null;
  warning_range: TelemetryRange | null;
  fatal_range: TelemetryRange | null;
  sample_rate_hz: number | null;
  derived: boolean;
};

export type TelemetrySeries = {
  run_id: string;
  stride: number;
  sample_count: number;
  channels: Record<string, string[]>;
  history: TelemetryRow[];
  truth: TelemetryRow[];
  controls: TelemetryRow[];
  sensors: TelemetryRow[];
  targets: TelemetryRow[];
  interceptors: TelemetryRow[];
  metadata?: Record<string, TelemetryChannelMetadata>;
};

export type ReplayHandoff = {
  runId: string;
  run: RunSummary | null;
  telemetry: TelemetrySeries;
  index: number;
  environmentMode: "range" | "coast" | "night";
  cameraMode: "chase" | "orbit" | "cockpit" | "map" | "rangeSafety";
  playing: boolean;
};
