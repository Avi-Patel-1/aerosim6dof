import {
  FileText,
  Loader2,
  Navigation as NavigationIcon,
  Play,
  RadioTower,
  Route,
  Satellite,
  TriangleAlert
} from "lucide-react";
import { useMemo, useState, type CSSProperties } from "react";
import type { ActionResult, ArtifactRef, NavigationTelemetry, RunSummary, TelemetrySeries } from "../types";

export type EstimationActionPayload = {
  action: string;
  params: Record<string, unknown>;
  runId: string;
  label: string;
};

export type EstimationPanelProps = {
  runs: RunSummary[];
  results?: ActionResult[];
  busyAction?: string | null;
  selectedRunId?: string;
  telemetry?: TelemetrySeries | null;
  navigation?: NavigationTelemetry | null;
  estimationAction?: string;
  onRunChange?: (runId: string) => void;
  onRunAction?: (payload: EstimationActionPayload) => void | Promise<void>;
};

type Row = Record<string, unknown>;

type SummaryRow = {
  label: string;
  truth: string;
  sensor: string;
  estimate: string;
  residual: string;
};

type SensorComparisonRow = {
  id: string;
  sensor: string;
  channel: string;
  health: string;
  residual: string;
  source: string;
};

type SensorDefinition = {
  id: string;
  sensor: string;
  channel: string;
  validKey?: string;
  validMetricKey?: string;
  metricKeys: string[];
  measuredGroups?: string[][];
  truthGroups?: string[][];
  measuredKey?: string;
  truthKey?: string;
  unit: string;
};

const DEFAULT_ESTIMATION_ACTION = "estimation_report";
const ESTIMATION_ACTION_MATCHERS = ["estimation", "estimate", "navigation", "nav", "sensor_report"];

const SENSOR_DEFINITIONS: SensorDefinition[] = [
  {
    id: "gnss-position",
    sensor: "GNSS Position",
    channel: "gps_x/y/z",
    validKey: "gps_valid",
    validMetricKey: "gps_valid_fraction",
    metricKeys: ["gnss_position_error_m", "gps_position_rmse_m"],
    measuredGroups: [
      ["sensor_gnss_x_m", "sensor_gnss_y_m", "sensor_gnss_z_m"],
      ["sensor_gps_x_m", "sensor_gps_y_m", "sensor_gps_z_m"],
      ["gps_x_m", "gps_y_m", "gps_z_m"]
    ],
    truthGroups: [
      ["truth_x_m", "truth_y_m", "truth_z_m"],
      ["x_m", "y_m", "altitude_m"],
      ["x_m", "y_m", "z_m"]
    ],
    unit: "m"
  },
  {
    id: "gnss-velocity",
    sensor: "GNSS Velocity",
    channel: "gps_vx/vy/vz",
    validKey: "gps_valid",
    validMetricKey: "gps_valid_fraction",
    metricKeys: ["gnss_velocity_error_mps", "gps_velocity_rmse_mps"],
    measuredGroups: [
      ["sensor_gnss_vx_mps", "sensor_gnss_vy_mps", "sensor_gnss_vz_mps"],
      ["sensor_gps_vx_mps", "sensor_gps_vy_mps", "sensor_gps_vz_mps"],
      ["gps_vx_mps", "gps_vy_mps", "gps_vz_mps"]
    ],
    truthGroups: [
      ["truth_vx_mps", "truth_vy_mps", "truth_vz_mps"],
      ["vx_mps", "vy_mps", "vz_mps"]
    ],
    unit: "m/s"
  },
  {
    id: "barometer",
    sensor: "Barometer",
    channel: "baro_alt_m",
    validKey: "baro_valid",
    validMetricKey: "barometer_valid_fraction",
    metricKeys: ["baro_altitude_residual_m", "barometer_altitude_rmse_m"],
    measuredKey: "sensor_baro_alt_m",
    truthKey: "altitude_m",
    unit: "m"
  },
  {
    id: "pitot",
    sensor: "Pitot",
    channel: "pitot_airspeed_mps",
    validKey: "pitot_valid",
    validMetricKey: "pitot_valid_fraction",
    metricKeys: ["pitot_airspeed_residual_mps", "pitot_airspeed_rmse_mps"],
    measuredKey: "sensor_pitot_airspeed_mps",
    truthKey: "truth_airspeed_mps",
    unit: "m/s"
  },
  {
    id: "radar",
    sensor: "Radar Altimeter",
    channel: "radar_agl_m",
    validKey: "radar_valid",
    validMetricKey: "radar_valid_fraction",
    metricKeys: ["radar_altitude_residual_m", "radar_agl_rmse_m_flat_terrain"],
    measuredKey: "sensor_radar_agl_m",
    truthKey: "truth_z_m",
    unit: "m"
  },
  {
    id: "horizon",
    sensor: "Horizon",
    channel: "horizon_pitch_deg",
    validKey: "horizon_valid",
    validMetricKey: "horizon_valid_fraction",
    metricKeys: ["horizon_pitch_rmse_deg"],
    measuredKey: "horizon_pitch_deg",
    truthKey: "pitch_deg",
    unit: "deg"
  }
];

