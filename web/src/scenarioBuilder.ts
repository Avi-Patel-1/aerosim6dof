export type JsonObject = Record<string, unknown>;
export type ScenarioPath = Array<string | number>;

export type ScenarioSectionId =
  | "mission_profile"
  | "vehicle"
  | "environment"
  | "initial_state"
  | "gnc"
  | "sensors"
  | "faults"
  | "targets_interceptors"
  | "termination"
  | "output_reports"
  | "expert_json";

export type ScenarioSectionDefinition = {
  id: ScenarioSectionId;
  label: string;
  description: string;
  paths: string[];
};

export type ScenarioPresetId = "nominal" | "gusty_range" | "terrain_agl" | "high_altitude" | "sensor_fault" | "intercept";

export type ScenarioPresetDefinition = {
  id: ScenarioPresetId;
  label: string;
  description: string;
  scenario: JsonObject;
};

export type ScenarioWarningSeverity = "info" | "caution" | "warning";

export type ScenarioWarningRow = {
  severity: ScenarioWarningSeverity;
  section: ScenarioSectionId;
  message: string;
  path: string;
};

export type ScenarioCompleteness = {
  percent: number;
  missingSections: ScenarioSectionId[];
};

export type ScenarioParseResult = {
  draft: JsonObject;
  valid: boolean;
  error: string | null;
};

export const SCENARIO_SECTION_IDS: ScenarioSectionId[] = [
  "mission_profile",
  "vehicle",
  "environment",
  "initial_state",
  "gnc",
  "sensors",
  "faults",
  "targets_interceptors",
  "termination",
  "output_reports",
  "expert_json"
];

export const SCENARIO_SECTIONS: ScenarioSectionDefinition[] = [
  {
    id: "mission_profile",
    label: "Mission Profile",
    description: "Scenario identity, time step, duration, and integration settings.",
    paths: ["name", "dt", "duration", "integrator"]
  },
  {
    id: "vehicle",
    label: "Vehicle",
    description: "Vehicle configuration reference and optional scenario-level vehicle overrides.",
    paths: ["vehicle_config", "vehicle"]
  },
  {
    id: "environment",
    label: "Environment",
    description: "Atmosphere, wind, turbulence, terrain, and range environment selection.",
    paths: ["environment_config", "environment"]
  },
  {
    id: "initial_state",
    label: "Initial State",
    description: "Initial position, velocity, attitude, and body rates.",
    paths: ["initial.position_m", "initial.velocity_mps", "initial.euler_deg", "initial.body_rates_dps"]
  },
  {
    id: "gnc",
    label: "GNC",
    description: "Guidance mode, commands, target points, navigation mode, and throttle.",
    paths: ["guidance"]
  },
  {
    id: "sensors",
    label: "Sensors",
    description: "Sensor seeds, rates, noise models, latency, and drift settings.",
    paths: ["sensors"]
  },
  {
    id: "faults",
    label: "Faults",
    description: "Sensor, propulsion, and actuator faults injected during the run.",
    paths: ["sensors.faults", "vehicle.actuators", "vehicle.engine.failure", "vehicle.propulsion.failure"]
  },
  {
    id: "targets_interceptors",
    label: "Targets/Interceptors",
    description: "Moving targets, decoys, interceptor launches, and proximity-fuze settings.",
    paths: ["targets", "interceptors", "guidance.target_position_m"]
  },
  {
    id: "termination",
    label: "Termination",
    description: "Event thresholds and stop conditions used by range safety and analysis.",
    paths: ["events"]
  },
  {
    id: "output_reports",
    label: "Output/Reports",
    description: "Optional reporting, sampling, and export hints for browser workflows.",
    paths: ["output", "reports"]
  },
  {
    id: "expert_json",
    label: "Expert JSON",
    description: "Raw scenario JSON for advanced edits and uncommon engine features.",
    paths: ["*"]
  }
];

