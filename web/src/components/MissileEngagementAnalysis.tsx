import { Activity, Crosshair, Gauge, Loader2, RadioTower, ScanLine, ShieldAlert, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import type { MissileEngagementComparisonPacket, MissileEngagementRun, MissilePhaseInterval, MissileTimelineSample } from "../types";

type MissileEngagementAnalysisProps = {
  packet: MissileEngagementComparisonPacket | null;
  loading: boolean;
  error: string;
  selectedRunId: string;
  onSelectRun: (runId: string) => void;
  onJumpTime: (runId: string, timeS: number) => void;
};

type ChartMode = "range" | "rate" | "lateral" | "lock";

type TimelineEvent = {
  runId: string;
  runLabel: string;
  timeS: number;
  label: string;
  detail: string;
  tone: "neutral" | "lock" | "warn" | "terminal";
};

const CHART_MODES: { id: ChartMode; label: string; unit: string }[] = [
  { id: "range", label: "Range", unit: "m" },
  { id: "rate", label: "Range-rate", unit: "m/s" },
  { id: "lateral", label: "Lateral accel", unit: "m/s2" },
  { id: "lock", label: "Seeker lock", unit: "" }
];

const RUN_COLORS = ["#ededf3", "#cdddff", "#aeb8d6", "#7f89aa"];

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatMetric(value: number | null | undefined, unit = "", digits = 1): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  const abs = Math.abs(value);
  const resolvedDigits = abs >= 1000 ? 0 : abs >= 100 ? 1 : digits;
  return `${value.toFixed(resolvedDigits)}${unit}`;
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return `${Math.round(value * 100)}%`;
}

function formatText(value: string | null | undefined): string {
  return value?.trim() ? value.replaceAll("_", " ") : "-";
}

function compactScenario(value: string): string {
  return value.replace(/^missile_/, "").replaceAll("_", " ");
}

function sampleValue(sample: MissileTimelineSample, mode: ChartMode): number | null {
  if (mode === "range") {
    return asNumber(sample.range_m);
  }
  if (mode === "rate") {
    return asNumber(sample.range_rate_mps) ?? asNumber(sample.closing_speed_mps);
  }
  if (mode === "lateral") {
    return asNumber(sample.lateral_accel_mps2);
  }
  return sample.seeker_locked || sample.locked || sample.control_saturated || sample.saturated || sample.fuze_fuzed || sample.fuzed ? 1 : 0;
}

function samplesFor(run: MissileEngagementRun, mode: ChartMode): MissileTimelineSample[] {
  if (mode === "lateral") {
    return run.lateral_acceleration.timeline;
  }
  if (mode === "lock") {
    return run.seeker_lock.timeline;
  }
  return run.range.timeline;
}

function phaseIntervals(run: MissileEngagementRun, kind: "motor" | "fuze"): MissilePhaseInterval[] {
  if (kind === "motor") {
    return run.motor.phase_intervals?.length ? run.motor.phase_intervals : run.motor.phase_sequence;
  }
  return run.fuze.state_intervals ?? [];
}

function intervalLabel(interval: MissilePhaseInterval): string {
  return formatText(interval.value ?? interval.phase);
}

function lastItem<T>(items: T[] | undefined): T | undefined {
  return items && items.length ? items[items.length - 1] : undefined;
}

