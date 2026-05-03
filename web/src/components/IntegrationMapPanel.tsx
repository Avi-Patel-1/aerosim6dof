import {
  Activity,
  BarChart3,
  FileJson,
  Gauge,
  Layers3,
  Play,
  Radar,
  Route,
  Settings2,
  SlidersHorizontal,
  Target
} from "lucide-react";
import type { ReactNode } from "react";

type IntegrationSurface = {
  name: string;
  purpose: string;
  source: string;
  outputs: string;
  icon: ReactNode;
};

const SURFACES: IntegrationSurface[] = [
  {
    name: "Replay",
    purpose: "Review generated runs in 3D with events, alarms, targets, interceptors, terrain, and synchronized scrub controls.",
    source: "aerosim6dof simulation, web run index, telemetry CSVs",
    outputs: "history.csv, truth.csv, controls.csv, sensors.csv, events.json",
    icon: <Route size={16} />
  },
  {
    name: "Telemetry",
    purpose: "Inspect mission data by subsystem with search, pinned parameters, min/max/current readouts, limits, export, and compare traces.",
    source: "telemetry metadata, alarms, run outputs, report-studio packet data",
    outputs: "selected-channel CSV export, chart layouts, report packet sections",
    icon: <Gauge size={16} />
  },
  {
    name: "Estimation",
    purpose: "Compare truth, raw sensors, and fused navigation estimates, including GNSS availability and residual metrics.",
    source: "navigation endpoint plus sensor-fusion report pipeline",
    outputs: "estimation_summary.json, residuals.csv, estimation_metrics.csv, SVG plots, estimation_report.html",
    icon: <Radar size={16} />
  },
  {
    name: "Engagement",
    purpose: "Compare target and interceptor runs by seeker lock, range, range-rate, closing speed, motor phase, fuze state, and miss distance.",
    source: "target/interceptor CSVs, engagement reports, missile comparison packet",
    outputs: "targets.csv, interceptors.csv, engagement_report.html, missile comparison summaries",
    icon: <Target size={16} />
  },
  {
    name: "Launch",
    purpose: "Validate scenarios, execute new runs, compare runs, and create subsystem reports without leaving the browser.",
    source: "FastAPI action and job routes over the existing CLI analysis functions",
    outputs: "new run directories, compare reports, report.html, sensor_report, engagement_report",
    icon: <Play size={16} />
  },
  {
    name: "Campaigns",
    purpose: "Launch repeatable batch, Monte Carlo, sweep, and fault-campaign jobs through the same scenario engine.",
    source: "aerosim6dof simulation campaign runners",
    outputs: "batch, Monte Carlo, sweep, and fault-campaign indexes and reports",
    icon: <SlidersHorizontal size={16} />
  },
  {
    name: "Trade Space",
    purpose: "Rank designs from simulator outputs using Pareto, reliability, uncertainty, sensitivity, surrogate, and optimization studies.",
    source: "AeroLab trade-space primitives adapted from the Monte Carlo explorer workflow",
    outputs: "design_ranking.csv, pareto.csv, reliability, UQ, surrogate, optimization, trade_space_report.html",
    icon: <BarChart3 size={16} />
  },
  {
    name: "Engineering",
    purpose: "Run trim, trim sweeps, linearization, stability analysis, and linear-model reporting against selected scenarios and vehicles.",
    source: "analysis trim, linearization, stability, and linear-model-report actions",
    outputs: "trim.json, trim_sweep.csv, linearization.json, stability summaries, linear_model_report.html",
    icon: <Activity size={16} />
  },
  {
    name: "Models",
    purpose: "Inspect vehicles, aerodynamic data, propulsion curves, environments, and generated scenario templates before trusting a run.",
    source: "vehicle, aero, propulsion, environment, and config analysis actions",
    outputs: "model inspection JSON, aero/propulsion/environment HTML reports, generated scenario JSON",
    icon: <Layers3 size={16} />
  },
  {
    name: "Editor",
    purpose: "Build missions with guided fields for vehicle, environment, GNC, sensors, faults, targets, interceptors, and expert JSON.",
    source: "scenario schema, validation hardening, examples, vehicle and environment configs",
    outputs: "scenario drafts, validation advisories, runnable scenario JSON",
    icon: <Settings2 size={16} />
  },
  {
    name: "Reports",
    purpose: "Collect generated packets, HTML reports, SVG plots, CSV/JSON artifacts, and background-job history in one review surface.",
    source: "report studio, action result artifacts, storage index, job progress state",
    outputs: "mission packets, report exports, generated artifacts, job history",
    icon: <FileJson size={16} />
  }
];

export function IntegrationMapPanel() {
  return (
    <section className="integration-map-panel" aria-label="Integration map">
      <div className="section-title">
        <Route size={16} />
        <h3>Integration Map</h3>
      </div>
      <p>
        AeroLab keeps the original command-line simulator intact, then exposes the 6DOF, trade-space,
        and sensor-fusion workflows as browser surfaces around the same generated artifacts.
      </p>
      <div className="integration-map-list">
        {SURFACES.map((surface) => (
          <article key={surface.name} className="integration-map-row">
            <span>{surface.icon}</span>
            <div>
              <strong>{surface.name}</strong>
              <p>{surface.purpose}</p>
              <small>{surface.source}</small>
              <small>{surface.outputs}</small>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