export const SCENARIO_PRESETS: ScenarioPresetDefinition[] = [
  {
    id: "nominal",
    label: "Nominal",
    description: "Baseline pitch-program ascent in a calm range environment.",
    scenario: {
      name: "browser_nominal_ascent",
      dt: 0.03,
      duration: 18.0,
      integrator: "semi_implicit_euler",
      vehicle_config: "../vehicles/baseline.json",
      environment_config: "../environments/calm.json",
      initial: {
        position_m: [0.0, 0.0, 20.0],
        velocity_mps: [85.0, 0.0, 8.0],
        euler_deg: [0.0, 6.0, 0.0],
        body_rates_dps: [0.0, 0.0, 0.0]
      },
      guidance: {
        mode: "pitch_program",
        pitch_program: [[0.0, 13.0], [6.0, 10.0], [14.0, 7.0]],
        heading_command_deg: 0.0,
        throttle: 0.86
      },
      sensors: {
        seed: 21,
        imu_noise_std: 0.04,
        gps_noise_std_m: 1.2,
        baro_noise_std_m: 0.6
      },
      events: {
        qbar_limit_pa: 90000.0,
        load_limit_g: 15.0
      }
    }
  },
  {
    id: "gusty_range",
    label: "Gusty Range",
    description: "Crossrange ascent with gusts, heading hold, and noisier sensors.",
    scenario: {
      name: "browser_gusty_range",
      dt: 0.03,
      duration: 20.0,
      integrator: "semi_implicit_euler",
      vehicle_config: "../vehicles/baseline.json",
      environment_config: "../environments/gusted_range.json",
      initial: {
        position_m: [0.0, 0.0, 1000.0],
        velocity_mps: [84.0, 2.0, 15.0],
        euler_deg: [0.0, 9.0, 2.0],
        body_rates_dps: [0.0, 0.0, 0.0]
      },
      vehicle: {
        mass_kg: 19.0,
        dry_mass_kg: 14.2,
        inertia_kgm2: [[0.38, 0.0, 0.0], [0.0, 0.96, 0.0], [0.0, 0.0, 0.9]]
      },
      guidance: {
        mode: "heading_hold",
        pitch_command_deg: 18.0,
        heading_command_deg: -5.0,
        throttle: 0.84
      },
      sensors: {
        seed: 44,
        imu_noise_std: 0.05,
        gps_noise_std_m: 2.0,
        baro_noise_std_m: 0.9
      }
    }
  },
  {
    id: "terrain_agl",
    label: "Terrain/AGL",
    description: "Waypoint mission against the terrain range with radar-altimeter context.",
    scenario: {
      name: "browser_terrain_agl",
      dt: 0.04,
      duration: 28.0,
      vehicle_config: "../vehicles/electric_uav.json",
      environment_config: "../environments/terrain_range.json",
      initial: {
        position_m: [0.0, -180.0, 450.0],
        velocity_mps: [42.0, 2.0, 0.0],
        euler_deg: [0.0, 3.0, 4.0],
        body_rates_dps: [0.0, 0.0, 0.0]
      },
      guidance: {
        mode: "waypoint",
        target_position_m: [900.0, 80.0, 520.0],
        throttle: 0.78
      },
      sensors: {
        seed: 233,
        gps_noise_std_m: 3.0,
        baro_noise_std_m: 1.5,
        radar_altimeter: {
          rate_hz: 15.0,
          max_range_m: 1800.0
        }
      },
      events: {
        target_threshold_m: 60.0,
        qbar_limit_pa: 22000.0,
        load_limit_g: 6.0
      }
    }
  },
  {
    id: "high_altitude",
    label: "High Altitude",
    description: "Low-density flight using the high-altitude probe and RK4 integration.",
    scenario: {
      name: "browser_high_altitude",
      dt: 0.04,
      duration: 24.0,
      integrator: "rk4",
      vehicle_config: "../vehicles/high_altitude_probe.json",
      environment_config: "../environments/calm.json",
      initial: {
        position_m: [0.0, 0.0, 14500.0],
        velocity_mps: [168.0, 0.0, 10.0],
        euler_deg: [0.0, 4.0, 0.0],
        body_rates_dps: [0.0, 0.0, 0.0]
      },
      guidance: {
        mode: "pitch_program",
        pitch_program: [[0.0, 6.0], [8.0, 10.0], [18.0, 4.0]],
        heading_command_deg: 0.0,
        throttle: 0.92
      },
      events: {
        qbar_limit_pa: 65000.0,
        load_limit_g: 8.0
      },
      sensors: {
        seed: 143,
        gps_noise_std_m: 6.0,
        baro_noise_std_m: 4.0
      }
    }
  },
  {
    id: "sensor_fault",
    label: "Sensor Fault",
    description: "Noisy-sensor navigation with a timed GPS dropout.",
    scenario: {
      name: "browser_sensor_fault",
      dt: 0.03,
      duration: 18.0,
      vehicle_config: "../vehicles/baseline.json",
      environment_config: "../environments/turbulent_range.json",
      initial: {
        position_m: [0.0, 0.0, 900.0],
        velocity_mps: [84.0, 1.0, 10.0],
        euler_deg: [0.5, 7.0, 0.5],
        body_rates_dps: [0.0, 0.0, 0.0]
      },
      guidance: {
        mode: "altitude_hold",
        target_altitude_m: 1450.0,
        trim_pitch_deg: 7.0,
        heading_command_deg: 4.0,
        throttle: 0.84,
        navigation: "noisy_sensors"
      },
      sensors: {
        seed: 261,
        gps: {
          rate_hz: 3.0,
          position_noise_std_m: 3.0,
          velocity_noise_std_mps: 0.25,
          latency_s: 0.18,
          multipath_amplitude_m: 4.0
        },
        barometer: {
          rate_hz: 20.0,
          noise_std_m: 2.0,
          weather_drift_mps: 0.08
        },
        radar_altimeter: {
          rate_hz: 15.0,
          max_range_m: 1800.0
        },
        faults: [
          {
            sensor: "gps",
            type: "dropout",
            start_s: 7.0,
            end_s: 11.0
          }
        ]
      }
    }
  },
  {
    id: "intercept",
    label: "Intercept",
    description: "Target-intercept scenario with decoy target and range defender launch.",
    scenario: {
      name: "browser_target_intercept",
      dt: 0.03,
      duration: 18.0,
      vehicle_config: "../vehicles/baseline.json",
      environment_config: "../environments/gusted_range.json",
      initial: {
        position_m: [0.0, -120.0, 1000.0],
        velocity_mps: [88.0, 4.0, 14.0],
        euler_deg: [0.0, 8.0, 3.0],
        body_rates_dps: [0.0, 0.0, 0.0]
      },
      guidance: {
        mode: "target_intercept",
        target_position_m: [1450.0, 0.0, 1500.0],
        throttle: 0.88
      },
      targets: [
        {
          id: "primary_target",
          label: "Primary target",
          role: "primary",
          initial_position_m: [1450.0, 0.0, 1500.0],
          velocity_mps: [-8.0, 0.0, -1.5]
        },
        {
          id: "offset_reference",
          label: "Offset reference",
          role: "decoy",
          initial_position_m: [1300.0, 170.0, 1380.0],
          velocity_mps: [-4.0, -2.0, 0.0]
        }
      ],
      interceptors: [
        {
          id: "range_defender_1",
          target_id: "primary_target",
          launch_time_s: 2.0,
          initial_velocity_mps: [10.0, 0.0, 0.0],
          max_speed_mps: 280.0,
          max_accel_mps2: 90.0,
          guidance_gain: 2.1,
          proximity_fuze_m: 25.0
        }
      ],
      events: {
        target_threshold_m: 75.0,
        qbar_limit_pa: 90000.0,
        load_limit_g: 12.0
      },
      sensors: {
        seed: 166
      }
    }
  }
];

