import { BarChart3, Boxes, Loader2, Play, Route, SlidersHorizontal, Sparkles, Target } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { ActionResult, ConfigSummary, ScenarioSummary } from "../types";

export type TradeSpaceMode = "parameter_sweep" | "robustness" | "campaign";
export type TradeSpaceActionName = "trade_space";
export type TradeSpaceObjectiveMetric =
  | "miss_distance_m"
  | "final_altitude_m"
  | "max_qbar_pa"
  | "max_load_factor_g"
  | "robustness_margin";
export type TradeSpaceObjectiveGoal = "maximize" | "minimize";

export type TradeSpaceObjective = {
  metric: TradeSpaceObjectiveMetric;
  goal: TradeSpaceObjectiveGoal;
};

export type TradeSpaceConstraint = {
  metric: TradeSpaceObjectiveMetric;
  label: string;
  operator: "<=" | ">=";
  value: number | null;
  unit: string;
};

export type TradeSpaceActionPayload = {
  mode: TradeSpaceMode;
  action: TradeSpaceActionName;
  params: Record<string, unknown>;
  objective: TradeSpaceObjective;
  constraints: TradeSpaceConstraint[];
  estimatedRuns: number;
  label: string;
};

export type TradeSpaceValidation = {
  valid: boolean;
  errors: string[];
  warnings: string[];
  estimatedRuns: number;
};

export type TradeSpacePanelProps = {
  scenarios: ScenarioSummary[];
  vehicles?: ConfigSummary[];
  selectedScenarioId?: string;
  selectedVehicleId?: string;
  busyAction?: string | null;
  results?: ActionResult[];
  onScenarioChange?: (scenarioId: string) => void;
  onVehicleChange?: (vehicleId: string) => void;
  onPlanChange?: (payload: TradeSpaceActionPayload, validation: TradeSpaceValidation) => void;
  onRunTrade?: (payload: TradeSpaceActionPayload) => void | Promise<void>;
};

type FieldProps = {
  label: string;
  children: ReactNode;
};

type ModeDefinition = {
  id: TradeSpaceMode;
  label: string;
  action: TradeSpaceActionName;
  icon: ReactNode;
  summary: string;
};

type MetricDefinition = {
  label: string;
  unit: string;
  defaultGoal: TradeSpaceObjectiveGoal;
};

type TradeSpacePoint = {
  label: string;
  metrics: Partial<Record<TradeSpaceObjectiveMetric, number>>;
  feasible: boolean;
};

const MODE_DEFINITIONS: ModeDefinition[] = [
  {
    id: "parameter_sweep",
    label: "Parameter Sweep",
    action: "trade_space",
    icon: <SlidersHorizontal size={16} />,
    summary: "Rank candidate scenario variables through the 6DOF engine"
  },
  {
    id: "robustness",
    label: "Robustness",
    action: "trade_space",
    icon: <Sparkles size={16} />,
    summary: "Seeded uncertainty samples with Pareto, reliability, UQ, sensitivity, surrogate, and optimization artifacts"
  },
  {
    id: "campaign",
    label: "Campaign",
    action: "trade_space",
    icon: <Boxes size={16} />,
    summary: "Baseline dispersion plus throttle and pitch design sweeps"
  }
];

const METRIC_DEFINITIONS: Record<TradeSpaceObjectiveMetric, MetricDefinition> = {
  miss_distance_m: { label: "Miss distance", unit: "m", defaultGoal: "minimize" },
  final_altitude_m: { label: "Final altitude", unit: "m", defaultGoal: "maximize" },
  max_qbar_pa: { label: "Max qbar", unit: "Pa", defaultGoal: "minimize" },
  max_load_factor_g: { label: "Max load", unit: "g", defaultGoal: "minimize" },
  robustness_margin: { label: "Robustness margin", unit: "", defaultGoal: "maximize" }
};

