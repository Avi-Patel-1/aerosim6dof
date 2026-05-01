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

export type TelemetryRow = Record<string, number | string | null>;

export type TelemetrySeries = {
  run_id: string;
  stride: number;
  sample_count: number;
  channels: Record<string, string[]>;
  history: TelemetryRow[];
  truth: TelemetryRow[];
  controls: TelemetryRow[];
  sensors: TelemetryRow[];
};