export function parseScenarioDraft(text: string): ScenarioParseResult {
  try {
    const parsed = JSON.parse(text);
    if (!isRecord(parsed)) {
      return { draft: {}, valid: false, error: "Scenario JSON must be an object." };
    }
    return { draft: parsed, valid: true, error: null };
  } catch (error) {
    return { draft: {}, valid: false, error: error instanceof Error ? error.message : "Invalid JSON." };
  }
}

export function cloneScenarioDraft<T>(draft: T): T {
  return deepClone(draft);
}

export function updateNestedValue<T>(draft: T, path: string | ScenarioPath, value: unknown): T {
  const next = deepClone(draft);
  setValueAt(next, path, value);
  return next;
}

export function updateVectorValue<T>(draft: T, path: string | ScenarioPath, index: number, value: number): T {
  const current = valueAt(draft, path);
  const vector = Array.isArray(current) ? [...current] : [0, 0, 0];
  while (vector.length <= index) {
    vector.push(0);
  }
  vector[index] = value;
  return updateNestedValue(draft, path, vector);
}

export function updateArrayObject<T>(draft: T, path: string | ScenarioPath, index: number, key: string, value: unknown): T {
  const next = deepClone(draft);
  const list = ensureListAt(next, path);
  const item = isRecord(list[index]) ? { ...list[index] } : {};
  item[key] = value;
  list[index] = item;
  return next;
}