const MODE_OBJECTIVES: Record<TradeSpaceMode, TradeSpaceObjectiveMetric[]> = {
  parameter_sweep: ["final_altitude_m", "miss_distance_m", "max_qbar_pa", "max_load_factor_g", "robustness_margin"],
  robustness: ["robustness_margin", "final_altitude_m", "miss_distance_m", "max_qbar_pa", "max_load_factor_g"],
  campaign: ["robustness_margin", "final_altitude_m", "max_qbar_pa", "max_load_factor_g"]
};

const DOTTED_PATH_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$/;
const DECIMAL_VALUE_PATTERN = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

function Field({ label, children }: FieldProps) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function firstScenarioId(scenarios: ScenarioSummary[]): string {
  return scenarios.find((scenario) => scenario.id === "nominal_ascent")?.id ?? scenarios[0]?.id ?? "nominal_ascent";
}

function firstVehicleId(vehicles: ConfigSummary[]): string {
  return vehicles.find((vehicle) => vehicle.id === "baseline")?.id ?? vehicles[0]?.id ?? "baseline";
}

function scenarioOptionLabel(scenario: ScenarioSummary): string {
  return `${scenario.name} (${scenario.id})`;
}

function trimText(value: string): string {
  return value.trim();
}

function parseCsvList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseMixedValues(value: string): Array<number | string> {
  return parseCsvList(value).map((item) => (DECIMAL_VALUE_PATTERN.test(item) ? Number(item) : item));
}

function parseFinite(value: string): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function parseInteger(value: string): number | null {
  const number = Number(value);
  return Number.isInteger(number) ? number : null;
}

function metricUnit(metric: TradeSpaceObjectiveMetric): string {
  return METRIC_DEFINITIONS[metric].unit;
}

function metricLabel(metric: TradeSpaceObjectiveMetric): string {
  return METRIC_DEFINITIONS[metric].label;
}

