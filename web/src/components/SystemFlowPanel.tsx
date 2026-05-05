import {
  Activity,
  BarChart3,
  Boxes,
  Braces,
  CheckCircle2,
  Database,
  FileJson,
  MonitorPlay,
  PlayCircle,
  Route,
  type LucideIcon
} from "lucide-react";
import { useMemo, useState } from "react";

type FlowBlock = {
  id: string;
  label: string;
  kicker: string;
  summary: string;
  reads: string[];
  writes: string[];
  tabs: string[];
  code: string[];
  icon: LucideIcon;
};

const FLOW_BLOCKS: FlowBlock[] = [
  {
    id: "mission",
    label: "Mission Definition",
    kicker: "Inputs",
    summary: "Scenarios collect vehicle, environment, initial-state, guidance, sensor, target, and output assumptions.",
    reads: ["scenario JSON", "vehicle config", "environment config"],
    writes: ["resolved scenario", "run request"],
    tabs: ["Editor", "Launch", "Models"],
    code: ["aerosim6dof/scenario.py", "examples/scenarios/"],
    icon: Route
  },
  {
    id: "validation",
    label: "Validation",
    kicker: "Guardrails",
    summary: "Config checks catch missing references, invalid ranges, unsupported presets, and likely failure modes before execution.",
    reads: ["run request", "scenario references"],
    writes: ["validation advisories", "safe run inputs"],
    tabs: ["Editor", "Launch"],
    code: ["aerosim6dof/analysis/scenario_validation.py", "aerosim6dof/web/api.py"],
    icon: CheckCircle2
  },
  {
    id: "core",
    label: "Simulation Core",
    kicker: "Engine",
    summary: "The Python core propagates 6DOF state, vehicle forces, controls, sensors, terrain/contact, targets, and events.",
    reads: ["resolved scenario", "vehicle models", "environment models"],
    writes: ["state history", "controls", "sensor rows", "events"],
    tabs: ["Replay", "Engineering"],
    code: ["aerosim6dof/simulation/runner.py", "aerosim6dof/simulation/dynamics.py"],
    icon: Activity
  },
  {
    id: "artifacts",
    label: "Run Artifacts",
    kicker: "Evidence",
    summary: "Each run is saved as reviewable CSV, JSON, HTML, and SVG artifacts so results are inspectable outside the browser.",
    reads: ["simulation state", "events", "model outputs"],
    writes: ["history.csv", "truth.csv", "controls.csv", "sensors.csv", "summary.json"],
    tabs: ["Replay", "Reports"],
    code: ["aerosim6dof/simulation/logger.py", "aerosim6dof/reports/studio.py"],
    icon: Database
  },
  {
    id: "analysis",
    label: "Analysis Layers",
    kicker: "Interpretation",
    summary: "Post-run tools derive telemetry metadata, alarms, estimation residuals, engagement metrics, and trade-space results.",
    reads: ["run artifacts", "metadata", "campaign outputs"],
    writes: ["alarms", "metrics", "plots", "reports"],
    tabs: ["Telemetry", "Estimation", "Engagement", "Trade Space"],
    code: ["aerosim6dof/analysis/", "aerosim6dof/telemetry/metadata.py"],
    icon: BarChart3
  },
  {
    id: "workbench",
    label: "Browser Workbench",
    kicker: "Operations",
    summary: "FastAPI serves run data while React and Three.js provide replay, telemetry, campaigns, reports, and scenario tools.",
    reads: ["API responses", "telemetry series", "artifacts"],
    writes: ["new run jobs", "exports", "saved drafts"],
    tabs: ["Replay", "Telemetry", "Campaigns", "Reports"],
    code: ["aerosim6dof/web/api.py", "web/src/components/Workbench.tsx"],
    icon: MonitorPlay
  },
  {
    id: "reports",
    label: "Reports And Review",
    kicker: "Output",
    summary: "Final packets tie conclusions back to scenarios, telemetry, events, alarms, plots, and generated evidence.",
    reads: ["analysis results", "run summaries", "plots"],
    writes: ["HTML report", "SVG plots", "export packets"],
    tabs: ["Reports", "Methodology"],
    code: ["aerosim6dof/reports/studio.py", "web/src/components/ReportStudio.tsx"],
    icon: FileJson
  }
];

const PIPELINE_SUMMARY = [
  "Define the mission",
  "validate assumptions",
  "run the Python core",
  "write artifacts",
  "derive analysis",
  "inspect in the browser",
  "export evidence"
];

export function SystemFlowPanel() {
  const [selectedId, setSelectedId] = useState(FLOW_BLOCKS[0].id);
  const selectedBlock = useMemo(
    () => FLOW_BLOCKS.find((block) => block.id === selectedId) ?? FLOW_BLOCKS[0],
    [selectedId]
  );
  const SelectedIcon = selectedBlock.icon;

  return (
    <section className="system-flow-panel" aria-label="System flow overview">
      <div className="system-flow-head">
        <div>
          <p className="eyebrow">System Flow</p>
          <h3>From mission setup to evidence-backed review.</h3>
        </div>
        <p>
          A high-level map of how inputs move through validation, simulation, artifacts,
          analysis, and the browser workbench.
        </p>
      </div>

      <div className="system-flow-overview" aria-label="Pipeline summary">
        {PIPELINE_SUMMARY.map((item, index) => (
          <span key={item}>
            <strong>{String(index + 1).padStart(2, "0")}</strong>
            {item}
          </span>
        ))}
      </div>

      <div className="system-flow-layout">
        <div className="system-flow-track" aria-label="Clickable system flow blocks">
          {FLOW_BLOCKS.map((block, index) => {
            const Icon = block.icon;
            const isActive = selectedId === block.id;
            return (
              <div className="system-flow-node-wrap" key={block.id}>
                <button
                  type="button"
                  className={`system-flow-node${isActive ? " active" : ""}`}
                  aria-pressed={isActive}
                  onClick={() => setSelectedId(block.id)}
                >
                  <span className="system-flow-node-icon">
                    <Icon size={17} />
                  </span>
                  <small>{block.kicker}</small>
                  <strong>{block.label}</strong>
                  <p>{block.summary}</p>
                </button>
                {index < FLOW_BLOCKS.length - 1 && (
                  <span className="system-flow-connector" aria-hidden="true">
                    <span />
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <aside className="system-flow-detail" aria-label={`${selectedBlock.label} details`}>
          <div className="system-flow-detail-title">
            <span>
              <SelectedIcon size={18} />
            </span>
            <div>
              <p className="eyebrow">{selectedBlock.kicker}</p>
              <h3>{selectedBlock.label}</h3>
            </div>
          </div>
          <p>{selectedBlock.summary}</p>
          <div className="system-flow-detail-grid">
            <FlowList icon={Boxes} label="Reads" items={selectedBlock.reads} />
            <FlowList icon={Database} label="Writes" items={selectedBlock.writes} />
            <FlowList icon={PlayCircle} label="UI tabs" items={selectedBlock.tabs} />
            <FlowList icon={Braces} label="Code" items={selectedBlock.code} />
          </div>
        </aside>
      </div>
    </section>
  );
}

function FlowList({ icon: Icon, label, items }: { icon: LucideIcon; label: string; items: string[] }) {
  return (
    <div className="system-flow-list">
      <span>
        <Icon size={14} />
        {label}
      </span>
      {items.map((item) => (
        <code key={item}>{item}</code>
      ))}
    </div>
  );
}