export function updateArrayObjectVector<T>(
  draft: T,
  path: string | ScenarioPath,
  index: number,
  key: string,
  vectorIndex: number,
  value: number
): T {
  const next = deepClone(draft);
  const list = ensureListAt(next, path);
  const item = isRecord(list[index]) ? { ...list[index] } : {};
  const vector = Array.isArray(item[key]) ? [...item[key]] : [0, 0, 0];
  while (vector.length <= vectorIndex) {
    vector.push(0);
  }
  vector[vectorIndex] = value;
  item[key] = vector;
  list[index] = item;
  return next;
}

export function appendObject<T>(draft: T, path: string | ScenarioPath, value: JsonObject): T {
  const next = deepClone(draft);
  ensureListAt(next, path).push(deepClone(value));
  return next;
}

export function removeObjectAt<T>(draft: T, path: string | ScenarioPath, index: number): T {
  const next = deepClone(draft);
  const list = ensureListAt(next, path);
  if (index >= 0 && index < list.length) {
    list.splice(index, 1);
  }
  return next;
}

export function duplicateObjectAt<T>(draft: T, path: string | ScenarioPath, index: number): T {
  const next = deepClone(draft);
  const list = ensureListAt(next, path);
  if (index >= 0 && index < list.length && isRecord(list[index])) {
    list.splice(index + 1, 0, duplicateWithFreshId(list[index] as JsonObject));
  }
  return next;
}

export function toScenarioText(draft: unknown): string {
  return JSON.stringify(draft ?? {}, null, 2);
}

export function updateScenarioText(text: string, path: string | ScenarioPath, value: unknown): string {
  const parsed = parseScenarioDraft(text);
  const next = updateNestedValue(parsed.valid ? parsed.draft : {}, path, value);
  return toScenarioText(next);
}

export function updateScenarioTextVector(text: string, path: string | ScenarioPath, index: number, value: number): string {
  const parsed = parseScenarioDraft(text);
  const next = updateVectorValue(parsed.valid ? parsed.draft : {}, path, index, value);
  return toScenarioText(next);
}

export function appendScenarioTextObject(text: string, path: string | ScenarioPath, value: JsonObject): string {
  const parsed = parseScenarioDraft(text);
  return toScenarioText(appendObject(parsed.valid ? parsed.draft : {}, path, value));
}

export function removeScenarioTextObject(text: string, path: string | ScenarioPath, index: number): string {
  const parsed = parseScenarioDraft(text);
  return toScenarioText(removeObjectAt(parsed.valid ? parsed.draft : {}, path, index));
}

export function duplicateScenarioTextObject(text: string, path: string | ScenarioPath, index: number): string {
  const parsed = parseScenarioDraft(text);
  return toScenarioText(duplicateObjectAt(parsed.valid ? parsed.draft : {}, path, index));
}