function formatMetric(value: number | null | undefined, metric: TradeSpaceObjectiveMetric): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "-";
  }
  const unit = metricUnit(metric);
  const digits = metric === "max_qbar_pa" ? 0 : metric === "max_load_factor_g" ? 2 : 1;
  return `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function arrayOfRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(asRecord).filter((item): item is Record<string, unknown> => item !== null) : [];
}

function readNumber(record: Record<string, unknown>, key: string): number | null {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readNestedNumber(record: Record<string, unknown>, key: string, nestedKey: string): number | null {
  const nested = asRecord(record[key]);
  return nested ? readNumber(nested, nestedKey) : null;
}

function metricValue(record: Record<string, unknown>, metric: TradeSpaceObjectiveMetric): number | null {
  if (metric === "final_altitude_m") {
    return readNestedNumber(record, "final", "altitude_m") ?? readNumber(record, "final_altitude_m") ?? readNumber(record, "max_altitude_m");
  }
  return readNumber(record, metric);
}

function pointLabel(record: Record<string, unknown>, fallback: string): string {
  const explicit = record.label ?? record.scenario ?? record.run_dir ?? record.sample_index ?? record.sweep_index;
  return explicit === undefined || explicit === null ? fallback : String(explicit);
}

function allMetricValues(record: Record<string, unknown>): Partial<Record<TradeSpaceObjectiveMetric, number>> {
  const metrics: Partial<Record<TradeSpaceObjectiveMetric, number>> = {};
  for (const metric of Object.keys(METRIC_DEFINITIONS) as TradeSpaceObjectiveMetric[]) {
    const value = metricValue(record, metric);
    if (value !== null) {
      metrics[metric] = value;
    }
  }
  return metrics;
}

function satisfiesConstraints(metrics: Partial<Record<TradeSpaceObjectiveMetric, number>>, constraints: TradeSpaceConstraint[]): boolean {
  return constraints.every((constraint) => {
    if (constraint.value === null) {
      return true;
    }
    const value = metrics[constraint.metric];
    if (value === undefined) {
      return true;
    }
    return constraint.operator === "<=" ? value <= constraint.value : value >= constraint.value;
  });
}

function extractTradePoints(result: ActionResult | undefined, constraints: TradeSpaceConstraint[]): TradeSpacePoint[] {
  const data = asRecord(result?.data);
  if (!data) {
    return [];
  }
  const sourceRows = arrayOfRecords(data.ranked_preview).length
    ? arrayOfRecords(data.ranked_preview)
    : arrayOfRecords(data.pareto_preview).length
      ? arrayOfRecords(data.pareto_preview)
      : arrayOfRecords(data.runs).length
        ? arrayOfRecords(data.runs)
        : arrayOfRecords(data.rows);
  return sourceRows.map((row, index) => {
    const metrics = allMetricValues(row);
    return {
      label: pointLabel(row, `case ${index + 1}`),
      metrics,
      feasible: satisfiesConstraints(metrics, constraints)
    };
  });
}

function bestPoint(points: TradeSpacePoint[], objective: TradeSpaceObjective): TradeSpacePoint | null {
  const ranked = points
    .filter((point) => point.metrics[objective.metric] !== undefined)
    .sort((a, b) => {
      const first = a.metrics[objective.metric] ?? 0;
      const second = b.metrics[objective.metric] ?? 0;
      return objective.goal === "maximize" ? second - first : first - second;
    });
  return ranked[0] ?? null;
}

function spread(points: TradeSpacePoint[], metric: TradeSpaceObjectiveMetric): number | null {
  const values = points.map((point) => point.metrics[metric]).filter((value): value is number => value !== undefined);
  if (!values.length) {
    return null;
  }
  return Math.max(...values) - Math.min(...values);
}

function modeDefinition(mode: TradeSpaceMode): ModeDefinition {
  return MODE_DEFINITIONS.find((definition) => definition.id === mode) ?? MODE_DEFINITIONS[0];
}

function buildValidation(input: {
  mode: TradeSpaceMode;
  scenarioId: string;
  vehicleId: string;
  sweepParameter: string;
  sweepValues: string;
  sweepMaxRuns: string;
  samples: string;
  seed: string;
  massSigmaKg: string;
  windSigmaMps: string;
  qbarLimit: string;
  loadLimit: string;
}): TradeSpaceValidation {
  const errors: string[] = [];
  const warnings: string[] = [];
  let estimatedRuns = 0;

  if (!trimText(input.scenarioId)) {
    errors.push("Select a scenario.");
  }

  if (input.mode === "parameter_sweep") {
    const values = parseMixedValues(input.sweepValues);
    const maxRuns = parseInteger(input.sweepMaxRuns);
    estimatedRuns = values.length;
    if (!DOTTED_PATH_PATTERN.test(trimText(input.sweepParameter))) {
      errors.push("Use a dotted scenario parameter path.");
    }
    if (!values.length) {
      errors.push("Enter at least one candidate value.");
    }
    if (values.length === 1) {
      warnings.push("Only one candidate is listed.");
    }
    if (maxRuns === null || maxRuns < 1 || maxRuns > 100) {
      errors.push("Max runs must be an integer from 1 to 100.");
    } else if (values.length > maxRuns) {
      errors.push(`Candidate count ${values.length} is above max runs ${maxRuns}.`);
    }
  }

  if (input.mode === "robustness") {
    const sampleCount = parseInteger(input.samples);
    estimatedRuns = sampleCount ?? 0;
    if (sampleCount === null || sampleCount < 1 || sampleCount > 50) {
      errors.push("Samples must be an integer from 1 to 50.");
    }
    if (parseInteger(input.seed) === null) {
      errors.push("Seed must be an integer.");
    }
    const massSigma = parseFinite(input.massSigmaKg);
    const windSigma = parseFinite(input.windSigmaMps);
    if (massSigma === null || massSigma < 0) {
      errors.push("Mass sigma must be zero or positive.");
    }
    if (windSigma === null || windSigma < 0) {
      errors.push("Wind sigma must be zero or positive.");
    }
    if (massSigma === 0 && windSigma === 0) {
      warnings.push("Both dispersions are zero.");
    }
  }

  if (input.mode === "campaign") {
    const sampleCount = parseInteger(input.samples);
    estimatedRuns = (sampleCount ?? 0) + 6;
    if (sampleCount === null || sampleCount < 2 || sampleCount > 18) {
      errors.push("Campaign baseline samples must be an integer from 2 to 18.");
    }
    if (parseInteger(input.seed) === null) {
      errors.push("Seed must be an integer.");
    }
  }

  for (const [label, value] of [
    ["Qbar limit", input.qbarLimit],
    ["Load limit", input.loadLimit],
  ] as const) {
    if (trimText(value) && parseFinite(value) === null) {
      errors.push(`${label} must be numeric.`);
    }
  }

  return { valid: errors.length === 0, errors, warnings, estimatedRuns: Math.max(estimatedRuns, 0) };
}

function TradeSpaceChart({ points, objective }: { points: TradeSpacePoint[]; objective: TradeSpaceObjective }) {
  const chartPoints = points
    .map((point, index) => ({ point, index, value: point.metrics[objective.metric] }))
    .filter((item): item is { point: TradeSpacePoint; index: number; value: number } => item.value !== undefined);

  if (!chartPoints.length) {
    return <div className="empty-state">No numeric points for {metricLabel(objective.metric)}.</div>;
  }

  const width = 560;
  const height = 230;
  const padding = { top: 18, right: 22, bottom: 34, left: 54 };
  const values = chartPoints.map((item) => item.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || Math.max(1, Math.abs(maxValue) * 0.1);
  const yMin = minValue - range * 0.08;
  const yMax = maxValue + range * 0.08;
  const xStep = chartPoints.length > 1 ? (width - padding.left - padding.right) / (chartPoints.length - 1) : 0;
  const yScale = (value: number) => padding.top + ((yMax - value) / (yMax - yMin || 1)) * (height - padding.top - padding.bottom);
  const coordinates = chartPoints.map((item, index) => ({
    x: chartPoints.length === 1 ? (width + padding.left - padding.right) / 2 : padding.left + xStep * index,
    y: yScale(item.value),
    item
  }));
  const path = coordinates.map((coordinate, index) => `${index === 0 ? "M" : "L"} ${coordinate.x.toFixed(1)} ${coordinate.y.toFixed(1)}`).join(" ");
  const best = bestPoint(points, objective);

  return (
    <section className="chart-panel trade-space-chart" aria-label={`${metricLabel(objective.metric)} trade plot`}>
      <div className="chart-header">
        <h3>{metricLabel(objective.metric)}</h3>
        <div className="legend">
          <span>
            <i style={{ background: "var(--color-ghost-blue)" }} />
            feasible
          </span>
          <span>
            <i style={{ background: "var(--color-lead)" }} />
            constrained
          </span>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${metricLabel(objective.metric)} values by trade case`}>
        <rect x="0" y="0" width={width} height={height} className="chart-bg" />
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padding.top + ratio * (height - padding.top - padding.bottom);
          const value = yMax - ratio * (yMax - yMin);
          return (
            <g key={ratio}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="grid-line" />
              <text x="8" y={y + 4} className="axis-label">
                {formatMetric(value, objective.metric)}
              </text>
            </g>
          );
        })}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="axis" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} className="axis" />
        <path d={path} fill="none" stroke="var(--color-ghost-blue)" strokeWidth="1.8" opacity="0.78" />
        {coordinates.map(({ x, y, item }) => {
          const isBest = best?.label === item.point.label;
          return (
            <g key={`${item.point.label}-${item.index}`}>
              <circle
                cx={x}
                cy={y}
                r={isBest ? 6 : 4.5}
                fill={item.point.feasible ? "var(--color-ghost-blue)" : "var(--color-lead)"}
                stroke={isBest ? "var(--color-pure-white)" : "transparent"}
                strokeWidth="1.5"
              />
            </g>
          );
        })}
        <text x={padding.left} y={height - 10} className="axis-label">
          case 1
        </text>
        <text x={width - padding.right - 54} y={height - 10} className="axis-label">
          case {chartPoints.length}
        </text>
      </svg>
    </section>
  );
}

