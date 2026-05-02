import {
  AlertTriangle,
  CheckCircle2,
  FileJson,
  Gauge,
  ListChecks,
  Play,
  Plus,
  Radar,
  Save,
  ShieldAlert,
  SlidersHorizontal,
  Target,
  Trash2,
  Wand2
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { normalizeScenarioDraft } from "../scenarioBuilder";
import type { ConfigSummary } from "../types";

type BuilderSection =
  | "mission"
  | "vehicle"
  | "environment"
  | "initial"
  | "gnc"
  | "sensors"
  | "faults"
  | "targets"
  | "termination"
  | "outputs"
  | "json";

type BusyAction = string | null | undefined;

type ScenarioValidation = {
  valid?: boolean;
  errors?: string[];
  warnings?: Array<string | { severity?: string; section?: string; path?: string; message?: string }>;
  [key: string]: unknown;
} | null;

type ScenarioBuilderV2Props = {
  scenarioText: string;
  onScenarioTextChange: (value: string) => void;
  vehicles: ConfigSummary[];
  environments: ConfigSummary[];
  selectedVehicle: string;
  selectedEnvironment: string;
  onSelectedVehicleChange: (value: string) => void;
  onSelectedEnvironmentChange: (value: string) => void;
  onValidate: () => void | Promise<void>;
  onSave: () => void | Promise<void>;
  onRun: () => void | Promise<void>;
  busyAction?: BusyAction;
  validation?: ScenarioValidation;
};

type Option = {
  id: string;
  name: string;
  path?: string;
};

type PresetId = "calm" | "gusty" | "terrain" | "highAltitude" | "sensorFault" | "intercept";

const SECTIONS: { id: BuilderSection; label: string }[] = [
  { id: "mission", label: "Mission Profile" },
  { id: "vehicle", label: "Vehicle" },
  { id: "environment", label: "Environment" },
  { id: "initial", label: "Initial State" },
  { id: "gnc", label: "GNC" },
  { id: "sensors", label: "Sensors" },
  { id: "faults", label: "Faults" },
  { id: "targets", label: "Targets/Interceptors" },
  { id: "termination", label: "Termination" },
  { id: "outputs", label: "Outputs" },
  { id: "json", label: "Expert JSON" }
];

const PRESETS: { id: PresetId; label: string; note: string }[] = [
  { id: "calm", label: "Calm", note: "Nominal low-wind checkout." },
  { id: "gusty", label: "Gusty", note: "Adds wind, turbulence, and qbar margin." },
  { id: "terrain", label: "Terrain", note: "Low-altitude terrain/radar profile." },
  { id: "highAltitude", label: "High-altitude", note: "Thin-air climb and long duration." },
  { id: "sensorFault", label: "Sensor-fault", note: "Dropouts, noise, and a fault timeline." },
  { id: "intercept", label: "Intercept", note: "Target plus interceptor engagement." }
];

function parseDraft(text: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function cloneDraft(text: string): Record<string, unknown> {
  return structuredClone(normalizeScenarioDraft(parseDraft(text) ?? {}));
}

function writeDraft(draft: Record<string, unknown>): string {
  return JSON.stringify(draft, null, 2);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function configId(value: unknown): string {
  const text = asString(value);
  const name = text.split("/").pop() ?? text;
  return name.replace(/\.json$/i, "");
}

function getAt(root: Record<string, unknown>, path: string[]): unknown {
  return path.reduce<unknown>((cursor, key) => asRecord(cursor)[key], root);
}

function ensureArray(root: Record<string, unknown>, path: string[]): unknown[] {
  let cursor = root;
  for (const key of path.slice(0, -1)) {
    const next = cursor[key];
    if (!next || typeof next !== "object" || Array.isArray(next)) {
      cursor[key] = {};
    }
    cursor = cursor[key] as Record<string, unknown>;
  }
  const leaf = path[path.length - 1];
  if (!Array.isArray(cursor[leaf])) {
    cursor[leaf] = [];
  }
  return cursor[leaf] as unknown[];
}

function setAt(root: Record<string, unknown>, path: string[], value: unknown): void {
  let cursor = root;
  for (const key of path.slice(0, -1)) {
    const next = cursor[key];
    if (!next || typeof next !== "object" || Array.isArray(next)) {
      cursor[key] = {};
    }
    cursor = cursor[key] as Record<string, unknown>;
  }
  cursor[path[path.length - 1]] = value;
}

function vectorNumber(value: unknown, index: number, fallback = 0): number {
  return asNumber(asArray(value)[index], fallback);
}

function setVector(root: Record<string, unknown>, path: string[], index: number, value: number): void {
  const current = asArray(getAt(root, path));
  const next = [...current];
  while (next.length <= index) {
    next.push(0);
  }
  next[index] = value;
  setAt(root, path, next);
}

function compactJson(value: unknown): string {
  return JSON.stringify(value, null, 2).slice(0, 1800);
}

function vehiclePath(id: string): string {
  return `../vehicles/${id}.json`;
}

function environmentPath(id: string): string {
  return `../environments/${id}.json`;
}

function optionLabel(options: Option[], id: string): string {
  return (options.find((option) => option.id === id)?.name ?? id) || "unselected";
}

function uniqueStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  if (typeof value === "string") {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function explainScenario(draft: Record<string, unknown>, vehicleName: string, environmentName: string): string {
  const guidance = asRecord(draft.guidance);
  const initial = asRecord(draft.initial);
  const sensors = asRecord(draft.sensors);
  const targets = asArray(draft.targets).length;
  const interceptors = asArray(draft.interceptors).length;
  const altitude = vectorNumber(initial.position_m, 2, 0);
  const speed = vectorNumber(initial.velocity_mps, 0, 0);
  const duration = asNumber(draft.duration, 0);
  const mode = asString(guidance.mode, "guidance");
  const faultCount = asArray(sensors.faults).length + asArray(draft.faults).length + asArray(asRecord(draft.events).faults).length;

  return `${asString(draft.name, "Scenario")} runs ${duration.toFixed(1)} s with ${vehicleName} in ${environmentName}, starting at ${altitude.toFixed(0)} m and ${speed.toFixed(0)} m/s. It uses ${mode}, tracks ${targets} target${targets === 1 ? "" : "s"}, launches ${interceptors} interceptor${interceptors === 1 ? "" : "s"}, and schedules ${faultCount} fault event${faultCount === 1 ? "" : "s"}.`;
}

function completionScore(draft: Record<string, unknown>, parseError: string | null): number {
  if (parseError) {
    return 0;
  }
  const checks = [
    Boolean(asString(draft.name)),
    asNumber(draft.duration) > 0,
    asNumber(draft.dt) > 0,
    Boolean(asString(draft.vehicle_config)),
    Boolean(asString(draft.environment_config)),
    asArray(asRecord(draft.initial).position_m).length >= 3,
    asArray(asRecord(draft.initial).velocity_mps).length >= 3,
    Boolean(asString(asRecord(draft.guidance).mode)),
    Object.keys(asRecord(draft.sensors)).length > 0,
    Object.keys(asRecord(draft.events)).length > 0,
    Object.keys(asRecord(draft.outputs)).length > 0 || Object.keys(asRecord(draft.logging)).length > 0
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
}

function validationIssues(validation: ScenarioValidation, parseError: string | null): string[] {
  if (parseError) {
    return [parseError];
  }
  if (!validation) {
    return [];
  }
  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
  return [
    ...errors.map(String),
    ...warnings.map((warning) => {
      if (typeof warning === "string") {
        return warning;
      }
      const path = warning.path ? `${warning.path}: ` : "";
      const severity = warning.severity ? `${warning.severity} ` : "";
      return `${severity}${path}${warning.message ?? "Scenario advisory"}`;
    })
  ];
}

function presetPatch(id: PresetId, vehicleId: string, environmentId: string): Record<string, unknown> {
  const base: Record<string, unknown> = {
    vehicle_config: vehiclePath(vehicleId || "baseline"),
    environment_config: environmentPath(environmentId || "calm"),
    integrator: "semi_implicit_euler",
    outputs: { telemetry: true, events: true, summary: true }
  };

  if (id === "calm") {
    return {
      ...base,
      name: "calm_checkout",
      duration: 24,
      dt: 0.03,
      initial: { position_m: [0, 0, 120], velocity_mps: [82, 0, 0], euler_deg: [0, 5, 0] },
      guidance: { mode: "pitch_program", throttle: 0.82, heading_command_deg: 0, pitch_program: [[0, 5], [12, 4], [24, 3]] },
      environment: { wind_mps: [0, 0, 0], turbulence_intensity: 0 },
      events: { qbar_limit_pa: 90000, load_limit_g: 12, min_altitude_m: 20 }
    };
  }
  if (id === "gusty") {
    return {
      ...base,
      name: "gust_response",
      duration: 35,
      dt: 0.025,
      initial: { position_m: [0, 0, 350], velocity_mps: [95, 0, 0], euler_deg: [0, 4, 0] },
      guidance: { mode: "heading_hold", throttle: 0.88, heading_command_deg: 8, pitch_command_deg: 4 },
      environment: { wind_mps: [8, -5, 0], gust_mps: [6, 3, 0], turbulence_intensity: 0.35 },
      events: { qbar_limit_pa: 110000, load_limit_g: 10, min_altitude_m: 75 }
    };
  }
  if (id === "terrain") {
    return {
      ...base,
      name: "terrain_following",
      duration: 42,
      dt: 0.03,
      initial: { position_m: [0, 0, 180], velocity_mps: [72, 0, 0], euler_deg: [0, 3, 0] },
      guidance: { mode: "waypoint", throttle: 0.76, target_position_m: [1200, 120, 210] },
      sensors: { radar_altimeter: { rate_hz: 30, noise_std: 0.8, dropout_probability: 0.01 } },
      events: { qbar_limit_pa: 75000, load_limit_g: 8, min_altitude_m: 45, target_altitude_error_m: 25 }
    };
  }
  if (id === "highAltitude") {
    return {
      ...base,
      name: "high_altitude_climb",
      duration: 75,
      dt: 0.05,
      initial: { position_m: [0, 0, 10500], velocity_mps: [165, 0, 8], euler_deg: [0, 9, 0] },
      guidance: { mode: "pitch_program", throttle: 0.95, heading_command_deg: 0, pitch_program: [[0, 9], [25, 7], [75, 4]] },
      environment: { wind_mps: [18, 2, 0], turbulence_intensity: 0.12 },
      events: { qbar_limit_pa: 65000, load_limit_g: 6, min_altitude_m: 9000 }
    };
  }
  if (id === "sensorFault") {
    return {
      ...base,
      name: "sensor_fault_campaign",
      duration: 40,
      dt: 0.025,
      initial: { position_m: [0, 0, 600], velocity_mps: [105, 0, 0], euler_deg: [0, 5, 0] },
      guidance: { mode: "heading_hold", throttle: 0.86, heading_command_deg: 12, pitch_command_deg: 4 },
      sensors: {
        seed: 77,
        imu: { rate_hz: 100, noise_std: 0.015, dropout_probability: 0 },
        gps: { rate_hz: 8, noise_std: 1.5, dropout_probability: 0.12 },
        pitot: { rate_hz: 40, noise_std: 0.8, dropout_probability: 0.02 },
        faults: [{ sensor: "gps", type: "dropout", start_s: 12, end_s: 20 }]
      },
      events: { qbar_limit_pa: 95000, load_limit_g: 9, min_altitude_m: 90 }
    };
  }
  return {
    ...base,
    name: "intercept_trial",
    duration: 32,
    dt: 0.02,
    initial: { position_m: [0, 0, 900], velocity_mps: [115, 0, 0], euler_deg: [0, 4, 0] },
    guidance: { mode: "target_intercept", throttle: 0.9, target_position_m: [1700, 0, 1200], heading_command_deg: 0, pitch_command_deg: 3 },
    targets: [{ id: "primary_target", label: "Primary Target", role: "primary", initial_position_m: [1700, 0, 1200], velocity_mps: [-12, 0, -2] }],
    interceptors: [
      {
        id: "interceptor_1",
        target_id: "primary_target",
        launch_time_s: 4,
        initial_velocity_mps: [20, 0, 0],
        max_speed_mps: 320,
        max_accel_mps2: 95,
        guidance_gain: 2.4,
        proximity_fuze_m: 22
      }
    ],
    events: { qbar_limit_pa: 105000, load_limit_g: 14, min_altitude_m: 90, target_threshold_m: 30 }
  };
}

function mergePatch(target: Record<string, unknown>, patch: Record<string, unknown>): Record<string, unknown> {
  const next = structuredClone(target);
  for (const [key, value] of Object.entries(patch)) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      next[key] = mergePatch(asRecord(next[key]), value as Record<string, unknown>);
    } else {
      next[key] = value;
    }
  }
  return next;
}

function NumberControl({
  label,
  value,
  min,
  max,
  step = 1,
  unit,
  onChange
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  onChange: (value: number) => void;
}) {
  const hasSlider = typeof min === "number" && typeof max === "number";
  return (
    <label className="field scenario-builder-v2-number">
      <span>
        {label}
        {unit ? <em>{unit}</em> : null}
      </span>
      <div className="scenario-builder-v2-number-row">
        {hasSlider ? <input type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /> : null}
        <input type="number" min={min} max={max} step={step} value={Number.isFinite(value) ? value : 0} onChange={(event) => onChange(Number(event.target.value))} />
      </div>
    </label>
  );
}

function TextControl({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectControl({ label, value, options, onChange }: { label: string; value: string; options: Option[]; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function SectionShell({ eyebrow, title, icon, children }: { eyebrow: string; title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="scenario-builder-v2-section builder-section">
      <div className="section-title">
        {icon}
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h3>{title}</h3>
        </div>
      </div>
      {children}
    </section>
  );
}

export function ScenarioBuilderV2({
  scenarioText,
  onScenarioTextChange,
  vehicles,
  environments,
  selectedVehicle,
  selectedEnvironment,
  onSelectedVehicleChange,
  onSelectedEnvironmentChange,
  onValidate,
  onSave,
  onRun,
  busyAction,
  validation = null
}: ScenarioBuilderV2Props) {
  const [activeSection, setActiveSection] = useState<BuilderSection>("mission");
  const draft = useMemo(() => parseDraft(scenarioText), [scenarioText]);
  const parseError = draft ? null : scenarioText.trim() ? "Scenario JSON is not currently parseable." : "Scenario JSON is empty.";
  const safeDraft = draft ?? {};
  const initial = asRecord(safeDraft.initial);
  const guidance = asRecord(safeDraft.guidance);
  const sensors = asRecord(safeDraft.sensors);
  const events = asRecord(safeDraft.events);
  const outputs = asRecord(safeDraft.outputs);
  const targets = asArray(safeDraft.targets).map(asRecord);
  const interceptors = asArray(safeDraft.interceptors).map(asRecord);
  const sensorFaults = asArray(sensors.faults).map(asRecord);
  const faults = [...sensorFaults, ...asArray(safeDraft.faults), ...asArray(events.faults)].map(asRecord);
  const vehicleId = configId(safeDraft.vehicle_config) || selectedVehicle;
  const environmentId = configId(safeDraft.environment_config) || selectedEnvironment;
  const completion = completionScore(safeDraft, parseError);
  const issues = validationIssues(validation, parseError);
  const explanation = explainScenario(safeDraft, optionLabel(vehicles, vehicleId), optionLabel(environments, environmentId));

  const update = (recipe: (next: Record<string, unknown>) => void) => {
    const next = cloneDraft(scenarioText);
    recipe(next);
    onScenarioTextChange(writeDraft(next));
  };

  const updateValue = (path: string[], value: unknown) => update((next) => setAt(next, path, value));
  const updateVector = (path: string[], index: number, value: number) => update((next) => setVector(next, path, index, value));

  const applyPreset = (id: PresetId) => {
    const next = mergePatch(cloneDraft(scenarioText), presetPatch(id, selectedVehicle || vehicleId, selectedEnvironment || environmentId));
    onScenarioTextChange(writeDraft(next));
  };

  const addTarget = () =>
    update((next) => {
      ensureArray(next, ["targets"]).push({
        id: `target_${targets.length + 1}`,
        label: `Target ${targets.length + 1}`,
        role: targets.length === 0 ? "primary" : "decoy",
        initial_position_m: [1400, 0, 900],
        velocity_mps: [-8, 0, 0]
      });
    });

  const addInterceptor = () =>
    update((next) => {
      ensureArray(next, ["interceptors"]).push({
        id: `interceptor_${interceptors.length + 1}`,
        target_id: asString(targets[0]?.id, "primary_target"),
        launch_time_s: 3,
        initial_velocity_mps: [15, 0, 0],
        max_speed_mps: 300,
        max_accel_mps2: 85,
        guidance_gain: 2,
        proximity_fuze_m: 25
      });
    });

  const removeArrayItem = (path: string[], index: number) =>
    update((next) => {
      const list = ensureArray(next, path);
      list.splice(index, 1);
    });

  const updateArrayItem = (path: string[], index: number, key: string, value: unknown) =>
    update((next) => {
      const list = ensureArray(next, path);
      list[index] = { ...asRecord(list[index]), [key]: value };
    });

  const updateArrayVector = (path: string[], index: number, key: string, vectorIndex: number, value: number) =>
    update((next) => {
      const list = ensureArray(next, path);
      const item = asRecord(list[index]);
      const vector = [...asArray(item[key])];
      while (vector.length <= vectorIndex) {
        vector.push(0);
      }
      vector[vectorIndex] = value;
      list[index] = { ...item, [key]: vector };
    });

  const addFault = () =>
    update((next) => {
      ensureArray(next, ["sensors", "faults"]).push({
        sensor: "gps",
        type: "dropout",
        start_s: 10,
        end_s: 15
      });
    });

  const setVehicle = (id: string) => {
    onSelectedVehicleChange(id);
    updateValue(["vehicle_config"], vehiclePath(id));
  };

  const setEnvironment = (id: string) => {
    onSelectedEnvironmentChange(id);
    updateValue(["environment_config"], environmentPath(id));
  };

  const renderSection = () => {
    if (activeSection === "mission") {
      return (
        <SectionShell eyebrow="Mission Profile" title="Shape the run envelope." icon={<ListChecks size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            <TextControl label="Name" value={asString(safeDraft.name)} onChange={(value) => updateValue(["name"], value)} />
            <NumberControl label="Duration" unit="s" min={1} max={240} step={1} value={asNumber(safeDraft.duration, 30)} onChange={(value) => updateValue(["duration"], value)} />
            <NumberControl label="dt" unit="s" min={0.005} max={0.2} step={0.005} value={asNumber(safeDraft.dt, 0.03)} onChange={(value) => updateValue(["dt"], value)} />
            <label className="field">
              <span>Integrator</span>
              <select value={asString(safeDraft.integrator, "semi_implicit_euler")} onChange={(event) => updateValue(["integrator"], event.target.value)}>
                {["semi_implicit_euler", "euler", "rk2", "rk4", "adaptive_rk45"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "vehicle") {
      return (
        <SectionShell eyebrow="Vehicle" title="Choose the airframe and key actuation assumptions." icon={<Gauge size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            <SelectControl label="Vehicle config" value={vehicleId} options={vehicles} onChange={setVehicle} />
            <NumberControl label="Throttle" min={0} max={1} step={0.01} value={asNumber(guidance.throttle, 0.85)} onChange={(value) => updateValue(["guidance", "throttle"], value)} />
            <NumberControl label="Max qbar" unit="Pa" min={10000} max={150000} step={1000} value={asNumber(events.qbar_limit_pa, 90000)} onChange={(value) => updateValue(["events", "qbar_limit_pa"], value)} />
            <NumberControl label="Max load" unit="g" min={1} max={25} step={0.5} value={asNumber(events.load_limit_g, 12)} onChange={(value) => updateValue(["events", "load_limit_g"], value)} />
          </div>
          <div className="scenario-builder-v2-hint">Selected: {optionLabel(vehicles, vehicleId)}. The JSON reference remains `{vehiclePath(vehicleId || selectedVehicle || "baseline")}`.</div>
        </SectionShell>
      );
    }

    if (activeSection === "environment") {
      const environment = asRecord(safeDraft.environment);
      return (
        <SectionShell eyebrow="Environment" title="Set atmosphere, wind, and range conditions." icon={<SlidersHorizontal size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            <SelectControl label="Environment config" value={environmentId} options={environments} onChange={setEnvironment} />
            <NumberControl label="Wind X" unit="m/s" min={-40} max={40} step={1} value={vectorNumber(environment.wind_mps, 0, 0)} onChange={(value) => updateVector(["environment", "wind_mps"], 0, value)} />
            <NumberControl label="Wind Y" unit="m/s" min={-40} max={40} step={1} value={vectorNumber(environment.wind_mps, 1, 0)} onChange={(value) => updateVector(["environment", "wind_mps"], 1, value)} />
            <NumberControl label="Turbulence" min={0} max={1} step={0.01} value={asNumber(environment.turbulence_intensity, 0)} onChange={(value) => updateValue(["environment", "turbulence_intensity"], value)} />
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "initial") {
      return (
        <SectionShell eyebrow="Initial State" title="Initialize position, velocity, and attitude." icon={<Radar size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            <NumberControl label="Altitude" unit="m" min={0} max={20000} step={10} value={vectorNumber(initial.position_m, 2, 100)} onChange={(value) => updateVector(["initial", "position_m"], 2, value)} />
            <NumberControl label="Downrange X" unit="m" min={-5000} max={5000} step={10} value={vectorNumber(initial.position_m, 0, 0)} onChange={(value) => updateVector(["initial", "position_m"], 0, value)} />
            <NumberControl label="Crossrange Y" unit="m" min={-5000} max={5000} step={10} value={vectorNumber(initial.position_m, 1, 0)} onChange={(value) => updateVector(["initial", "position_m"], 1, value)} />
            <NumberControl label="Speed X" unit="m/s" min={0} max={400} step={1} value={vectorNumber(initial.velocity_mps, 0, 85)} onChange={(value) => updateVector(["initial", "velocity_mps"], 0, value)} />
            <NumberControl label="Vertical speed" unit="m/s" min={-80} max={80} step={1} value={vectorNumber(initial.velocity_mps, 2, 0)} onChange={(value) => updateVector(["initial", "velocity_mps"], 2, value)} />
            <NumberControl label="Pitch" unit="deg" min={-45} max={45} step={0.5} value={vectorNumber(initial.euler_deg, 1, 5)} onChange={(value) => updateVector(["initial", "euler_deg"], 1, value)} />
            <NumberControl label="Heading yaw" unit="deg" min={-180} max={180} step={1} value={vectorNumber(initial.euler_deg, 2, 0)} onChange={(value) => updateVector(["initial", "euler_deg"], 2, value)} />
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "gnc") {
      return (
        <SectionShell eyebrow="GNC" title="Command guidance, heading, pitch, and throttle." icon={<ShieldAlert size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            <label className="field">
              <span>Guidance mode</span>
              <select value={asString(guidance.mode, "pitch_program")} onChange={(event) => updateValue(["guidance", "mode"], event.target.value)}>
                {["pitch_program", "altitude_hold", "waypoint", "target_intercept", "proportional_navigation", "heading_hold", "open_loop"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <NumberControl label="Heading command" unit="deg" min={-180} max={180} step={1} value={asNumber(guidance.heading_command_deg, 0)} onChange={(value) => updateValue(["guidance", "heading_command_deg"], value)} />
            <NumberControl label="Pitch command" unit="deg" min={-30} max={30} step={0.5} value={asNumber(guidance.pitch_command_deg, vectorNumber(initial.euler_deg, 1, 5))} onChange={(value) => updateValue(["guidance", "pitch_command_deg"], value)} />
            <NumberControl label="Throttle" min={0} max={1} step={0.01} value={asNumber(guidance.throttle, 0.85)} onChange={(value) => updateValue(["guidance", "throttle"], value)} />
            <NumberControl label="Altitude command" unit="m" min={0} max={20000} step={10} value={asNumber(guidance.altitude_command_m, vectorNumber(initial.position_m, 2, 100))} onChange={(value) => updateValue(["guidance", "altitude_command_m"], value)} />
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "sensors") {
      const imu = asRecord(sensors.imu);
      const gps = asRecord(sensors.gps);
      const pitot = asRecord(sensors.pitot);
      const radarAltimeter = asRecord(sensors.radar_altimeter);
      return (
        <SectionShell eyebrow="Sensors" title="Tune rates, noise, seeds, and dropouts." icon={<Radar size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            <NumberControl label="Sensor seed" min={0} max={9999} step={1} value={asNumber(sensors.seed, 21)} onChange={(value) => updateValue(["sensors", "seed"], value)} />
            <NumberControl label="IMU rate" unit="Hz" min={10} max={400} step={5} value={asNumber(imu.rate_hz, 100)} onChange={(value) => updateValue(["sensors", "imu", "rate_hz"], value)} />
            <NumberControl label="IMU noise" min={0} max={0.2} step={0.001} value={asNumber(imu.noise_std, 0.01)} onChange={(value) => updateValue(["sensors", "imu", "noise_std"], value)} />
            <NumberControl label="GPS rate" unit="Hz" min={1} max={50} step={1} value={asNumber(gps.rate_hz, 5)} onChange={(value) => updateValue(["sensors", "gps", "rate_hz"], value)} />
            <NumberControl label="GPS noise" unit="m" min={0} max={20} step={0.1} value={asNumber(gps.noise_std, 1.5)} onChange={(value) => updateValue(["sensors", "gps", "noise_std"], value)} />
            <NumberControl label="GPS dropout" min={0} max={1} step={0.01} value={asNumber(gps.dropout_probability, 0)} onChange={(value) => updateValue(["sensors", "gps", "dropout_probability"], value)} />
            <NumberControl label="Pitot rate" unit="Hz" min={1} max={100} step={1} value={asNumber(pitot.rate_hz, 30)} onChange={(value) => updateValue(["sensors", "pitot", "rate_hz"], value)} />
            <NumberControl label="Pitot noise" unit="m/s" min={0} max={10} step={0.1} value={asNumber(pitot.noise_std, 0.6)} onChange={(value) => updateValue(["sensors", "pitot", "noise_std"], value)} />
            <NumberControl label="Radar rate" unit="Hz" min={1} max={100} step={1} value={asNumber(radarAltimeter.rate_hz, 20)} onChange={(value) => updateValue(["sensors", "radar_altimeter", "rate_hz"], value)} />
            <NumberControl label="Radar dropout" min={0} max={1} step={0.01} value={asNumber(radarAltimeter.dropout_probability, 0)} onChange={(value) => updateValue(["sensors", "radar_altimeter", "dropout_probability"], value)} />
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "faults") {
      return (
        <SectionShell eyebrow="Faults" title="Schedule injected failures on a timeline." icon={<AlertTriangle size={18} />}>
          <div className="section-row">
            <div className="scenario-builder-v2-hint">Fault entries are written to `sensors.faults`; existing top-level or event fault lists are counted but left in place.</div>
            <button className="secondary-action" type="button" onClick={addFault}>
              <Plus size={16} />
              Add Fault
            </button>
          </div>
          <div className="builder-card-grid scenario-builder-v2-card-grid">
            {sensorFaults.map((fault, index) => {
              return (
                <div className="builder-card scenario-builder-v2-card" key={`${asString(fault.sensor, "fault")}-${index}`}>
                  <div className="section-row">
                    <strong>{asString(fault.sensor, `sensor_${index + 1}`)} {asString(fault.type, "fault")}</strong>
                    <button className="icon-action" type="button" aria-label="Remove fault" onClick={() => removeArrayItem(["sensors", "faults"], index)}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <TextControl label="Sensor" value={asString(fault.sensor, asString(fault.target, "gps"))} onChange={(value) => updateArrayItem(["sensors", "faults"], index, "sensor", value)} />
                  <label className="field">
                    <span>Type</span>
                    <select value={asString(fault.type, "dropout")} onChange={(event) => updateArrayItem(["sensors", "faults"], index, "type", event.target.value)}>
                      <option value="dropout">dropout</option>
                      <option value="bias">bias</option>
                      <option value="bias_jump">bias_jump</option>
                      <option value="scale">scale</option>
                    </select>
                  </label>
                  <NumberControl label="Start" unit="s" min={0} max={asNumber(safeDraft.duration, 60)} value={asNumber(fault.start_s, 10)} onChange={(value) => updateArrayItem(["sensors", "faults"], index, "start_s", value)} />
                  <NumberControl label="End" unit="s" min={0} max={asNumber(safeDraft.duration, 60)} value={asNumber(fault.end_s, 15)} onChange={(value) => updateArrayItem(["sensors", "faults"], index, "end_s", value)} />
                </div>
              );
            })}
            {sensorFaults.length === 0 ? <div className="empty-state">No sensor faults configured. Add one to create a reproducible failure timeline.</div> : null}
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "targets") {
      return (
        <SectionShell eyebrow="Targets/Interceptors" title="Manage engagement objects." icon={<Target size={18} />}>
          <div className="section-row scenario-builder-v2-actions">
            <button className="secondary-action" type="button" onClick={addTarget}>
              <Plus size={16} />
              Add Target
            </button>
            <button className="secondary-action" type="button" onClick={addInterceptor}>
              <Plus size={16} />
              Add Interceptor
            </button>
          </div>
          <div className="builder-card-grid scenario-builder-v2-card-grid scenario-builder-v2-engagement-grid">
            {targets.map((target, index) => (
              <div className="builder-card scenario-builder-v2-card" key={`${asString(target.id, "target")}-${index}`}>
                <div className="section-row">
                  <strong>{asString(target.label, asString(target.id, `target_${index + 1}`))}</strong>
                  <button className="icon-action" type="button" aria-label="Remove target" onClick={() => removeArrayItem(["targets"], index)}>
                    <Trash2 size={16} />
                  </button>
                </div>
                <TextControl label="ID" value={asString(target.id, `target_${index + 1}`)} onChange={(value) => updateArrayItem(["targets"], index, "id", value)} />
                <TextControl label="Label" value={asString(target.label, `Target ${index + 1}`)} onChange={(value) => updateArrayItem(["targets"], index, "label", value)} />
                <label className="field">
                  <span>Role</span>
                  <select value={asString(target.role, index === 0 ? "primary" : "decoy")} onChange={(event) => updateArrayItem(["targets"], index, "role", event.target.value)}>
                    <option value="primary">primary</option>
                    <option value="decoy">decoy</option>
                    <option value="waypoint">waypoint</option>
                  </select>
                </label>
                <NumberControl label="Target X" unit="m" value={vectorNumber(target.initial_position_m, 0, 1400)} onChange={(value) => updateArrayVector(["targets"], index, "initial_position_m", 0, value)} />
                <NumberControl label="Target Y" unit="m" value={vectorNumber(target.initial_position_m, 1, 0)} onChange={(value) => updateArrayVector(["targets"], index, "initial_position_m", 1, value)} />
                <NumberControl label="Target altitude" unit="m" value={vectorNumber(target.initial_position_m, 2, 900)} onChange={(value) => updateArrayVector(["targets"], index, "initial_position_m", 2, value)} />
                <NumberControl label="Target VX" unit="m/s" value={vectorNumber(target.velocity_mps, 0, -8)} onChange={(value) => updateArrayVector(["targets"], index, "velocity_mps", 0, value)} />
              </div>
            ))}
            {interceptors.map((interceptor, index) => (
              <div className="builder-card scenario-builder-v2-card" key={`${asString(interceptor.id, "interceptor")}-${index}`}>
                <div className="section-row">
                  <strong>{asString(interceptor.id, `interceptor_${index + 1}`)}</strong>
                  <button className="icon-action" type="button" aria-label="Remove interceptor" onClick={() => removeArrayItem(["interceptors"], index)}>
                    <Trash2 size={16} />
                  </button>
                </div>
                <TextControl label="ID" value={asString(interceptor.id, `interceptor_${index + 1}`)} onChange={(value) => updateArrayItem(["interceptors"], index, "id", value)} />
                <TextControl label="Target ID" value={asString(interceptor.target_id, asString(targets[0]?.id, "primary_target"))} onChange={(value) => updateArrayItem(["interceptors"], index, "target_id", value)} />
                <NumberControl label="Launch" unit="s" min={0} max={asNumber(safeDraft.duration, 60)} value={asNumber(interceptor.launch_time_s, 3)} onChange={(value) => updateArrayItem(["interceptors"], index, "launch_time_s", value)} />
                <NumberControl label="Max speed" unit="m/s" min={0} max={1200} value={asNumber(interceptor.max_speed_mps, 300)} onChange={(value) => updateArrayItem(["interceptors"], index, "max_speed_mps", value)} />
                <NumberControl label="Max accel" unit="m/s2" min={0} max={250} value={asNumber(interceptor.max_accel_mps2, 85)} onChange={(value) => updateArrayItem(["interceptors"], index, "max_accel_mps2", value)} />
                <NumberControl label="Fuze" unit="m" min={1} max={200} value={asNumber(interceptor.proximity_fuze_m, 25)} onChange={(value) => updateArrayItem(["interceptors"], index, "proximity_fuze_m", value)} />
              </div>
            ))}
            {targets.length + interceptors.length === 0 ? <div className="empty-state">No targets or interceptors configured.</div> : null}
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "termination") {
      return (
        <SectionShell eyebrow="Termination" title="Define guardrails that stop or flag runs." icon={<ShieldAlert size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            <NumberControl label="Qbar limit" unit="Pa" min={10000} max={160000} step={1000} value={asNumber(events.qbar_limit_pa, 90000)} onChange={(value) => updateValue(["events", "qbar_limit_pa"], value)} />
            <NumberControl label="Load limit" unit="g" min={1} max={25} step={0.5} value={asNumber(events.load_limit_g, 12)} onChange={(value) => updateValue(["events", "load_limit_g"], value)} />
            <NumberControl label="Min altitude" unit="m" min={-200} max={5000} step={10} value={asNumber(events.min_altitude_m, 0)} onChange={(value) => updateValue(["events", "min_altitude_m"], value)} />
            <NumberControl label="Target miss limit" unit="m" min={1} max={1000} step={1} value={asNumber(events.target_threshold_m, 50)} onChange={(value) => updateValue(["events", "target_threshold_m"], value)} />
          </div>
        </SectionShell>
      );
    }

    if (activeSection === "outputs") {
      return (
        <SectionShell eyebrow="Outputs" title="Choose artifacts and telemetry products." icon={<FileJson size={18} />}>
          <div className="guided-grid scenario-builder-v2-grid">
            {(["telemetry", "events", "summary", "plots", "html_report"] as const).map((key) => (
              <label className="field scenario-builder-v2-check" key={key}>
                <span>{key}</span>
                <input type="checkbox" checked={asBoolean(outputs[key], key === "telemetry" || key === "summary")} onChange={(event) => updateValue(["outputs", key], event.target.checked)} />
              </label>
            ))}
            <TextControl label="Channels" value={uniqueStringList(outputs.channels).join(", ")} onChange={(value) => updateValue(["outputs", "channels"], uniqueStringList(value))} />
          </div>
        </SectionShell>
      );
    }

    return (
      <SectionShell eyebrow="Expert JSON" title="Edit the raw source of truth." icon={<FileJson size={18} />}>
        <label className="field editor-field scenario-builder-v2-json">
          <span>Scenario JSON</span>
          <textarea value={scenarioText} onChange={(event) => onScenarioTextChange(event.target.value)} spellCheck={false} />
        </label>
      </SectionShell>
    );
  };

  return (
    <div className="scenario-builder-v2">
      <div className="scenario-builder-v2-preset-bar">
        {PRESETS.map((preset) => (
          <button className="secondary-action scenario-builder-v2-preset" type="button" key={preset.id} onClick={() => applyPreset(preset.id)} title={preset.note}>
            <Wand2 size={15} />
            {preset.label}
          </button>
        ))}
      </div>

      <div className="scenario-builder-v2-layout editor-layout">
        <section className="editor-panel scenario-builder-v2-main">
          <div className="mini-segment scenario-builder-v2-tabs" role="tablist" aria-label="Scenario builder sections">
            {SECTIONS.map((section) => (
              <button key={section.id} className={activeSection === section.id ? "active" : ""} type="button" role="tab" aria-selected={activeSection === section.id} onClick={() => setActiveSection(section.id)}>
                {section.label}
              </button>
            ))}
          </div>
          {renderSection()}
          <div className="editor-actions scenario-builder-v2-runbar">
            <button className="secondary-action" type="button" onClick={onValidate} disabled={busyAction === "validate_draft"}>
              <CheckCircle2 size={17} />
              Validate
            </button>
            <button className="secondary-action" type="button" onClick={onSave} disabled={busyAction === "save_draft"}>
              <Save size={17} />
              Save Draft
            </button>
            <button className="primary-action" type="button" onClick={onRun} disabled={busyAction === "run"}>
              <Play size={17} />
              Run Draft
            </button>
          </div>
        </section>

        <aside className="editor-panel compact-panel scenario-builder-v2-aside">
          <div className="section-title">
            <ListChecks size={16} />
            <h3>Completeness</h3>
          </div>
          <div className="scenario-builder-v2-meter" aria-label={`Scenario completeness ${completion}%`}>
            <span style={{ width: `${completion}%` }} />
          </div>
          <strong>{completion}% ready</strong>

          <div className="scenario-explain">
            <strong>Explain this scenario</strong>
            <p>{explanation}</p>
          </div>

          <div className={`validation-state ${validation?.valid && !parseError ? "ok" : issues.length ? "bad" : ""}`}>
            {validation?.valid && !parseError ? "valid" : issues.length ? "needs attention" : "not validated"}
          </div>
          {issues.length > 0 ? (
            <div className="scenario-builder-v2-warning-panel">
              {issues.map((issue, index) => (
                <p key={`${issue}-${index}`}>
                  <AlertTriangle size={14} />
                  {issue}
                </p>
              ))}
            </div>
          ) : null}
          {validation ? <pre>{compactJson(validation)}</pre> : null}
        </aside>
      </div>
    </div>
  );
}

export default ScenarioBuilderV2;