export function normalizeScenarioDraft(draft: unknown): JsonObject {
  const next = isRecord(draft) ? deepClone(draft) : {};
  if (!isNonEmptyString(next.name)) {
    next.name = "browser_scenario";
  }
  if (!isFiniteNumber(next.dt) || (next.dt as number) <= 0) {
    next.dt = 0.03;
  }
  if (!isFiniteNumber(next.duration) || (next.duration as number) <= 0) {
    next.duration = 18.0;
  }
  if (!isNonEmptyString(next.integrator)) {
    next.integrator = "semi_implicit_euler";
  }
  if (!isNonEmptyString(next.vehicle_config)) {
    next.vehicle_config = "../vehicles/baseline.json";
  }
  if (!isNonEmptyString(next.environment_config)) {
    next.environment_config = "../environments/calm.json";
  }

  const initial = objectAt(next, "initial");
  if (!Array.isArray(initial.position_m)) {
    initial.position_m = [0.0, 0.0, 20.0];
  }
  if (!Array.isArray(initial.velocity_mps)) {
    initial.velocity_mps = [85.0, 0.0, 8.0];
  }
  if (!Array.isArray(initial.euler_deg)) {
    initial.euler_deg = [0.0, 6.0, 0.0];
  }
  if (!Array.isArray(initial.body_rates_dps)) {
    initial.body_rates_dps = [0.0, 0.0, 0.0];
  }

  const guidance = objectAt(next, "guidance");
  if (!isNonEmptyString(guidance.mode)) {
    guidance.mode = "pitch_program";
  }
  if (!isFiniteNumber(guidance.throttle)) {
    guidance.throttle = 0.86;
  }
  if (guidance.mode === "pitch_program" && !Array.isArray(guidance.pitch_program)) {
    guidance.pitch_program = [[0.0, 13.0], [6.0, 10.0], [14.0, 7.0]];
  }

  const sensors = objectAt(next, "sensors");
  if (!isFiniteNumber(sensors.seed)) {
    sensors.seed = 1;
  }
  return next;
}

