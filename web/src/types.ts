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
  advisory_summary?: {
    counts_by_severity?: Record<string, number>;
    blocking_count?: number;
    error_count?: number;
    warning_count?: number;
    info_count?: number;
    highest_severity?: string;
    suggested_next_actions?: string[];
    [key: string]: unknown;
  };
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
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
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
  role: "truth" | "sensor" | "command" | "actuator_state" | "environment" | "aero" | "gnc" | "propulsion" | "derived" | "estimate";
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

export type MissileMetric = {
  value: number | null;
  time_s?: number | null;
  source?: string;
};

export type MissileTimelineSample = {
  time_s: number | null;
  locked?: boolean;
  status?: string;
  seeker_locked?: boolean;
  seeker_status?: string;
  range_m?: number | null;
  range_rate_mps?: number | null;
  closing_speed_mps?: number | null;
  phase?: string;
  motor_phase?: string;
  thrust_n?: number | null;
  motor_thrust_n?: number | null;
  spool_fraction?: number | null;
  motor_spool_fraction?: number | null;
  lateral_accel_mps2?: number | null;
  saturated?: boolean;
  control_saturated?: boolean;
  armed?: boolean;
  fuze_armed?: boolean;
  fuzed?: boolean;
  fuze_fuzed?: boolean;
  closest_range_m?: number | null;
  fuze_status?: string;
  fuze_closest_range_m?: number | null;
  miss_distance_m?: number | null;
};

export type MissilePhaseInterval = {
  value?: string;
  phase?: string;
  start_time_s: number | null;
  end_time_s?: number | null;
};

export type MissileClosestApproachEvent = {
  time_s: number | null;
  type: string;
  target_id?: string;
  interceptor_id?: string;
  miss_distance_m?: number | null;
  description?: string;
};

export type MissileEngagementRun = {
  id: string;
  scenario: string;
  run_dir: string;
  available: boolean;
  sample_count: number;
  summary: {
    miss_distance_m?: MissileMetric;
    closest_approach_time_s?: number | null;
    first_seeker_lock_time_s?: number | null;
    seeker_lock_fraction?: number | null;
    first_fuze_time_s?: number | null;
    max_lateral_accel_mps2?: number | null;
    max_closing_speed_mps?: number | null;
    actuator_saturation_count?: number;
    actuator_saturation_fraction?: number | null;
    motor_phases?: string[];
    fuze_states?: string[];
    interceptor_id?: string | null;
    target_id?: string | null;
    [key: string]: unknown;
  };
  seeker_lock: {
    ever_locked: boolean;
    first_lock_time_s: number | null;
    lock_fraction?: number | null;
    locked_sample_count?: number;
    timeline: MissileTimelineSample[];
  };
  range: {
    min_range_m?: number | null;
    timeline: MissileTimelineSample[];
  };
  motor: {
    phase_sequence: MissilePhaseInterval[];
    phase_intervals?: MissilePhaseInterval[];
    timeline: MissileTimelineSample[];
  };
  lateral_acceleration: {
    max_abs_mps2: number | null;
    timeline: MissileTimelineSample[];
  };
  actuator_saturation: {
    count: number;
    fraction?: number | null;
    first_time_s: number | null;
    events: Array<Record<string, unknown>>;
    timeline: MissileTimelineSample[];
  };
  fuze: {
    first_armed_time_s: number | null;
    first_fuzed_time_s: number | null;
    state_intervals?: MissilePhaseInterval[];
    timeline: MissileTimelineSample[];
  };
  miss_distance: MissileMetric;
  closest_approach_timeline: {
    event: MissileClosestApproachEvent | null;
    samples: MissileTimelineSample[];
  };
};

export type MissileEngagementComparisonRow = {
  id: string;
  scenario: string;
  miss_distance_m: number | null;
  closest_approach_time_s: number | null;
  first_seeker_lock_time_s: number | null;
  seeker_lock_fraction?: number | null;
  first_fuze_time_s: number | null;
  max_lateral_accel_mps2: number | null;
  max_closing_speed_mps?: number | null;
  actuator_saturation_count: number;
  actuator_saturation_fraction?: number | null;
  motor_phases: string[];
  fuze_states: string[];
};

export type MissileEngagementComparisonPacket = {
  schema: string;
  run_count: number;
  runs: MissileEngagementRun[];
  comparison_table: MissileEngagementComparisonRow[];
  timeline_channels: string[];
};

export type NavigationTelemetryChannel = {
  key: string;
  label: string;
  unit: string;
};

export type NavigationTelemetry = {
  run_id: string;
  rows: TelemetryRow[];
  channels: NavigationTelemetryChannel[];
  summary: Record<string, unknown>;
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