function buildTimeline(packet: MissileEngagementComparisonPacket): TimelineEvent[] {
  const items: TimelineEvent[] = [];
  packet.runs.forEach((run) => {
    const label = compactScenario(run.scenario);
    const add = (timeS: number | null | undefined, eventLabel: string, detail: string, tone: TimelineEvent["tone"]) => {
      if (typeof timeS === "number" && Number.isFinite(timeS)) {
        items.push({ runId: run.id, runLabel: label, timeS, label: eventLabel, detail, tone });
      }
    };
    add(run.summary.first_seeker_lock_time_s, "seeker lock", `${formatPercent(run.summary.seeker_lock_fraction)} locked samples`, "lock");
    add(run.actuator_saturation.first_time_s, "actuator saturation", `${run.actuator_saturation.count} saturated samples`, "warn");
    add(run.summary.first_fuze_time_s, "fuze", formatText(lastItem(run.fuze.state_intervals)?.value ?? lastItem(run.summary.fuze_states)), "terminal");
    const closest = run.closest_approach_timeline.event;
    add(
      closest?.time_s ?? run.miss_distance.time_s,
      "closest approach",
      `${formatMetric(run.miss_distance.value ?? closest?.miss_distance_m, " m")} miss distance`,
      "neutral"
    );
  });
  return items
    .sort((a, b) => a.timeS - b.timeS)
    .filter((event, index, list) => index === 0 || event.runId !== list[index - 1].runId || event.label !== list[index - 1].label || Math.abs(event.timeS - list[index - 1].timeS) > 0.05)
    .slice(0, 18);
}

function closestTime(run: MissileEngagementRun): number | null {
  return run.miss_distance.time_s ?? run.closest_approach_timeline.event?.time_s ?? run.summary.closest_approach_time_s ?? null;
}

function MetricCard({ run, selected, onSelect }: { run: MissileEngagementRun; selected: boolean; onSelect: () => void }) {
  return (
    <section className={`engagement-run-card ${selected ? "selected" : ""}`}>
      <div className="engagement-run-title">
        <div>
          <p className="eyebrow">{run.summary.interceptor_id ?? "missile"} to {run.summary.target_id ?? "target"}</p>
          <h3>{compactScenario(run.scenario)}</h3>
        </div>
        <button type="button" className="engagement-open-run" onClick={onSelect}>
          {selected ? "selected" : "open"}
        </button>
      </div>
      <div className="engagement-metric-grid compact">
        <div>
          <span>Miss distance</span>
          <strong>{formatMetric(run.miss_distance.value, " m")}</strong>
        </div>
        <div>
          <span>Seeker lock</span>
          <strong>{formatPercent(run.summary.seeker_lock_fraction)}</strong>
          <small>{formatMetric(run.summary.first_seeker_lock_time_s, " s", 2)}</small>
        </div>
        <div>
          <span>Closing</span>
          <strong>{formatMetric(run.summary.max_closing_speed_mps, " m/s")}</strong>
        </div>
        <div>
          <span>Lateral accel</span>
          <strong>{formatMetric(run.summary.max_lateral_accel_mps2, " m/s2")}</strong>
        </div>
        <div>
          <span>Motor phases</span>
          <strong>{run.summary.motor_phases?.map(formatText).join(" / ") || "-"}</strong>
        </div>
        <div>
          <span>Actuator sat</span>
          <strong>{formatPercent(run.summary.actuator_saturation_fraction)}</strong>
          <small>{run.summary.actuator_saturation_count ?? 0} samples</small>
        </div>
        <div>
          <span>Fuze</span>
          <strong>{run.summary.fuze_states?.map(formatText).join(" / ") || "-"}</strong>
        </div>
        <div>
          <span>Closest time</span>
          <strong>{formatMetric(closestTime(run), " s", 2)}</strong>
        </div>
      </div>
    </section>
  );
}