export function scenarioBuilderWarnings(draft: unknown): ScenarioWarningRow[] {
  const scenario = isRecord(draft) ? draft : {};
  const warnings: ScenarioWarningRow[] = [];
  const duration = numberValue(scenario.duration, NaN);
  const dt = numberValue(scenario.dt, NaN);
  const initial = objectAtReadonly(scenario, "initial");
  const guidance = objectAtReadonly(scenario, "guidance");
  const sensors = objectAtReadonly(scenario, "sensors");
  const events = objectAtReadonly(scenario, "events");
  const targets = listAtReadonly(scenario, "targets");
  const interceptors = listAtReadonly(scenario, "interceptors");

  if (!isNonEmptyString(scenario.name)) {
    addWarning(warnings, "warning", "mission_profile", "Scenario name is required before saving or launching.", "name");
  }
  if (!isFiniteNumber(dt) || dt <= 0) {
    addWarning(warnings, "warning", "mission_profile", "Time step must be a positive number.", "dt");
  } else if (dt > 0.1) {
    addWarning(warnings, "caution", "mission_profile", "Time step is coarse for flight dynamics; inspect stability before trusting results.", "dt");
  } else if (dt < 0.005) {
    addWarning(warnings, "info", "mission_profile", "Small time step can make browser-launched jobs slower.", "dt");
  }
  if (!isFiniteNumber(duration) || duration <= 0) {
    addWarning(warnings, "warning", "mission_profile", "Duration must be a positive number.", "duration");
  } else if (duration < 3) {
    addWarning(warnings, "caution", "mission_profile", "Very short duration may end before guidance or faults become observable.", "duration");
  } else if (duration > 120) {
    addWarning(warnings, "info", "mission_profile", "Long scenarios can create larger telemetry and report artifacts.", "duration");
  }
  if (!isNonEmptyString(scenario.vehicle_config)) {
    addWarning(warnings, "warning", "vehicle", "Select a vehicle configuration.", "vehicle_config");
  }
  if (!isNonEmptyString(scenario.environment_config)) {
    addWarning(warnings, "warning", "environment", "Select an environment configuration.", "environment_config");
  }

  warnVector(warnings, initial.position_m, "initial_state", "Initial position must be a 3-axis vector.", "initial.position_m");
  warnVector(warnings, initial.velocity_mps, "initial_state", "Initial velocity must be a 3-axis vector.", "initial.velocity_mps");
  warnVector(warnings, initial.euler_deg, "initial_state", "Initial attitude must be a 3-axis Euler vector.", "initial.euler_deg");
  if (Array.isArray(initial.position_m) && numberValue(initial.position_m[2], 0) < 0) {
    addWarning(warnings, "warning", "initial_state", "Initial altitude is below zero meters.", "initial.position_m[2]");
  }
  if (vectorMagnitude(initial.velocity_mps) < 1) {
    addWarning(warnings, "caution", "initial_state", "Initial speed is near zero; aerodynamic controls may be ineffective.", "initial.velocity_mps");
  }

  const mode = stringValue(guidance.mode, "");
  if (!mode) {
    addWarning(warnings, "warning", "gnc", "Guidance mode is required.", "guidance.mode");
  }
  const throttle = numberValue(guidance.throttle, NaN);
  if (!isFiniteNumber(throttle)) {
    addWarning(warnings, "caution", "gnc", "Throttle is not set; engine defaults may apply.", "guidance.throttle");
  } else if (throttle < 0 || throttle > 1) {
    addWarning(warnings, "warning", "gnc", "Throttle should normally be between 0 and 1.", "guidance.throttle");
  }
  if (mode === "pitch_program" && !Array.isArray(guidance.pitch_program)) {
    addWarning(warnings, "warning", "gnc", "Pitch-program guidance needs a pitch_program schedule.", "guidance.pitch_program");
  }
  if ((mode === "waypoint" || mode === "target_intercept") && !Array.isArray(guidance.target_position_m)) {
    addWarning(warnings, "warning", "gnc", "This guidance mode needs target_position_m.", "guidance.target_position_m");
  }

  const faults = listAtReadonly(sensors, "faults");
  faults.forEach((fault, index) => {
    if (!isRecord(fault)) {
      addWarning(warnings, "warning", "faults", "Fault entries must be objects.", `sensors.faults[${index}]`);
      return;
    }
    const start = numberValue(fault.start_s, NaN);
    const end = numberValue(fault.end_s, NaN);
    if (!isNonEmptyString(fault.type)) {
      addWarning(warnings, "caution", "faults", "Fault is missing a type.", `sensors.faults[${index}].type`);
    }
    if (isFiniteNumber(start) && isFiniteNumber(end) && end <= start) {
      addWarning(warnings, "warning", "faults", "Fault end time must be after start time.", `sensors.faults[${index}].end_s`);
    }
    if (isFiniteNumber(start) && isFiniteNumber(duration) && start > duration) {
      addWarning(warnings, "caution", "faults", "Fault starts after the scenario duration.", `sensors.faults[${index}].start_s`);
    }
  });

  targets.forEach((target, index) => {
    if (!isRecord(target)) {
      addWarning(warnings, "warning", "targets_interceptors", "Target entries must be objects.", `targets[${index}]`);
      return;
    }
    if (!isNonEmptyString(target.id)) {
      addWarning(warnings, "warning", "targets_interceptors", "Target is missing an id.", `targets[${index}].id`);
    }
    warnVector(warnings, target.initial_position_m, "targets_interceptors", "Target initial position must be a 3-axis vector.", `targets[${index}].initial_position_m`);
    warnVector(warnings, target.velocity_mps, "targets_interceptors", "Target velocity must be a 3-axis vector.", `targets[${index}].velocity_mps`);
  });

  interceptors.forEach((interceptor, index) => {
    if (!isRecord(interceptor)) {
      addWarning(warnings, "warning", "targets_interceptors", "Interceptor entries must be objects.", `interceptors[${index}]`);
      return;
    }
    if (targets.length > 0 && !isNonEmptyString(interceptor.target_id)) {
      addWarning(warnings, "warning", "targets_interceptors", "Interceptor must reference a target_id.", `interceptors[${index}].target_id`);
    }
    const launch = numberValue(interceptor.launch_time_s, NaN);
    if (isFiniteNumber(launch) && isFiniteNumber(duration) && launch > duration) {
      addWarning(warnings, "warning", "targets_interceptors", "Interceptor launch happens after scenario end.", `interceptors[${index}].launch_time_s`);
    }
    if (numberValue(interceptor.max_speed_mps, 1) <= 0) {
      addWarning(warnings, "warning", "targets_interceptors", "Interceptor max speed must be positive.", `interceptors[${index}].max_speed_mps`);
    }
  });

  if (mode === "target_intercept" && targets.length === 0) {
    addWarning(warnings, "caution", "targets_interceptors", "Target-intercept guidance has no target objects for replay context.", "targets");
  }
  if (!isRecord(events)) {
    addWarning(warnings, "info", "termination", "No event thresholds are configured.", "events");
  } else {
    if (isFiniteNumber(events.load_limit_g) && events.load_limit_g <= 0) {
      addWarning(warnings, "warning", "termination", "Load limit must be positive.", "events.load_limit_g");
    }
    if (isFiniteNumber(events.qbar_limit_pa) && events.qbar_limit_pa <= 0) {
      addWarning(warnings, "warning", "termination", "Dynamic-pressure limit must be positive.", "events.qbar_limit_pa");
    }
  }

  return warnings;
}

