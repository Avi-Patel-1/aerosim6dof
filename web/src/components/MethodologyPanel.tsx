import {
  Activity,
  BookOpen,
  Braces,
  CheckCircle2,
  Database,
  FileJson,
  GitBranch,
  Gauge,
  Layers3,
  Radar,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  TestTube2
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

type MethodologyCategory =
  | "architecture"
  | "modeling"
  | "analysis"
  | "validation"
  | "extension";

type MethodologyQuestion = {
  category: MethodologyCategory;
  question: string;
  answer: string;
  verify: string[];
  code: string[];
  artifacts: string[];
};

type MethodologyCategoryMeta = {
  id: MethodologyCategory;
  label: string;
  summary: string;
  icon: ReactNode;
};

const CATEGORIES: MethodologyCategoryMeta[] = [
  {
    id: "architecture",
    label: "Architecture",
    summary: "How the simulator core, API, browser, and artifacts stay separated.",
    icon: <Layers3 size={16} />
  },
  {
    id: "modeling",
    label: "Modeling",
    summary: "What physical systems are represented and what assumptions are visible.",
    icon: <Activity size={16} />
  },
  {
    id: "analysis",
    label: "Analysis",
    summary: "How runs become telemetry, campaigns, trade studies, and engagement reviews.",
    icon: <SlidersHorizontal size={16} />
  },
  {
    id: "validation",
    label: "Validation",
    summary: "How behavior is checked through tests, smoke runs, limits, and reports.",
    icon: <TestTube2 size={16} />
  },
  {
    id: "extension",
    label: "Extension",
    summary: "How to add models, sensors, scenarios, or algorithms without breaking the core.",
    icon: <GitBranch size={16} />
  }
];

const QUESTIONS: MethodologyQuestion[] = [
  {
    category: "architecture",
    question: "What is the purpose of AeroLab?",
    answer:
      "AeroLab is an inspectable 6DOF flight-simulation workbench for early GNC, vehicle-concept, mission-performance, sensor-analysis, and engagement studies. It is designed to make runs explainable through telemetry, replay, reports, and repeatable analysis workflows.",
    verify: ["Replay", "Telemetry", "Reports", "Methodology"],
    code: ["README.md", "docs/integration_map.md", "aerosim6dof/cli.py"],
    artifacts: ["scenario_resolved.json", "summary.json", "manifest.json"]
  },
  {
    category: "architecture",
    question: "How does the browser avoid changing the simulation physics?",
    answer:
      "The Python simulation core remains the source of truth. FastAPI starts runs or reads existing run directories, while React and Three.js visualize CSV/JSON artifacts produced by the same engine that the CLI uses.",
    verify: ["Launch", "Replay", "Reports"],
    code: ["aerosim6dof/simulation/runner.py", "aerosim6dof/web/api.py", "web/src/components/ReplayScene.tsx"],
    artifacts: ["history.csv", "truth.csv", "controls.csv", "sensors.csv"]
  },
  {
    category: "architecture",
    question: "What is the end-to-end data flow?",
    answer:
      "A scenario config resolves vehicle and environment assumptions, the runner propagates the state, the logger writes telemetry artifacts, analysis tools build derived reports, and the browser reads those outputs through API routes.",
    verify: ["Editor", "Launch", "Telemetry", "Reports"],
    code: ["aerosim6dof/scenario.py", "aerosim6dof/simulation/logger.py", "aerosim6dof/reports/studio.py"],
    artifacts: ["scenario_resolved.json", "history.csv", "report.html", "plots/*.svg"]
  },
  {
    category: "architecture",
    question: "How are the three source projects integrated?",
    answer:
      "The 6DOF simulator owns the runtime and browser. Trade-space workflows are represented through Campaigns and Trade Space, while sensor-fusion workflows are represented through Estimation and Telemetry. The companion projects remain independent CLI toolkits.",
    verify: ["Campaigns", "Trade Space", "Estimation", "Integration Map"],
    code: ["docs/integration_map.md", "aerosim6dof/tradespace/core.py", "aerosim6dof/estimation/fusion/pipeline.py"],
    artifacts: ["trade_space_report.html", "estimation_report.html", "residuals.csv"]
  },
  {
    category: "modeling",
    question: "What makes this a 6DOF simulator?",
    answer:
      "The simulation propagates translational motion and rotational attitude/rates. It tracks position, velocity, attitude, body rates, aerodynamic forces and moments, propulsion, mass properties, actuator states, and environment effects over time.",
    verify: ["Replay", "Telemetry"],
    code: ["aerosim6dof/simulation/dynamics.py", "aerosim6dof/core/quaternions.py", "aerosim6dof/vehicle/aerodynamics.py"],
    artifacts: ["truth.csv", "history.csv", "10_euler_deg.svg", "11_body_rates_dps.svg"]
  },
  {
    category: "modeling",
    question: "How are atmosphere, wind, terrain, and contact handled?",
    answer:
      "Environment modules provide atmosphere, gravity, wind, turbulence, and terrain queries. Runs can derive altitude AGL, radar-altimeter coupling, ground-contact state, impact speed, and terrain-relative event classifications without changing CSV column names.",
    verify: ["Replay", "Telemetry", "Models"],
    code: ["aerosim6dof/environment/terrain.py", "aerosim6dof/environment/wind.py", "aerosim6dof/simulation/contact.py"],
    artifacts: ["altitude_agl_m", "terrain_elevation_m", "ground_contact", "28_agl_terrain.svg"]
  },
  {
    category: "modeling",
    question: "How are propulsion, mass, and actuator limits represented?",
    answer:
      "Vehicle modules model thrust curves, fuel/mass depletion, mass properties, control-surface achievement, actuator limits, saturation flags, failures, rate behavior, and effective actuator state written into controls and history outputs.",
    verify: ["Telemetry", "Engineering", "Models"],
    code: ["aerosim6dof/vehicle/propulsion.py", "aerosim6dof/vehicle/mass_properties.py", "aerosim6dof/vehicle/actuators.py"],
    artifacts: ["thrust_n", "mass_kg", "controls.csv", "19_actuator_saturation.svg"]
  },
  {
    category: "modeling",
    question: "How are sensors represented?",
    answer:
      "Sensor modules generate measurements for IMU, GPS/GNSS-style position and velocity, barometer, pitot, magnetometer, radar altimeter, optical flow, and horizon sensing. Sensor outputs remain separate from truth so the UI can compare truth, sensor, and estimate channels.",
    verify: ["Telemetry", "Estimation"],
    code: ["aerosim6dof/sensors/sensor_suite.py", "aerosim6dof/sensors/gps.py", "aerosim6dof/sensors/radar_altimeter.py"],
    artifacts: ["sensors.csv", "gps_valid", "baro_alt_m", "radar_agl_m"]
  },
  {
    category: "modeling",
    question: "How are target, interceptor, and missile studies modeled?",
    answer:
      "Target/interceptor objects are logged as independent state histories. Missile engagement analysis derives range, range-rate, closing speed, seeker lock, motor phase, fuze state, actuator saturation, closest approach, and miss-distance metrics from generated outputs.",
    verify: ["Engagement", "Replay", "Reports"],
    code: ["aerosim6dof/simulation/targets.py", "aerosim6dof/simulation/interceptors.py", "aerosim6dof/simulation/missile_dynamics.py"],
    artifacts: ["targets.csv", "interceptors.csv", "engagement_report.html", "missile_*"]
  },
  {
    category: "analysis",
    question: "How does the telemetry console answer what happened and why?",
    answer:
      "Telemetry metadata groups raw channels by subsystem, adds readable labels and units, tracks limits, supports pinned parameters, compares runs, and links cursor position to charts and current/min/max readouts.",
    verify: ["Telemetry"],
    code: ["aerosim6dof/telemetry/metadata.py", "web/src/telemetryOps.ts", "web/src/components/OperationsTelemetryPanel.tsx"],
    artifacts: ["history.csv", "telemetry metadata", "selected-channel export"]
  },
  {
    category: "analysis",
    question: "How are alarms and events generated?",
    answer:
      "Events are generated during simulation and report processing. Alarm evaluation reads existing telemetry against rules such as qbar, load factor, GPS dropout, actuator saturation, thrust loss, and low-altitude descent without changing the integrator.",
    verify: ["Replay", "Telemetry", "Reports"],
    code: ["aerosim6dof/simulation/events.py", "aerosim6dof/analysis/alarms.py", "web/src/components/AlarmPanels.tsx"],
    artifacts: ["events.json", "alarms API", "summary.json"]
  },
  {
    category: "analysis",
    question: "How are Monte Carlo and trade-space studies performed?",
    answer:
      "Campaign tools run batches, dispersions, sweeps, and fault campaigns. Trade-space tools rank candidate designs from real simulator outputs using metrics, Pareto screening, reliability, uncertainty, sensitivity, surrogate, and optimization summaries.",
    verify: ["Campaigns", "Trade Space"],
    code: ["aerosim6dof/simulation/campaign.py", "aerosim6dof/simulation/monte_carlo_hooks.py", "aerosim6dof/tradespace/core.py"],
    artifacts: ["monte_carlo_index.csv", "design_ranking.csv", "pareto.csv", "trade_space_report.html"]
  },
  {
    category: "analysis",
    question: "How are truth, sensor, and estimate compared?",
    answer:
      "The navigation and estimation pipeline aligns truth and sensor rows by time, builds estimate channels, computes residuals and quality metrics, and exposes derived metadata so estimate channels do not get mistaken for truth.",
    verify: ["Estimation", "Telemetry"],
    code: ["aerosim6dof/estimation/navigation_filter.py", "aerosim6dof/estimation/fusion/pipeline.py", "web/src/components/EstimationPanel.tsx"],
    artifacts: ["estimate_*", "residuals.csv", "estimation_metrics.csv", "estimation_report.html"]
  },
  {
    category: "validation",
    question: "How do you know a run is valid enough to review?",
    answer:
      "Scenario validation checks configuration structure and references before execution. After execution, run summaries, required telemetry columns, events, plots, reports, and API smoke tests give multiple ways to detect broken or incomplete outputs.",
    verify: ["Editor", "Launch", "Reports"],
    code: ["aerosim6dof/analysis/scenario_validation.py", "aerosim6dof/web/api.py", "tests/test_web_api.py"],
    artifacts: ["validation advisories", "manifest.json", "summary.json"]
  },
  {
    category: "validation",
    question: "How is regression risk controlled?",
    answer:
      "The project keeps CLI commands stable, writes browser outputs under web-run directories, adds focused unit tests for new behavior, runs full Python discovery tests, type-checks the frontend, and performs browser smoke checks across the major tabs.",
    verify: ["Reports", "Methodology"],
    code: ["tests/", "web/package.json", "scripts/run_web_demo.sh"],
    artifacts: ["test outputs", "web/dist", "run artifacts"]
  },
  {
    category: "validation",
    question: "What happens if generated artifacts are incomplete or malformed?",
    answer:
      "API readers are defensive around optional artifacts and malformed JSON. A corrupt run metadata file should not take down run listing, run detail, navigation, telemetry, or engagement discovery surfaces.",
    verify: ["Reports", "Replay"],
    code: ["aerosim6dof/web/api.py", "tests/test_web_api_production.py"],
    artifacts: ["summary.json", "manifest.json", "events.json"]
  },
  {
    category: "validation",
    question: "What are the current limitations?",
    answer:
      "The project is an early engineering simulator, not a certified flight-dynamics package. Aerodynamic tables, actuator nonlinearities, engine transients, terrain/contact, estimation, and missile models are intentionally inspectable and improving, but should be validated against higher-fidelity references before operational use.",
    verify: ["Models", "Engineering", "Telemetry"],
    code: ["docs/output_reference.md", "examples/scenarios/", "examples/vehicles/"],
    artifacts: ["model reports", "scenario_resolved.json", "validation advisories"]
  },
  {
    category: "extension",
    question: "How would a new vehicle model be integrated?",
    answer:
      "Add or update a vehicle config, expose aero/propulsion/mass/actuator assumptions, validate it through scenario resolution, run a baseline smoke case, inspect telemetry and report plots, then add regression coverage for expected outputs.",
    verify: ["Models", "Editor", "Engineering"],
    code: ["examples/vehicles/", "aerosim6dof/vehicle/", "tests/test_sim.py"],
    artifacts: ["vehicle JSON", "scenario_resolved.json", "model reports"]
  },
  {
    category: "extension",
    question: "How would a new algorithm or subsystem be added safely?",
    answer:
      "Keep the subsystem behind config defaults, preserve existing output formats, add explicit telemetry channels and metadata, write a small scenario that exercises the feature, add tests, then expose the workflow in the browser only after the API path is stable.",
    verify: ["Editor", "Telemetry", "Reports"],
    code: ["aerosim6dof/scenario.py", "aerosim6dof/telemetry/metadata.py", "tests/"],
    artifacts: ["new channels", "metadata", "scenario smoke run"]
  },
  {
    category: "extension",
    question: "How would a stakeholder trace a conclusion back to evidence?",
    answer:
      "Start from the report summary, open the relevant event or alarm, jump to that time in Replay, inspect the channel in Telemetry, and confirm the raw CSV row or generated plot. The methodology is artifact-first rather than screenshot-first.",
    verify: ["Reports", "Replay", "Telemetry"],
    code: ["aerosim6dof/reports/studio.py", "web/src/components/ReportStudio.tsx", "web/src/components/ReplayScene.tsx"],
    artifacts: ["report packet", "events.json", "history.csv", "plots/*.svg"]
  }
];

const TRACE_STEPS = [
  {
    label: "Scenario",
    detail: "Resolve mission, vehicle, environment, guidance, sensors, faults, targets, and outputs.",
    icon: <Route size={16} />
  },
  {
    label: "Simulation",
    detail: "Propagate 6DOF state, controls, environment, sensors, events, and optional engagement objects.",
    icon: <Gauge size={16} />
  },
  {
    label: "Artifacts",
    detail: "Write CSV, JSON, SVG, and HTML files that remain reviewable outside the browser.",
    icon: <Database size={16} />
  },
  {
    label: "Analysis",
    detail: "Build alarms, estimation residuals, trade-space rankings, engagement metrics, and report packets.",
    icon: <FileJson size={16} />
  }
];

const REVIEW_PROMPTS = [
  "What assumptions are in the model, and where are they visible?",
  "Which telemetry channels support the conclusion?",
  "What changed between the baseline run and the comparison run?",
  "Which subsystem caused the event, alarm, or miss distance?",
  "What would need external validation before using the result operationally?",
  "How would this feature be extended without breaking existing scenarios?"
];

export function MethodologyPanel() {
  const [activeCategory, setActiveCategory] = useState<MethodologyCategory>("architecture");
  const activeQuestions = useMemo(
    () => QUESTIONS.filter((question) => question.category === activeCategory),
    [activeCategory]
  );
  const activeMeta = CATEGORIES.find((category) => category.id === activeCategory) ?? CATEGORIES[0];

  return (
    <section className="methodology-panel" aria-label="Engineering methodology">
      <div className="methodology-hero">
        <div>
          <p className="eyebrow">Engineering Methodology</p>
          <h3>Trace every claim back to code, artifacts, and repeatable checks.</h3>
          <p>
            This section documents the design rationale behind AeroLab: how the simulator is organized,
            what each analysis surface proves, what assumptions remain visible, and how to review the
            generated evidence.
          </p>
        </div>
        <div className="methodology-principles" aria-label="Methodology principles">
          <span>
            <ShieldCheck size={15} />
            preserve the CLI core
          </span>
          <span>
            <Database size={15} />
            artifacts as evidence
          </span>
          <span>
            <CheckCircle2 size={15} />
            test before trust
          </span>
        </div>
      </div>

      <div className="methodology-trace" aria-label="Evidence chain">
        {TRACE_STEPS.map((step) => (
          <article key={step.label}>
            <span>{step.icon}</span>
            <strong>{step.label}</strong>
            <p>{step.detail}</p>
          </article>
        ))}
      </div>

      <div className="methodology-category-strip" aria-label="Methodology categories">
        {CATEGORIES.map((category) => (
          <button
            key={category.id}
            type="button"
            className={activeCategory === category.id ? "active" : ""}
            aria-pressed={activeCategory === category.id}
            onClick={() => setActiveCategory(category.id)}
          >
            {category.icon}
            <span>{category.label}</span>
          </button>
        ))}
      </div>

      <div className="methodology-section-head">
        <div>
          <p className="eyebrow">{activeMeta.label}</p>
          <h3>{activeMeta.summary}</h3>
        </div>
        <span>{activeQuestions.length} review questions</span>
      </div>

      <div className="methodology-question-grid">
        {activeQuestions.map((item) => (
          <article key={item.question} className="methodology-question">
            <div className="methodology-question-title">
              <BookOpen size={16} />
              <h4>{item.question}</h4>
            </div>
            <p>{item.answer}</p>
            <div className="methodology-evidence-grid">
              <EvidenceList icon={<Target size={14} />} label="Verify in" items={item.verify} />
              <EvidenceList icon={<Braces size={14} />} label="Code path" items={item.code} />
              <EvidenceList icon={<FileJson size={14} />} label="Evidence" items={item.artifacts} />
            </div>
          </article>
        ))}
      </div>

      <section className="methodology-review-panel" aria-label="Technical review prompts">
        <div className="section-title">
          <Radar size={16} />
          <h3>Technical Review Prompts</h3>
        </div>
        <p>
          These prompts are useful when reviewing a run, extending the model, or deciding whether an
          analysis result is supported by the generated evidence.
        </p>
        <div className="methodology-prompt-list">
          {REVIEW_PROMPTS.map((prompt) => (
            <span key={prompt}>{prompt}</span>
          ))}
        </div>
      </section>
    </section>
  );
}

function EvidenceList({ icon, label, items }: { icon: ReactNode; label: string; items: string[] }) {
  return (
    <div className="methodology-evidence-list">
      <span>
        {icon}
        {label}
      </span>
      {items.map((item) => (
        <code key={item}>{item}</code>
      ))}
    </div>
  );
}