function ComparisonChart({ runs, mode }: { runs: MissileEngagementRun[]; mode: ChartMode }) {
  const width = 920;
  const height = 250;
  const pad = { top: 20, right: 22, bottom: 30, left: 62 };
  const points = runs.flatMap((run, runIndex) =>
    samplesFor(run, mode)
      .map((sample) => ({ runIndex, time: asNumber(sample.time_s), value: sampleValue(sample, mode) }))
      .filter((point): point is { runIndex: number; time: number; value: number } => point.time !== null && point.value !== null)
  );
  const bounds = points.length
    ? {
        minTime: Math.min(...points.map((point) => point.time)),
        maxTime: Math.max(...points.map((point) => point.time)),
        minValue: Math.min(...points.map((point) => point.value)),
        maxValue: Math.max(...points.map((point) => point.value))
      }
    : { minTime: 0, maxTime: 1, minValue: 0, maxValue: 1 };
  const spanTime = bounds.maxTime - bounds.minTime || 1;
  const spanValue = bounds.maxValue - bounds.minValue || 1;
  const axisUnit = CHART_MODES.find((item) => item.id === mode)?.unit ?? "";
  const axisSuffix = axisUnit ? ` ${axisUnit}` : "";
  const lineFor = (run: MissileEngagementRun) =>
    samplesFor(run, mode)
      .map((sample) => {
        const time = asNumber(sample.time_s);
        const value = sampleValue(sample, mode);
        if (time === null || value === null) {
          return null;
        }
        const x = pad.left + ((time - bounds.minTime) / spanTime) * (width - pad.left - pad.right);
        const y = pad.top + (1 - (value - bounds.minValue) / spanValue) * (height - pad.top - pad.bottom);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .filter((point): point is string => point !== null)
      .join(" ");

  return (
    <section className="engagement-chart">
      <div className="engagement-section-head">
        <div>
          <p className="eyebrow">Comparison Trace</p>
          <h3>{CHART_MODES.find((item) => item.id === mode)?.label}</h3>
        </div>
        <div className="engagement-legend">
          {runs.map((run, index) => (
            <span key={run.id}>
              <i style={{ background: RUN_COLORS[index % RUN_COLORS.length] }} />
              {compactScenario(run.scenario)}
            </span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Missile engagement comparison chart">
        <rect x="0" y="0" width={width} height={height} className="chart-bg" />
        {[0.25, 0.5, 0.75].map((ratio) => {
          const y = pad.top + (height - pad.top - pad.bottom) * ratio;
          return <line key={ratio} x1={pad.left} y1={y} x2={width - pad.right} y2={y} className="grid-line" />;
        })}
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={height - pad.bottom} className="axis" />
        <line x1={pad.left} y1={height - pad.bottom} x2={width - pad.right} y2={height - pad.bottom} className="axis" />
        {runs.map((run, index) => (
          <polyline key={run.id} points={lineFor(run)} fill="none" stroke={RUN_COLORS[index % RUN_COLORS.length]} strokeWidth="2.4" />
        ))}
        <text x="8" y={pad.top + 8} className="axis-label">
          {formatMetric(bounds.maxValue, axisSuffix, mode === "lock" ? 0 : 1)}
        </text>
        <text x="8" y={height - pad.bottom} className="axis-label">
          {formatMetric(bounds.minValue, axisSuffix, mode === "lock" ? 0 : 1)}
        </text>
        <text x={pad.left} y={height - 8} className="axis-label">
          {bounds.minTime.toFixed(1)}s
        </text>
        <text x={width - pad.right - 48} y={height - 8} className="axis-label">
          {bounds.maxTime.toFixed(1)}s
        </text>
      </svg>
    </section>
  );
}

function PhaseRail({ run }: { run: MissileEngagementRun }) {
  const motor = phaseIntervals(run, "motor");
  const fuze = phaseIntervals(run, "fuze");
  return (
    <div className="engagement-phase-row">
      <strong>{compactScenario(run.scenario)}</strong>
      <div>
        <span>Motor</span>
        <p>{motor.map(intervalLabel).join(" -> ") || "-"}</p>
      </div>
      <div>
        <span>Fuze</span>
        <p>{fuze.map(intervalLabel).join(" -> ") || run.summary.fuze_states?.map(formatText).join(" -> ") || "-"}</p>
      </div>
    </div>
  );
}

export function MissileEngagementAnalysis({ packet, loading, error, selectedRunId, onSelectRun, onJumpTime }: MissileEngagementAnalysisProps) {
  const [chartMode, setChartMode] = useState<ChartMode>("range");
  const runs = packet?.runs ?? [];
  const timeline = useMemo(() => (packet ? buildTimeline(packet) : []), [packet]);

  if (loading) {
    return (
      <section className="engagement-analysis loading">
        <Loader2 className="spin" size={18} />
        <span>Loading missile showcase runs...</span>
      </section>
    );
  }

  if (error) {
    return <div className="empty-state">Missile engagement analysis is unavailable: {error}</div>;
  }

  if (!runs.length) {
    return <div className="empty-state">No missile showcase runs are ready yet. Run the missile showcase scenarios or wait for the seed suite to finish syncing.</div>;
  }

  return (
    <section className="engagement-analysis">
      <div className="engagement-hero">
        <div>
          <p className="eyebrow">Missile Engagement Analysis</p>
          <h2>Showcase runs compared side by side.</h2>
          <p>Read-only analysis from existing outputs: seeker lock, closure, motor phase, control saturation, fuze state, and closest approach.</p>
        </div>
        <div className="engagement-hero-icons" aria-label="Engagement signals">
          <span><RadioTower size={16} /> seeker</span>
          <span><Zap size={16} /> motor</span>
          <span><ShieldAlert size={16} /> fuze</span>
        </div>
      </div>

      <div className="engagement-run-grid showcase">
        {runs.map((run) => (
          <MetricCard key={run.id} run={run} selected={run.id === selectedRunId} onSelect={() => onSelectRun(run.id)} />
        ))}
      </div>

      <section className="engagement-chart-shell">
        <div className="mini-segment compact" aria-label="Engagement chart metric">
          {CHART_MODES.map((mode) => (
            <button key={mode.id} type="button" className={chartMode === mode.id ? "active" : ""} onClick={() => setChartMode(mode.id)}>
              {mode.label}
            </button>
          ))}
        </div>
        <ComparisonChart runs={runs} mode={chartMode} />
      </section>

      <section className="engagement-lower-grid">
        <div className="engagement-signal-panel">
          <div className="engagement-section-head">
            <div>
              <p className="eyebrow">State Progression</p>
              <h3>Motor and fuze phases</h3>
            </div>
            <Gauge size={17} />
          </div>
          <div className="engagement-phase-table">
            {runs.map((run) => (
              <PhaseRail key={run.id} run={run} />
            ))}
          </div>
        </div>

        <div className="engagement-timeline-panel">
          <div className="engagement-section-head">
            <div>
              <p className="eyebrow">Events</p>
              <h3>Closest-approach timeline</h3>
            </div>
            <Activity size={17} />
          </div>
          <div className="engagement-timeline">
            {timeline.map((event, index) => (
              <button key={`${event.runId}-${event.timeS}-${event.label}-${index}`} className={event.tone} type="button" onClick={() => onJumpTime(event.runId, event.timeS)}>
                <span>{index + 1}</span>
                <strong>{event.timeS.toFixed(2)}s</strong>
                <em>{event.label}</em>
                <small>{event.runLabel}: {event.detail}</small>
              </button>
            ))}
            {!timeline.length && <div className="empty-state">No engagement markers were found in the showcase runs.</div>}
          </div>
        </div>
      </section>

      <div className="engagement-signal-list compact">
        {[
          ["Seeker lock", "fraction of samples with valid seeker/guidance lock", <RadioTower size={15} />],
          ["Range-rate", "negative range-rate and closing speed expose terminal geometry", <ScanLine size={15} />],
          ["Motor phase", "boost, sustain, coast, and burnout are read from missile telemetry", <Activity size={15} />],
          ["Fuze state", "armed/fuzed status and closest range explain terminal outcome", <Crosshair size={15} />]
        ].map(([label, value, icon]) => (
          <div key={String(label)}>
            {icon}
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