export function explainScenario(draft: unknown): string {
  const scenario = isRecord(draft) ? draft : {};
  const name = stringValue(scenario.name, "Unnamed scenario");
  const duration = numberValue(scenario.duration, 0);
  const dt = numberValue(scenario.dt, 0);
  const vehicle = configId(scenario.vehicle_config);
  const environment = configId(scenario.environment_config);
  const initial = objectAtReadonly(scenario, "initial");
  const guidance = objectAtReadonly(scenario, "guidance");
  const mode = stringValue(guidance.mode, "unspecified guidance");
  const altitude = vectorValue(initial.position_m, 2, 0);
  const speed = vectorMagnitude(initial.velocity_mps);
  const throttle = numberValue(guidance.throttle, NaN);
  const targets = listAtReadonly(scenario, "targets").length;
  const interceptors = listAtReadonly(scenario, "interceptors").length;
  const faults = listAtReadonly(objectAtReadonly(scenario, "sensors"), "faults").length;
  const throttleText = isFiniteNumber(throttle) ? ` at ${(throttle * 100).toFixed(0)}% throttle` : "";
  const targetText = targets || interceptors ? ` It includes ${targets} target${targets === 1 ? "" : "s"} and ${interceptors} interceptor${interceptors === 1 ? "" : "s"}.` : "";
  const faultText = faults ? ` ${faults} timed sensor fault${faults === 1 ? " is" : "s are"} configured.` : "";
  return `${name} runs ${duration.toFixed(1)} s with ${dt.toFixed(3)} s steps using ${vehicle || "an unspecified vehicle"} in ${environment || "an unspecified environment"}. It starts at ${altitude.toFixed(0)} m and ${speed.toFixed(1)} m/s, then flies ${mode}${throttleText}.${targetText}${faultText}`.trim();
}

export function scenarioCompleteness(draft: unknown): ScenarioCompleteness {
  const scenario = isRecord(draft) ? draft : {};
  const missingSections: ScenarioSectionId[] = [];
  const guidance = objectAtReadonly(scenario, "guidance");
  const initial = objectAtReadonly(scenario, "initial");

  if (!isNonEmptyString(scenario.name) || !isFiniteNumber(scenario.dt) || !isFiniteNumber(scenario.duration)) {
    missingSections.push("mission_profile");
  }
  if (!isNonEmptyString(scenario.vehicle_config)) {
    missingSections.push("vehicle");
  }
  if (!isNonEmptyString(scenario.environment_config)) {
    missingSections.push("environment");
  }
  if (!isVector3(initial.position_m) || !isVector3(initial.velocity_mps) || !isVector3(initial.euler_deg)) {
    missingSections.push("initial_state");
  }
  if (!isNonEmptyString(guidance.mode)) {
    missingSections.push("gnc");
  }
  if (!isRecord(scenario.sensors)) {
    missingSections.push("sensors");
  }
  if (!isRecord(scenario.events)) {
    missingSections.push("termination");
  }

  const required = 7;
  const complete = required - missingSections.length;
  return {
    percent: clamp(Math.round((complete / required) * 100), 0, 100),
    missingSections
  };
}

export function configId(value: unknown): string {
  const text = stringValue(value, "");
  const name = text.split("/").pop() ?? text;
  return name.replace(/\.json$/i, "");
}

export function vectorValue(value: unknown, index: number, fallback = 0): number {
  return Array.isArray(value) ? numberValue(value[index], fallback) : fallback;
}