function TradeSpaceResult({
  result,
  objective,
  constraints
}: {
  result: ActionResult | undefined;
  objective: TradeSpaceObjective;
  constraints: TradeSpaceConstraint[];
}) {
  const points = useMemo(() => extractTradePoints(result, constraints), [constraints, result]);
  const best = bestPoint(points, objective);
  const feasibleCount = points.filter((point) => point.feasible).length;
  const metricSpread = spread(points, objective.metric);
  const ranked = [...points]
    .filter((point) => point.metrics[objective.metric] !== undefined)
    .sort((a, b) => {
      const first = a.metrics[objective.metric] ?? 0;
      const second = b.metrics[objective.metric] ?? 0;
      return objective.goal === "maximize" ? second - first : first - second;
    });

  if (!result) {
    return <div className="empty-state">No trade output loaded.</div>;
  }

  return (
    <section className="builder-section trade-space-result" aria-label="Trade space result summary">
      <div className="section-row">
        <div>
          <p className="eyebrow">Latest Result</p>
          <h3>{result.action.replaceAll("_", " ")}</h3>
        </div>
        <span className={`validation-state ${result.status === "completed" ? "ok" : "bad"}`}>{result.status}</span>
      </div>

      <div className="metric-grid">
        <div>
          <span>Cases</span>
          <strong>{points.length || "-"}</strong>
        </div>
        <div>
          <span>Feasible</span>
          <strong>{points.length ? feasibleCount : "-"}</strong>
        </div>
        <div>
          <span>Best</span>
          <strong>{best ? formatMetric(best.metrics[objective.metric], objective.metric) : "-"}</strong>
        </div>
        <div>
          <span>Spread</span>
          <strong>{formatMetric(metricSpread, objective.metric)}</strong>
        </div>
      </div>

      <TradeSpaceChart points={points} objective={objective} />

      <div className="event-list trade-space-rankings">
        {ranked.slice(0, 5).map((point, index) => (
          <div className="event-item" key={`${point.label}-${index}`}>
            <span>#{index + 1}</span>
            <strong>{point.label}</strong>
            <p>
              {formatMetric(point.metrics[objective.metric], objective.metric)}
              {point.feasible ? " / feasible" : " / constrained"}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function TradeSpacePanel({
  scenarios,
  vehicles = [],
  selectedScenarioId,
  selectedVehicleId,
  busyAction,
  results = [],
  onScenarioChange,
  onVehicleChange,
  onPlanChange,
  onRunTrade
}: TradeSpacePanelProps) {
  const [mode, setMode] = useState<TradeSpaceMode>("parameter_sweep");
  const [scenarioId, setScenarioId] = useState(selectedScenarioId ?? firstScenarioId(scenarios));
  const [vehicleId, setVehicleId] = useState(selectedVehicleId ?? firstVehicleId(vehicles));
  const [sweepParameter, setSweepParameter] = useState("guidance.throttle");
  const [sweepValues, setSweepValues] = useState("0.78,0.82,0.86,0.90");
  const [sweepMaxRuns, setSweepMaxRuns] = useState("24");
  const [samples, setSamples] = useState("12");
  const [seed, setSeed] = useState("77");
  const [massSigmaKg, setMassSigmaKg] = useState("0.2");
  const [windSigmaMps, setWindSigmaMps] = useState("0.1");
  const [objectiveMetric, setObjectiveMetric] = useState<TradeSpaceObjectiveMetric>("final_altitude_m");
  const [objectiveGoal, setObjectiveGoal] = useState<TradeSpaceObjectiveGoal>("maximize");
  const [qbarLimit, setQbarLimit] = useState("45000");
  const [loadLimit, setLoadLimit] = useState("3.0");
  const [localBusy, setLocalBusy] = useState(false);

  useEffect(() => {
    if (selectedScenarioId) {
      setScenarioId(selectedScenarioId);
    }
  }, [selectedScenarioId]);

  useEffect(() => {
    if (selectedVehicleId) {
      setVehicleId(selectedVehicleId);
    }
  }, [selectedVehicleId]);

  useEffect(() => {
    if (!selectedScenarioId && scenarios.length && !scenarios.some((scenario) => scenario.id === scenarioId)) {
      setScenarioId(firstScenarioId(scenarios));
    }
  }, [scenarioId, scenarios, selectedScenarioId]);

  useEffect(() => {
    if (!selectedVehicleId && vehicles.length && !vehicles.some((vehicle) => vehicle.id === vehicleId)) {
      setVehicleId(firstVehicleId(vehicles));
    }
  }, [selectedVehicleId, vehicleId, vehicles]);

  useEffect(() => {
    const availableMetrics = MODE_OBJECTIVES[mode];
    const nextMetric = availableMetrics.includes(objectiveMetric) ? objectiveMetric : availableMetrics[0];
    setObjectiveMetric(nextMetric);
    setObjectiveGoal(METRIC_DEFINITIONS[nextMetric].defaultGoal);
  }, [mode, objectiveMetric]);

  const validation = useMemo(
    () =>
      buildValidation({
        mode,
        scenarioId,
        vehicleId,
        sweepParameter,
        sweepValues,
        sweepMaxRuns,
        samples,
        seed,
        massSigmaKg,
        windSigmaMps,
        qbarLimit,
        loadLimit
      }),
    [loadLimit, massSigmaKg, mode, qbarLimit, samples, scenarioId, seed, sweepMaxRuns, sweepParameter, sweepValues, vehicleId, windSigmaMps]
  );

  const objective = useMemo<TradeSpaceObjective>(() => ({ metric: objectiveMetric, goal: objectiveGoal }), [objectiveGoal, objectiveMetric]);

  const constraints = useMemo<TradeSpaceConstraint[]>(() => {
    const items: TradeSpaceConstraint[] = [];
    const qbar = parseFinite(qbarLimit);
    const load = parseFinite(loadLimit);
    if (trimText(qbarLimit) && qbar !== null) {
      items.push({ metric: "max_qbar_pa", label: "Qbar", operator: "<=", value: qbar, unit: "Pa" });
    }
    if (trimText(loadLimit) && load !== null) {
      items.push({ metric: "max_load_factor_g", label: "Load", operator: "<=", value: load, unit: "g" });
    }
    return items;
  }, [loadLimit, qbarLimit]);

  const payload = useMemo<TradeSpaceActionPayload>(() => {
    const definition = modeDefinition(mode);
    if (mode === "robustness") {
      return {
        mode,
        action: "trade_space",
        params: {
          mode: "study",
          scenario_id: scenarioId,
          label: `${scenarioId} robustness`,
          samples: parseInteger(samples) ?? 1,
          seed: parseInteger(seed) ?? 77,
          mass_sigma_kg: parseFinite(massSigmaKg) ?? 0,
          wind_sigma_mps: parseFinite(windSigmaMps) ?? 0
        },
        objective,
        constraints,
        estimatedRuns: validation.estimatedRuns,
        label: `${scenarioId} robustness`
      };
    }
    if (mode === "campaign") {
      return {
        mode,
        action: "trade_space",
        params: {
          mode: "campaign",
          scenario_id: scenarioId,
          label: `${scenarioId} campaign`,
          samples: parseInteger(samples) ?? 8,
          seed: parseInteger(seed) ?? 2026
        },
        objective,
        constraints,
        estimatedRuns: validation.estimatedRuns,
        label: `${scenarioId} campaign`
      };
    }
    return {
      mode,
      action: definition.action,
      params: {
        mode: "sweep",
        scenario_id: scenarioId,
        label: `${scenarioId} ${trimText(sweepParameter) || "parameter"} sweep`,
        parameter: trimText(sweepParameter),
        values: parseMixedValues(sweepValues),
        max_runs: parseInteger(sweepMaxRuns) ?? 20
      },
      objective,
      constraints,
      estimatedRuns: validation.estimatedRuns,
      label: `${scenarioId} ${trimText(sweepParameter) || "parameter"} sweep`
    };
  }, [constraints, massSigmaKg, mode, objective, samples, scenarioId, seed, sweepMaxRuns, sweepParameter, sweepValues, validation.estimatedRuns, windSigmaMps]);

  useEffect(() => {
    onPlanChange?.(payload, validation);
  }, [onPlanChange, payload, validation]);

  const latestResult = useMemo(() => results.find((result) => result.action === payload.action), [payload.action, results]);
  const activeMode = modeDefinition(mode);
  const runDisabled = !validation.valid || localBusy || Boolean(busyAction && busyAction === payload.action) || !onRunTrade;
  const running = localBusy || Boolean(busyAction && busyAction === payload.action);
  const planJson = useMemo(() => JSON.stringify(payload, null, 2), [payload]);

  const changeScenario = (value: string) => {
    setScenarioId(value);
    onScenarioChange?.(value);
  };

  const changeVehicle = (value: string) => {
    setVehicleId(value);
    onVehicleChange?.(value);
  };

  const runTrade = async () => {
    if (runDisabled || !onRunTrade) {
      return;
    }
    setLocalBusy(true);
    try {
      await onRunTrade(payload);
    } finally {
      setLocalBusy(false);
    }
  };

  return (
    <section className="scenario-builder-v2 trade-space-panel" aria-label="Trade Space Panel">
      <div className="scenario-builder-v2-preset-bar trade-space-mode-tabs" role="tablist" aria-label="Trade space mode">
        {MODE_DEFINITIONS.map((definition) => (
          <button
            key={definition.id}
            type="button"
            role="tab"
            aria-selected={mode === definition.id}
            className={`${mode === definition.id ? "primary-action" : "secondary-action"} scenario-builder-v2-preset`}
            onClick={() => setMode(definition.id)}
          >
            {definition.icon}
            {definition.label}
          </button>
        ))}
      </div>

      <div className="scenario-builder-v2-layout editor-layout trade-space-layout">
        <section className="scenario-builder-v2-main builder-section trade-space-config">
          <div className="section-row">
            <div>
              <p className="eyebrow">Trade Space</p>
              <h3>{activeMode.label}</h3>
              <p className="scenario-builder-v2-hint">{activeMode.summary}</p>
            </div>
            <span className={`validation-state ${validation.valid ? "ok" : "bad"}`}>{validation.valid ? "Ready" : "Review"}</span>
          </div>

          <div className="guided-grid scenario-builder-v2-grid trade-space-grid">
            <Field label="Scenario">
              <select value={scenarioId} onChange={(event) => changeScenario(event.target.value)}>
                {!scenarios.length && <option value={scenarioId}>{scenarioId}</option>}
                {scenarios.map((scenario) => (
                  <option key={scenario.id} value={scenario.id}>
                    {scenarioOptionLabel(scenario)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Objective">
              <select value={objectiveMetric} onChange={(event) => setObjectiveMetric(event.target.value as TradeSpaceObjectiveMetric)}>
                {MODE_OBJECTIVES[mode].map((metric) => (
                  <option key={metric} value={metric}>
                    {metricLabel(metric)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Goal">
              <select value={objectiveGoal} onChange={(event) => setObjectiveGoal(event.target.value as TradeSpaceObjectiveGoal)}>
                <option value="maximize">Maximize</option>
                <option value="minimize">Minimize</option>
              </select>
            </Field>
          </div>

          {mode === "parameter_sweep" && (
            <div className="guided-grid scenario-builder-v2-grid trade-space-grid">
              <Field label="Parameter path">
                <input value={sweepParameter} onChange={(event) => setSweepParameter(event.target.value)} />
              </Field>
              <Field label="Candidate values">
                <input value={sweepValues} onChange={(event) => setSweepValues(event.target.value)} />
              </Field>
              <Field label="Max runs">
                <input type="number" min={1} max={100} step={1} value={sweepMaxRuns} onChange={(event) => setSweepMaxRuns(event.target.value)} />
              </Field>
            </div>
          )}

          {mode === "robustness" && (
            <div className="guided-grid scenario-builder-v2-grid trade-space-grid">
              <Field label="Samples">
                <input type="number" min={1} max={50} step={1} value={samples} onChange={(event) => setSamples(event.target.value)} />
              </Field>
              <Field label="Seed">
                <input type="number" step={1} value={seed} onChange={(event) => setSeed(event.target.value)} />
              </Field>
              <Field label="Mass sigma kg">
                <input type="number" min={0} step={0.05} value={massSigmaKg} onChange={(event) => setMassSigmaKg(event.target.value)} />
              </Field>
              <Field label="Wind sigma m/s">
                <input type="number" min={0} step={0.05} value={windSigmaMps} onChange={(event) => setWindSigmaMps(event.target.value)} />
              </Field>
            </div>
          )}

          {mode === "campaign" && (
            <div className="guided-grid scenario-builder-v2-grid trade-space-grid">
              <Field label="Baseline samples">
                <input type="number" min={2} max={18} step={1} value={samples} onChange={(event) => setSamples(event.target.value)} />
              </Field>
              <Field label="Seed">
                <input type="number" step={1} value={seed} onChange={(event) => setSeed(event.target.value)} />
              </Field>
            </div>
          )}

          <div className="guided-grid scenario-builder-v2-grid trade-space-grid">
            <Field label="Qbar limit Pa">
              <input type="number" min={0} step={500} value={qbarLimit} onChange={(event) => setQbarLimit(event.target.value)} />
            </Field>
            <Field label="Load limit g">
              <input type="number" min={0} step={0.1} value={loadLimit} onChange={(event) => setLoadLimit(event.target.value)} />
            </Field>
          </div>

          {(validation.errors.length > 0 || validation.warnings.length > 0) && (
            <div className="scenario-builder-v2-warning-panel trade-space-messages">
              {validation.errors.map((message) => (
                <p key={`error-${message}`}>
                  <Target size={14} />
                  <span>{message}</span>
                </p>
              ))}
              {validation.warnings.map((message) => (
                <p key={`warning-${message}`}>
                  <BarChart3 size={14} />
                  <span>{message}</span>
                </p>
              ))}
            </div>
          )}

          <div className="scenario-builder-v2-runbar editor-actions section-row trade-space-runbar">
            <div className="telemetry-ops-runmeta">
              <Route size={16} />
              <span>{payload.action}</span>
              <strong>{validation.estimatedRuns} planned runs</strong>
            </div>
            <button className="primary-action" type="button" onClick={runTrade} disabled={runDisabled}>
              {running ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
              Run Trade
            </button>
          </div>
        </section>

        <aside className="scenario-builder-v2-aside report-panel trade-space-aside">
          <div className="action-card-title">
            <span>
              <Target size={17} />
            </span>
            <h3>Plan</h3>
          </div>
          <div className="metric-grid">
            <div>
              <span>Action</span>
              <strong>{payload.action.replaceAll("_", " ")}</strong>
            </div>
            <div>
              <span>Runs</span>
              <strong>{payload.estimatedRuns}</strong>
            </div>
            <div>
              <span>Metric</span>
              <strong>{metricLabel(payload.objective.metric)}</strong>
            </div>
            <div>
              <span>Goal</span>
              <strong>{payload.objective.goal}</strong>
            </div>
          </div>
          <div className="scenario-explain trade-space-constraints">
            <strong>Constraints</strong>
            {constraints.length ? (
              constraints.map((constraint) => (
                <p key={constraint.metric}>
                  {constraint.label} {constraint.operator} {constraint.value}
                  {constraint.unit ? ` ${constraint.unit}` : ""}
                </p>
              ))
            ) : (
              <p>No active constraints.</p>
            )}
          </div>
          <pre className="trade-space-payload">{planJson}</pre>
        </aside>
      </div>

      <TradeSpaceResult result={latestResult} objective={objective} constraints={constraints} />
    </section>
  );
}