function isRecord(value: unknown): value is Row {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteNumber(value: unknown): number | null {
  if (typeof value !== "number" && typeof value !== "string") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatMetric(value: unknown, unit = "", digits = 1): string {
  const number = finiteNumber(value);
  if (number === null) {
    return "-";
  }
  const suffix = unit ? ` ${unit}` : "";
  return `${number.toFixed(digits)}${suffix}`;
}

function formatSigned(value: number | null, unit = "", digits = 1): string {
  if (value === null) {
    return "-";
  }
  const suffix = unit ? ` ${unit}` : "";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}${suffix}`;
}

function formatPercent(value: unknown): string {
  const number = finiteNumber(value);
  return number === null ? "-" : `${Math.round(Math.max(0, Math.min(1, number)) * 100)}%`;
}

function percentWidth(value: unknown): string {
  const number = finiteNumber(value);
  return number === null ? "0%" : `${Math.round(Math.max(0, Math.min(1, number)) * 100)}%`;
}

function numberFrom(row: Row | undefined, keys: string[]): number | null {
  if (!row) {
    return null;
  }
  for (const key of keys) {
    const value = finiteNumber(row[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function vectorFrom(row: Row | undefined, groups: string[][]): [number, number, number] | null {
  if (!row) {
    return null;
  }
  for (const group of groups) {
    const values = group.map((key) => finiteNumber(row[key]));
    if (values.every((value): value is number => value !== null)) {
      return [values[0], values[1], values[2]];
    }
  }
  return null;
}

function magnitude(vector: [number, number, number] | null): number | null {
  return vector === null ? null : Math.hypot(vector[0], vector[1], vector[2]);
}

function delta(a: number | null, b: number | null): number | null {
  return a === null || b === null ? null : a - b;
}

function finiteValues(rows: Row[], key: string): number[] {
  return rows.map((row) => finiteNumber(row[key])).filter((value): value is number => value !== null);
}

function mean(values: number[]): number | null {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
}

function rmse(values: number[]): number | null {
  return values.length ? Math.sqrt(values.reduce((total, value) => total + value * value, 0) / values.length) : null;
}

function lastFinite(rows: Row[], key: string): number | null {
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    const value = finiteNumber(rows[index][key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function fractionFromRows(rows: Row[], key: string): number | null {
  const values = finiteValues(rows, key);
  return values.length ? values.filter((value) => value > 0.5).length / values.length : null;
}

function maxValue(values: number[]): number | null {
  return values.length ? Math.max(...values) : null;
}

function metricFromData(data: Row | undefined, keys: string[]): number | null {
  if (!data) {
    return null;
  }
  for (const key of keys) {
    const value = finiteNumber(data[key]);
    if (value !== null) {
      return value;
    }
    const metrics = isRecord(data.metrics) ? data.metrics : {};
    const metric = isRecord(metrics[key]) ? metrics[key] : null;
    if (metric) {
      for (const field of ["rmse", "current", "mean", "max", "min"]) {
        const nested = finiteNumber(metric[field]);
        if (nested !== null) {
          return nested;
        }
      }
    }
  }
  return null;
}

function qualityMetricFromData(data: Row | undefined, sensor: string, key: string): number | null {
  if (!data) {
    return null;
  }
  const quality = isRecord(data.quality) ? data.quality : {};
  const sensorQuality = isRecord(quality[sensor]) ? quality[sensor] : {};
  return finiteNumber(sensorQuality[key]);
}

function vectorErrorRmse(rows: Row[], measuredGroups: string[][], truthGroups: string[][]): number | null {
  const errors = rows
    .map((row) => {
      const measured = vectorFrom(row, measuredGroups);
      const truth = vectorFrom(row, truthGroups);
      if (!measured || !truth) {
        return null;
      }
      return Math.hypot(measured[0] - truth[0], measured[1] - truth[1], measured[2] - truth[2]);
    })
    .filter((value): value is number => value !== null);
  return rmse(errors);
}

function scalarRmse(rows: Row[], measuredKey: string, truthKey: string): number | null {
  const errors = rows
    .map((row) => {
      const measured = finiteNumber(row[measuredKey]);
      const truth = finiteNumber(row[truthKey]);
      return measured === null || truth === null ? null : measured - truth;
    })
    .filter((value): value is number => value !== null);
  return rmse(errors);
}

function runLabel(run: RunSummary): string {
  const id = run.id.replaceAll("~", " / ");
  return `${run.scenario} / ${id}`;
}

function finalRunRow(run: RunSummary | undefined): Row {
  const summary = isRecord(run?.summary) ? run.summary : {};
  const final = isRecord(summary.final) ? summary.final : {};
  return { ...summary, ...final };
}

function actionLooksEstimationRelated(action: string): boolean {
  const normalized = action.toLowerCase().replaceAll("-", "_");
  return ESTIMATION_ACTION_MATCHERS.some((matcher) => normalized.includes(matcher));
}

function latestRelatedResult(results: ActionResult[], action: string): ActionResult | undefined {
  return results.find((result) => result.action === action) ?? results.find((result) => actionLooksEstimationRelated(result.action));
}

function uniqueArtifacts(artifacts: ArtifactRef[]): ArtifactRef[] {
  const seen = new Set<string>();
  const unique: ArtifactRef[] = [];
  for (const artifact of artifacts) {
    const key = artifact.url || artifact.path || artifact.name;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(artifact);
    }
  }
  return unique;
}

function artifactLooksEstimationRelated(artifact: ArtifactRef): boolean {
  const text = `${artifact.name} ${artifact.path} ${artifact.kind}`.toLowerCase();
  return /(estimat|navigation|nav|gnss|gps|sensor|residual|filter|report|metric)/.test(text);
}

function rowSourceLabel(rows: Row[], navigation: NavigationTelemetry | null | undefined, telemetry: TelemetrySeries | null | undefined): string {
  if (navigation?.rows.length) {
    const source = isRecord(navigation.summary) ? navigation.summary.source : null;
    return typeof source === "string" ? source.replaceAll("_", " + ") : "navigation endpoint";
  }
  if (telemetry?.history.length) {
    return "telemetry rows";
  }
  return rows.length ? "computed rows" : "not loaded";
}

function speedFromTruth(row: Row | undefined): number | null {
  return numberFrom(row, ["truth_speed_mps", "speed_mps"]) ?? magnitude(vectorFrom(row, [["truth_vx_mps", "truth_vy_mps", "truth_vz_mps"], ["vx_mps", "vy_mps", "vz_mps"]]));
}

function speedFromSensor(row: Row | undefined): number | null {
  return (
    numberFrom(row, ["sensor_gps_speed_mps", "gps_speed_mps", "sensor_pitot_airspeed_mps", "pitot_airspeed_mps"]) ??
    magnitude(
      vectorFrom(row, [
        ["sensor_gnss_vx_mps", "sensor_gnss_vy_mps", "sensor_gnss_vz_mps"],
        ["sensor_gps_vx_mps", "sensor_gps_vy_mps", "sensor_gps_vz_mps"],
        ["gps_vx_mps", "gps_vy_mps", "gps_vz_mps"]
      ])
    )
  );
}

function speedFromEstimate(row: Row | undefined): number | null {
  return numberFrom(row, ["estimate_speed_mps"]) ?? magnitude(vectorFrom(row, [["estimate_vx_mps", "estimate_vy_mps", "estimate_vz_mps"]]));
}

function buildSummaryRows(rows: Row[], run: RunSummary | undefined): SummaryRow[] {
  const finalRow = rows[rows.length - 1] ?? finalRunRow(run);
  const truthAltitude = numberFrom(finalRow, ["truth_z_m", "truth_altitude_m", "altitude_m", "z_m"]);
  const sensorAltitude = numberFrom(finalRow, ["sensor_gnss_z_m", "sensor_gps_z_m", "gps_z_m", "sensor_baro_alt_m", "baro_alt_m"]);
  const estimateAltitude = numberFrom(finalRow, ["estimate_altitude_m", "estimate_z_m"]);
  const truthSpeed = speedFromTruth(finalRow);
  const sensorSpeed = speedFromSensor(finalRow);
  const estimateSpeed = speedFromEstimate(finalRow);
  const gpsPositionError = numberFrom(finalRow, ["gps_position_error_m"]);
  const estimatePositionError = numberFrom(finalRow, ["estimate_position_error_m", "position_error_m"]);
  const gpsVelocityError = numberFrom(finalRow, ["gps_velocity_error_mps"]);
  const estimateVelocityError = numberFrom(finalRow, ["estimate_velocity_error_mps", "velocity_error_mps"]);

  return [
    {
      label: "Altitude",
      truth: formatMetric(truthAltitude, "m", 1),
      sensor: formatMetric(sensorAltitude, "m", 1),
      estimate: formatMetric(estimateAltitude, "m", 1),
      residual: formatSigned(delta(estimateAltitude, truthAltitude), "m", 1)
    },
    {
      label: "Speed",
      truth: formatMetric(truthSpeed, "m/s", 1),
      sensor: formatMetric(sensorSpeed, "m/s", 1),
      estimate: formatMetric(estimateSpeed, "m/s", 1),
      residual: formatSigned(delta(estimateSpeed, truthSpeed), "m/s", 1)
    },
    {
      label: "Position Error",
      truth: "reference",
      sensor: formatMetric(gpsPositionError, "m", 2),
      estimate: formatMetric(estimatePositionError, "m", 2),
      residual: formatSigned(delta(estimatePositionError, gpsPositionError), "m", 2)
    },
    {
      label: "Velocity Error",
      truth: "reference",
      sensor: formatMetric(gpsVelocityError, "m/s", 2),
      estimate: formatMetric(estimateVelocityError, "m/s", 2),
      residual: formatSigned(delta(estimateVelocityError, gpsVelocityError), "m/s", 2)
    }
  ];
}

function buildSensorRows(rows: Row[], resultData: Row | undefined): SensorComparisonRow[] {
  return SENSOR_DEFINITIONS.map((definition) => {
    const validFraction =
      (definition.id.startsWith("gnss") ? qualityMetricFromData(resultData, "gnss", "valid_fraction") : null) ??
      metricFromData(resultData, definition.validMetricKey ? [definition.validMetricKey] : []) ??
      (definition.validKey ? fractionFromRows(rows, definition.validKey) : null);
    const residual =
      metricFromData(resultData, definition.metricKeys) ??
      (definition.measuredGroups && definition.truthGroups ? vectorErrorRmse(rows, definition.measuredGroups, definition.truthGroups) : null) ??
      (definition.measuredKey && definition.truthKey ? scalarRmse(rows, definition.measuredKey, definition.truthKey) : null);

    return {
      id: definition.id,
      sensor: definition.sensor,
      channel: definition.channel,
      health: validFraction === null ? (residual === null ? "-" : "observed") : formatPercent(validFraction),
      residual: formatMetric(residual, definition.unit, definition.unit === "deg" ? 1 : 2),
      source: residual === null ? "-" : metricFromData(resultData, definition.metricKeys) === null ? "rows" : "report"
    };
  });
}

function qualityClass(value: number | null): string {
  if (value === null) {
    return "validation-state";
  }
  if (value >= 0.72) {
    return "validation-state ok";
  }
  if (value <= 0.35) {
    return "validation-state bad";
  }
  return "validation-state";
}

export function EstimationPanel({
  runs,
  results = [],
  busyAction,
  selectedRunId,
  telemetry,
  navigation,
  estimationAction = DEFAULT_ESTIMATION_ACTION,
  onRunChange,
  onRunAction
}: EstimationPanelProps) {
  const [localBusy, setLocalBusy] = useState(false);
  const effectiveRunId = selectedRunId || navigation?.run_id || telemetry?.run_id || runs[0]?.id || "";
  const selectedRun = runs.find((run) => run.id === effectiveRunId) ?? runs[0];
  const navigationForRun = navigation && (!effectiveRunId || navigation.run_id === effectiveRunId) ? navigation : null;
  const telemetryForRun = telemetry && (!effectiveRunId || telemetry.run_id === effectiveRunId) ? telemetry : null;
  const rows = useMemo<Row[]>(
    () => (navigationForRun?.rows.length ? navigationForRun.rows : telemetryForRun?.history ?? []),
    [navigationForRun, telemetryForRun]
  );
  const latestResult = useMemo(() => latestRelatedResult(results, estimationAction), [estimationAction, results]);
  const resultData = isRecord(latestResult?.data) ? latestResult?.data : undefined;
  const summaryRows = useMemo(() => buildSummaryRows(rows, selectedRun), [rows, selectedRun]);
  const sensorRows = useMemo(() => buildSensorRows(rows, resultData), [rows, resultData]);
  const navigationSummary = navigationForRun && isRecord(navigationForRun.summary) ? navigationForRun.summary : undefined;
  const positionErrors = finiteValues(rows, "estimate_position_error_m");
  const velocityErrors = finiteValues(rows, "estimate_velocity_error_mps");
  const gpsPositionErrors = finiteValues(rows, "gps_position_error_m");
  const qualityMean =
    metricFromData(navigationSummary, ["gnss_quality_mean"]) ??
    qualityMetricFromData(resultData, "gnss", "quality_mean") ??
    mean(finiteValues(rows, "gnss_quality_score")) ??
    mean(finiteValues(rows, "gnss_quality"));
  const qualityFinal = lastFinite(rows, "gnss_quality_score") ?? lastFinite(rows, "gnss_quality");
  const validFraction =
    metricFromData(navigationSummary, ["gps_valid_fraction"]) ??
    qualityMetricFromData(resultData, "gnss", "valid_fraction") ??
    fractionFromRows(rows, "gnss_available") ??
    fractionFromRows(rows, "gps_valid");
  const updateFraction = mean(finiteValues(rows, "estimate_gnss_used")) ?? mean(finiteValues(rows, "gnss_used"));
  const relatedArtifacts = uniqueArtifacts([...(latestResult?.artifacts ?? []), ...((selectedRun?.artifacts ?? []).filter(artifactLooksEstimationRelated))]).slice(0, 8);
  const running = localBusy || busyAction === estimationAction;
  const runDisabled = !effectiveRunId || !onRunAction || running;
  const rowCount = rows.length || metricFromData(navigationSummary, ["row_count"]) || telemetry?.sample_count || 0;
  const dataSource = rowSourceLabel(rows, navigationForRun, telemetryForRun);

  const runReport = async () => {
    if (runDisabled || !onRunAction) {
      return;
    }
    setLocalBusy(true);
    try {
      await onRunAction({
        action: estimationAction,
        params: { run_id: effectiveRunId },
        runId: effectiveRunId,
        label: "Estimation Report"
      });
    } finally {
      setLocalBusy(false);
    }
  };

  return (
    <section className="scenario-builder-v2 estimation-panel" aria-label="Estimation and navigation panel">
      <div className="section-row" style={styles.headerRow}>
        <div>
          <p className="eyebrow">Estimation / Nav</p>
          <h3 style={styles.title}>Truth, sensors, and filter estimate.</h3>
          <p className="scenario-builder-v2-hint">
            {rowCount ? `${rowCount} rows from ${dataSource}` : "Navigation rows are not loaded yet; artifact and result context remain available."}
          </p>
        </div>
        <label className="field" style={styles.runField}>
          <span>Run</span>
          <select value={effectiveRunId} onChange={(event) => onRunChange?.(event.target.value)} disabled={!onRunChange || !runs.length}>
            {!runs.length && <option value={effectiveRunId}>{effectiveRunId || "No runs"}</option>}
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {runLabel(run)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="estimation-panel-layout" style={styles.layout}>
        <section className="builder-section" style={styles.mainSection}>
          <div className="section-row">
            <div>
              <p className="eyebrow">State Comparison</p>
              <h3>Truth vs Sensor vs Estimate</h3>
            </div>
            <span className={qualityClass(qualityMean)}>
              <Satellite size={15} />
              {formatPercent(qualityMean)} quality
            </span>
          </div>

          <div style={styles.tableShell}>
            <div style={{ ...styles.comparisonRow, ...styles.comparisonHeader }}>
              <span>Signal</span>
              <span>Truth</span>
              <span>Sensor</span>
              <span>Estimate</span>
              <span>Residual</span>
            </div>
            {summaryRows.map((row) => (
              <div key={row.label} style={styles.comparisonRow}>
                <strong>{row.label}</strong>
                <span>{row.truth}</span>
                <span>{row.sensor}</span>
                <span>{row.estimate}</span>
                <span>{row.residual}</span>
              </div>
            ))}
          </div>

          <div className="metric-grid">
            <div>
              <span>Estimate pos RMSE</span>
              <strong>{formatMetric(rmse(positionErrors), "m", 2)}</strong>
            </div>
            <div>
              <span>GNSS pos RMSE</span>
              <strong>{formatMetric(rmse(gpsPositionErrors) ?? metricFromData(resultData, ["gps_position_rmse_m"]), "m", 2)}</strong>
            </div>
            <div>
              <span>Velocity RMSE</span>
              <strong>{formatMetric(rmse(velocityErrors), "m/s", 2)}</strong>
            </div>
            <div>
              <span>Max pos residual</span>
              <strong>{formatMetric(metricFromData(navigationSummary, ["max_estimate_position_error_m"]) ?? maxValue(positionErrors), "m", 2)}</strong>
            </div>
          </div>

          <section className="builder-section" style={styles.sensorSection}>
            <div className="section-row">
              <div>
                <p className="eyebrow">Sensor Comparison</p>
                <h3>Residual Rows</h3>
              </div>
              <span className="validation-state">
                <RadioTower size={15} />
                {sensorRows.filter((row) => row.residual !== "-").length}/{sensorRows.length}
              </span>
            </div>
            <div style={styles.sensorList}>
              {sensorRows.map((row) => (
                <div key={row.id} style={styles.sensorRow}>
                  <div>
                    <strong>{row.sensor}</strong>
                    <p>{row.channel}</p>
                  </div>
                  <span>{row.health}</span>
                  <span>{row.residual}</span>
                  <small>{row.source}</small>
                </div>
              ))}
            </div>
          </section>
        </section>

        <aside className="report-panel" style={styles.aside}>
          <div className="action-card-title">
            <span>
              <NavigationIcon size={17} />
            </span>
            <h3>Nav Quality</h3>
          </div>

          <div style={styles.qualityStack}>
            <div className="scenario-builder-v2-meter" aria-label="Mean GNSS quality">
              <span style={{ width: percentWidth(qualityMean) }} />
            </div>
            <div style={styles.qualityGrid}>
              <div>
                <span>Mean quality</span>
                <strong>{formatPercent(qualityMean)}</strong>
              </div>
              <div>
                <span>Final quality</span>
                <strong>{formatPercent(qualityFinal)}</strong>
              </div>
              <div>
                <span>GNSS valid</span>
                <strong>{formatPercent(validFraction)}</strong>
              </div>
              <div>
                <span>Updates used</span>
                <strong>{formatPercent(updateFraction)}</strong>
              </div>
            </div>
          </div>

          <div className="scenario-explain">
            <strong>Residual metrics</strong>
            <p>
              Position sigma {formatMetric(lastFinite(rows, "position_sigma_m"), "m", 2)} / velocity sigma{" "}
              {formatMetric(lastFinite(rows, "velocity_sigma_mps"), "m/s", 2)}
            </p>
            <p>
              Covariance trace {formatMetric(lastFinite(rows, "covariance_trace"), "", 2)} / source {dataSource}
            </p>
          </div>

          <div className="scenario-builder-v2-runbar editor-actions section-row" style={styles.runbar}>
            <div className="telemetry-ops-runmeta">
              <Route size={16} />
              <span>{estimationAction}</span>
              <strong>{effectiveRunId || "no run"}</strong>
            </div>
            <button className="primary-action" type="button" onClick={runReport} disabled={runDisabled}>
              {running ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
              Report
            </button>
          </div>

          <div className="scenario-explain">
            <strong>Latest result</strong>
            {latestResult ? (
              <>
                <p>
                  <FileText size={14} /> {latestResult.action.replaceAll("_", " ")} / {latestResult.status}
                </p>
                {latestResult.message && <p>{latestResult.message}</p>}
              </>
            ) : (
              <p>No estimation result yet.</p>
            )}
          </div>

          <div>
            <div className="section-row" style={styles.artifactHeader}>
              <strong>Artifacts</strong>
              <span className="scenario-builder-v2-hint">{relatedArtifacts.length}</span>
            </div>
            {relatedArtifacts.length ? (
              <div className="artifact-links spacious" style={styles.artifacts}>
                {relatedArtifacts.map((artifact) => (
                  <a key={artifact.path || artifact.url || artifact.name} href={artifact.url} target="_blank" rel="noreferrer">
                    {artifact.name}
                  </a>
                ))}
              </div>
            ) : (
              <div className="empty-state" style={styles.emptyState}>
                <TriangleAlert size={16} />
                No nav artifacts linked.
              </div>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  headerRow: {
    alignItems: "end"
  },
  title: {
    fontSize: "1.75rem"
  },
  runField: {
    minWidth: 260,
    width: "min(100%, 360px)"
  },
  layout: {
    display: "grid",
    gap: 30,
    alignItems: "start"
  },
  mainSection: {
    minWidth: 0
  },
  tableShell: {
    minWidth: 0,
    overflowX: "auto",
    borderTop: "1px solid rgba(112, 112, 125, 0.42)"
  },
  comparisonRow: {
    minWidth: 650,
    display: "grid",
    gridTemplateColumns: "minmax(130px, 1fr) repeat(4, minmax(96px, 0.72fr))",
    gap: 12,
    alignItems: "center",
    borderBottom: "1px solid rgba(112, 112, 125, 0.35)",
    padding: "14px 0",
    color: "var(--color-silver)"
  },
  comparisonHeader: {
    minHeight: 42,
    color: "var(--color-starlight)",
    fontSize: "0.78rem",
    textTransform: "uppercase"
  },
  sensorSection: {
    paddingTop: 14
  },
  sensorList: {
    display: "grid",
    overflowX: "auto",
    borderTop: "1px solid rgba(112, 112, 125, 0.42)"
  },
  sensorRow: {
    minWidth: 430,
    display: "grid",
    gridTemplateColumns: "minmax(160px, 1fr) 72px minmax(82px, 0.5fr) 64px",
    gap: 14,
    alignItems: "center",
    borderBottom: "1px solid rgba(112, 112, 125, 0.35)",
    padding: "14px 0",
    color: "var(--color-silver)"
  },
  aside: {
    minWidth: 0
  },
  qualityStack: {
    display: "grid",
    gap: 14
  },
  qualityGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 12
  },
  runbar: {
    position: "static",
    paddingTop: 14
  },
  artifactHeader: {
    alignItems: "center",
    marginBottom: 12
  },
  artifacts: {
    alignItems: "flex-start"
  },
  emptyState: {
    minHeight: 72
  },
};