export function numberValue(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export function valueAt(root: unknown, path: string | ScenarioPath): unknown {
  const segments = normalizePath(path);
  let cursor: unknown = root;
  for (const segment of segments) {
    if (typeof segment === "number") {
      if (!Array.isArray(cursor)) {
        return undefined;
      }
      cursor = cursor[segment];
    } else {
      if (!isRecord(cursor)) {
        return undefined;
      }
      cursor = cursor[segment];
    }
  }
  return cursor;
}

export function objectAt(root: JsonObject, path: string | ScenarioPath): JsonObject {
  const existing = valueAt(root, path);
  if (isRecord(existing)) {
    return existing;
  }
  const replacement: JsonObject = {};
  setValueAt(root, path, replacement);
  return replacement;
}

export function listAt(root: JsonObject, path: string | ScenarioPath): unknown[] {
  return ensureListAt(root, path);
}

export function setValueAt(root: unknown, path: string | ScenarioPath, value: unknown): void {
  const segments = normalizePath(path);
  if (!segments.length || !isContainer(root)) {
    return;
  }
  let cursor: unknown = root;
  segments.slice(0, -1).forEach((segment, index) => {
    const nextSegment = segments[index + 1];
    const shouldBeArray = typeof nextSegment === "number";
    if (Array.isArray(cursor)) {
      const arrayIndex = typeof segment === "number" ? segment : Number(segment);
      if (!isContainer(cursor[arrayIndex])) {
        cursor[arrayIndex] = shouldBeArray ? [] : {};
      }
      cursor = cursor[arrayIndex];
      return;
    }
    if (isRecord(cursor)) {
      const key = String(segment);
      if (!isContainer(cursor[key])) {
        cursor[key] = shouldBeArray ? [] : {};
      }
      cursor = cursor[key];
    }
  });
  const leaf = segments[segments.length - 1];
  if (Array.isArray(cursor)) {
    cursor[typeof leaf === "number" ? leaf : Number(leaf)] = value;
  } else if (isRecord(cursor)) {
    cursor[String(leaf)] = value;
  }
}

function objectAtReadonly(root: unknown, path: string | ScenarioPath): JsonObject {
  const value = valueAt(root, path);
  return isRecord(value) ? value : {};
}

function listAtReadonly(root: unknown, path: string | ScenarioPath): unknown[] {
  const value = valueAt(root, path);
  return Array.isArray(value) ? value : [];
}

function ensureListAt(root: unknown, path: string | ScenarioPath): unknown[] {
  const existing = valueAt(root, path);
  if (Array.isArray(existing)) {
    return existing;
  }
  const replacement: unknown[] = [];
  setValueAt(root, path, replacement);
  return replacement;
}

function normalizePath(path: string | ScenarioPath): ScenarioPath {
  if (Array.isArray(path)) {
    return path;
  }
  if (!path) {
    return [];
  }
  const segments: ScenarioPath = [];
  path.split(".").forEach((part) => {
    const pattern = /([^[\]]+)|\[(\d+)\]/g;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(part)) !== null) {
      if (match[1]) {
        segments.push(match[1]);
      } else if (match[2]) {
        segments.push(Number(match[2]));
      }
    }
  });
  return segments;
}

function duplicateWithFreshId(value: JsonObject): JsonObject {
  const next = deepClone(value);
  if (isNonEmptyString(next.id)) {
    next.id = `${next.id}_copy`;
  }
  if (isNonEmptyString(next.label)) {
    next.label = `${next.label} copy`;
  }
  return next;
}

function deepClone<T>(value: T): T {
  if (value === undefined || value === null) {
    return value;
  }
  return JSON.parse(JSON.stringify(value)) as T;
}

function addWarning(rows: ScenarioWarningRow[], severity: ScenarioWarningSeverity, section: ScenarioSectionId, message: string, path: string): void {
  rows.push({ severity, section, message, path });
}

function warnVector(rows: ScenarioWarningRow[], value: unknown, section: ScenarioSectionId, message: string, path: string): void {
  if (!isVector3(value)) {
    addWarning(rows, "warning", section, message, path);
  }
}

function vectorMagnitude(value: unknown): number {
  if (!Array.isArray(value)) {
    return 0;
  }
  return Math.sqrt(value.slice(0, 3).reduce((sum, item) => sum + numberValue(item, 0) ** 2, 0));
}

function isVector3(value: unknown): boolean {
  return Array.isArray(value) && value.length >= 3 && value.slice(0, 3).every(isFiniteNumber);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isRecord(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isContainer(value: unknown): value is JsonObject | unknown[] {
  return isRecord(value) || Array.isArray(value);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
