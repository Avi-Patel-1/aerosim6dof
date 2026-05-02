import {
  Activity,
  BarChart3,
  Boxes,
  Braces,
  Camera,
  CheckCircle2,
  Compass,
  FileJson,
  Gauge,
  Home,
  Layers3,
  Loader2,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  RadioTower,
  RotateCcw,
  Route,
  Save,
  ScanLine,
  Settings2,
  ShieldAlert,
  Sparkles,
  TerminalSquare,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  cancelJob,
  createScenarioDraft,
  getCapabilities,
  getEnvironments,
  getExamplesGallery,
  getJob,
  getJobs,
  getRunNavigation,
  getReportStudioPacket,
  getRun,
  getRunAlarms,
  getRuns,
  getScenario,
  getScenarios,
  getStorageStatus,
  getTelemetry,
  getVehicles,
  jobEventsUrl,
  retryJob,
  startJob,
  validateScenario,
  validateScenarioJson
} from "../api";
import type { ActionResult, AlarmSummary, Capability, ConfigSummary, JobSummary, NavigationTelemetry, ReplayHandoff, RunSummary, ScenarioDraft, ScenarioSummary, ScenarioValidation, StorageStatus, TelemetryRow, TelemetrySeries } from "../types";
import type { ExamplesGalleryCard } from "../examplesGallery";
import type { ReportStudioExportPayload, ReportStudioExportRequest, ReportStudioPacket } from "../reportStudio";
import { activeAlarmCount } from "../alarms";
import { channelLabel, channelLabelWithUnit } from "../telemetry";
import { buildReplayOverlayState, buildTrailColorLegendDescriptor } from "../replayVisuals";
import { ActiveAlarmsPanel, AlarmHistoryPanel } from "./AlarmPanels";
import { CampaignDesigner } from "./CampaignDesigner";
import { ExamplesGallery } from "./ExamplesGallery";
import { LiveProgressPanel } from "./LiveProgressPanel";
import { OperationsTelemetryPanel } from "./OperationsTelemetryPanel";
import { ParameterInfoPanel } from "./ParameterInfoPanel";
import { ReplayScene } from "./ReplayScene";
import { ReplaySceneOverlayLegend } from "./ReplaySceneOverlayLegend";
import { ReportStudio } from "./ReportStudio";
import { ScenarioBuilderV2 } from "./ScenarioBuilderV2";
import { TelemetryChart } from "./TelemetryChart";

type TabId = "replay" | "telemetry" | "launch" | "campaigns" | "engineering" | "models" | "editor" | "reports";
type ChartMode = "flight" | "intercept" | "controls" | "sensors";
type EnvironmentMode = "range" | "coast" | "night";
type CameraMode = "chase" | "orbit" | "cockpit" | "map" | "rangeSafety";
type TrailColorMode = "plain" | "speed" | "qbar" | "load" | "altitude";

const TABS: { id: TabId; label: string; title: string; subtitle: string }[] = [
  { id: "replay", label: "Replay", title: "Replay the vehicle in full flight context.", subtitle: "Scrub attitude, trajectory, events, and sampled telemetry from the selected output run." },
  { id: "telemetry", label: "Telemetry", title: "Answer what happened, when, and why.", subtitle: "Search, pin, compare, export, and inspect subsystem telemetry like a mission operations console." },
  { id: "launch", label: "Launch", title: "Run, validate, compare, and report.", subtitle: "Execute scenarios through the existing Python engine and keep generated outputs under web runs." },
  { id: "campaigns", label: "Campaigns", title: "Batch the uncertainty space.", subtitle: "Monte Carlo, parameter sweeps, fault campaigns, and batch workflows are available from one console." },
  { id: "engineering", label: "Engineering", title: "Trim, linearize, and inspect stability.", subtitle: "Use the simulator's engineering analysis commands without leaving the browser." },
  { id: "models", label: "Models", title: "Open the configuration surface.", subtitle: "Inspect vehicles, aerodynamic data, propulsion, environments, and scenario templates." },
  { id: "editor", label: "Editor", title: "Draft scenarios with guardrails.", subtitle: "Use guided controls or raw JSON, validate before launch, and preserve checked-in examples." },
  { id: "reports", label: "Reports", title: "Collect artifacts and job history.", subtitle: "Review generated HTML, SVG, CSV, JSON, action output, and background job events." }
];

const DEFAULT_CHANNELS: Record<ChartMode, string[]> = {
  flight: ["altitude_m", "speed_mps", "pitch_deg", "load_factor_g"],
  intercept: ["target_range_m", "interceptor_range_m", "closing_speed_mps", "interceptor_closing_speed_mps", "relative_z_m"],
  controls: ["elevator_deg", "aileron_deg", "rudder_deg", "throttle"],
  sensors: ["pitot_airspeed_mps", "baro_alt_m", "gps_z_m", "radar_agl_m"]
};

const REPLAY_SCALE_MIN = 0.88;
const REPLAY_SCALE_MAX = 1.04;
const REPLAY_SCALE_STEP = 0.04;
const DEFAULT_REPLAY_SCALE = 0.92;

function numeric(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function formatMetric(value: unknown, unit = "", digits = 1): string {
  const number = numeric(value);
  return number === null ? "-" : `${number.toFixed(digits)}${unit}`;
}

function currentTime(rows: TelemetryRow[], index: number): string {
  const value = numeric(rows[index]?.time_s);
  return value === null ? "0.00s" : `${value.toFixed(2)}s`;
}

function summaryFinal(summary: RunSummary | null): Record<string, unknown> {
  const final = summary?.summary.final;
  return final && typeof final === "object" ? (final as Record<string, unknown>) : {};
}

function compactJson(value: unknown): string {
  return JSON.stringify(value, null, 2).slice(0, 1600);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function preferredRun(items: RunSummary[], preferredId?: string): RunSummary | undefined {
  return (
    items.find((run) => run.id === preferredId) ??
    items.find((run) => run.scenario === "nominal_ascent") ??
    items.find((run) => run.id.startsWith("web_runs~")) ??
    items[0]
  );
}

function compareRun(items: RunSummary[], selectedId?: string): string {
  return items.find((run) => run.id !== selectedId)?.id ?? selectedId ?? "";
}

function telemetryWithNavigation(series: TelemetrySeries, navigation: NavigationTelemetry | null): TelemetrySeries {
  if (!navigation?.rows.length) {
    return series;
  }
  const history = series.history.map((row, index) => ({ ...row, ...(navigation.rows[index] ?? {}) }));
  const metadata = { ...(series.metadata ?? {}), ...(navigation.metadata ?? {}) };
  const navigationChannels = navigation.channels.map((channel) => channel.key).filter(Boolean);
  return {
    ...series,
    history,
    channels: {
      ...series.channels,
      history: [...new Set([...(series.channels.history ?? []), ...navigationChannels])]
    },
    metadata
  };
}

type SelectProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { id: string; name: string }[];
};

function SelectField({ label, value, onChange, options }: SelectProps) {
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

type TextFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
};

function TextField({ label, value, onChange, type = "text" }: TextFieldProps) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

type ActionCardProps = {
  title: string;
  icon: ReactNode;
  running: boolean;
  onRun: () => void;
  children?: ReactNode;
};

function ActionCard({ title, icon, running, onRun, children }: ActionCardProps) {
  return (
    <section className="action-card">
      <div className="action-card-title">
        <span>{icon}</span>
        <h3>{title}</h3>
      </div>
      <div className="action-card-body">{children}</div>
      <button className="primary-action" onClick={onRun} disabled={running}>
        {running ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
        Run
      </button>
    </section>
  );
}

type WorkbenchProps = {
  initialHandoff?: ReplayHandoff | null;
  onHome: () => void;
};

export function Workbench({ initialHandoff, onHome }: WorkbenchProps) {
  const [activeTab, setActiveTab] = useState<TabId>("replay");
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [vehicles, setVehicles] = useState<ConfigSummary[]>([]);
  const [environments, setEnvironments] = useState<ConfigSummary[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [examplesGallery, setExamplesGallery] = useState<ExamplesGalleryCard[]>([]);
  const [storageStatus, setStorageStatus] = useState<StorageStatus | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>(initialHandoff?.run ? [initialHandoff.run] : []);
  const [selectedScenario, setSelectedScenario] = useState("nominal_ascent");
  const [selectedVehicle, setSelectedVehicle] = useState("baseline");
  const [secondVehicle, setSecondVehicle] = useState("electric_uav");
  const [selectedEnvironment, setSelectedEnvironment] = useState("calm");
  const [selectedRunId, setSelectedRunId] = useState(initialHandoff?.runId ?? "");
  const [compareRunId, setCompareRunId] = useState("");
  const [runDetail, setRunDetail] = useState<RunSummary | null>(initialHandoff?.run ?? null);
  const [telemetry, setTelemetry] = useState<TelemetrySeries | null>(initialHandoff?.telemetry ?? null);
  const [compareTelemetry, setCompareTelemetry] = useState<TelemetrySeries | null>(null);
  const [alarms, setAlarms] = useState<AlarmSummary[]>([]);
  const [acknowledgedAlarms, setAcknowledgedAlarms] = useState<Record<string, boolean>>({});
  const [currentIndex, setCurrentIndex] = useState(initialHandoff?.index ?? 0);
  const [playing, setPlaying] = useState(initialHandoff?.playing ?? false);
  const [chartMode, setChartMode] = useState<ChartMode>("flight");
  const [channelSelections, setChannelSelections] = useState<Record<ChartMode, string[]>>(DEFAULT_CHANNELS);
  const [inspectedChannel, setInspectedChannel] = useState("");
  const [environmentMode, setEnvironmentMode] = useState<EnvironmentMode>(initialHandoff?.environmentMode ?? "range");
  const [cameraMode, setCameraMode] = useState<CameraMode>(initialHandoff?.cameraMode ?? "chase");
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [replayScale, setReplayScale] = useState(DEFAULT_REPLAY_SCALE);
  const [replayFullscreen, setReplayFullscreen] = useState(false);
  const [showTrail, setShowTrail] = useState(true);
  const [showAxes, setShowAxes] = useState(false);
  const [showWind, setShowWind] = useState(false);
  const [showVelocity, setShowVelocity] = useState(true);
  const [showAcceleration, setShowAcceleration] = useState(false);
  const [showSensors, setShowSensors] = useState(false);
  const [trailColorMode, setTrailColorMode] = useState<TrailColorMode>("speed");
  const [busyAction, setBusyAction] = useState("");
  const [activeJob, setActiveJob] = useState<JobSummary | null>(null);
  const [jobHistory, setJobHistory] = useState<JobSummary[]>([]);
  const [reportPacket, setReportPacket] = useState<ReportStudioPacket | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [results, setResults] = useState<ActionResult[]>([]);
  const [scenarioText, setScenarioText] = useState("");
  const [scenarioValidation, setScenarioValidation] = useState<ScenarioValidation | null>(null);
  const [draftInfo, setDraftInfo] = useState<ScenarioDraft | null>(null);
  const [mcSamples, setMcSamples] = useState("5");
  const [sweepParameter, setSweepParameter] = useState("guidance.throttle");
  const [sweepValues, setSweepValues] = useState("0.82,0.86");
  const [faults, setFaults] = useState("gps_dropout,thrust_loss");
  const [speeds, setSpeeds] = useState("90,120,150");
  const [altitudes, setAltitudes] = useState("0,1000");
  const [linearTime, setLinearTime] = useState("3.0");
  const [generatedName, setGeneratedName] = useState("browser_template");

  const scenarioOptions = scenarios.map((scenario) => ({ id: scenario.id, name: scenario.name }));
  const vehicleOptions = vehicles.map((vehicle) => ({ id: vehicle.id, name: vehicle.name }));
  const environmentOptions = environments.map((environment) => ({ id: environment.id, name: environment.name }));
  const runOptions = runs.map((run) => ({ id: run.id, name: `${run.scenario} / ${run.id.replaceAll("~", " / ")}` }));

  const refreshRuns = async (preferredId?: string) => {
    const items = await getRuns();
    setRuns(items);
    if (preferredId) {
      setSelectedRunId(preferredId);
      return;
    }
    if (!selectedRunId && items[0]) {
      setSelectedRunId(preferredRun(items)?.id ?? "");
    }
    if (!compareRunId && items[0]) {
      setCompareRunId(compareRun(items, selectedRunId || preferredRun(items)?.id));
    }
  };

  useEffect(() => {
    let mounted = true;
    Promise.all([getScenarios(), getVehicles(), getEnvironments(), getCapabilities(), getRuns(), getJobs(), getExamplesGallery(), getStorageStatus().catch(() => null)])
      .then(([scenarioItems, vehicleItems, environmentItems, capabilityItems, runItems, jobItems, galleryItems, storage]) => {
        if (!mounted) {
          return;
        }
        setScenarios(scenarioItems);
        setVehicles(vehicleItems);
        setEnvironments(environmentItems);
        setCapabilities(capabilityItems);
        setRuns(runItems);
        setJobHistory(jobItems);
        setExamplesGallery(galleryItems);
        setStorageStatus(storage);
        setSelectedScenario(scenarioItems.find((item) => item.id === "nominal_ascent")?.id ?? scenarioItems[0]?.id ?? "");
        setSelectedVehicle(vehicleItems.find((item) => item.id === "baseline")?.id ?? vehicleItems[0]?.id ?? "");
        setSecondVehicle(vehicleItems.find((item) => item.id === "electric_uav")?.id ?? vehicleItems[1]?.id ?? vehicleItems[0]?.id ?? "");
        setSelectedEnvironment(environmentItems[0]?.id ?? "");
        const preferred = preferredRun(runItems, initialHandoff?.runId);
        setSelectedRunId(preferred?.id ?? "");
        setCompareRunId(compareRun(runItems, preferred?.id));
      })
      .catch((error: Error) => setMessage(error.message));
    return () => {
      mounted = false;
    };
  }, [initialHandoff?.runId]);

  useEffect(() => {
    if (!selectedScenario) {
      return;
    }
    let mounted = true;
    getScenario(selectedScenario)
      .then((detail) => {
        if (!mounted) {
          return;
        }
        setScenarioText(JSON.stringify(detail.raw, null, 2));
        setScenarioValidation(null);
        setDraftInfo(null);
      })
      .catch((error: Error) => setMessage(error.message));
    return () => {
      mounted = false;
    };
  }, [selectedScenario]);

  useEffect(() => {
    if (!scenarios.length || runs.length >= scenarios.length) {
      return;
    }
    let cancelled = false;
    const timer = window.setInterval(() => {
      getRuns()
        .then((items) => {
          if (cancelled) {
            return;
          }
          setRuns(items);
          const selected = selectedRunId || preferredRun(items)?.id || "";
          if (!selectedRunId && selected) {
            setSelectedRunId(selected);
          }
          if (!compareRunId && items.length) {
            setCompareRunId(compareRun(items, selected));
          }
        })
        .catch(() => undefined);
    }, 4500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [compareRunId, runs.length, scenarios.length, selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    let mounted = true;
    const canReuseHandoff = initialHandoff?.runId === selectedRunId && initialHandoff.telemetry.run_id === selectedRunId;
    if (!canReuseHandoff) {
      setTelemetry(null);
      setCurrentIndex(0);
    }
    setAlarms([]);
    setReportPacket(null);
    setAcknowledgedAlarms({});
    Promise.all([
      getRun(selectedRunId),
      getTelemetry(selectedRunId, 3),
      getRunAlarms(selectedRunId).catch(() => []),
      getRunNavigation(selectedRunId, 3).catch(() => null)
    ])
      .then(([detail, series, alarmItems, navigation]) => {
        if (!mounted) {
          return;
        }
        const augmentedSeries = telemetryWithNavigation(series, navigation);
        setRunDetail(detail);
        setTelemetry(augmentedSeries);
        setAlarms(alarmItems);
        if (canReuseHandoff) {
          setCurrentIndex((index) => Math.min(index, Math.max(augmentedSeries.history.length - 1, 0)));
        } else {
          setCurrentIndex(0);
        }
      })
      .catch((error: Error) => setMessage(error.message));
    return () => {
      mounted = false;
    };
  }, [selectedRunId]);

  useEffect(() => {
    if (activeTab !== "reports" || !selectedRunId) {
      return;
    }
    let mounted = true;
    setReportLoading(true);
    getReportStudioPacket(selectedRunId)
      .then((packet) => {
        if (mounted) {
          setReportPacket(packet);
        }
      })
      .catch((error: Error) => {
        if (mounted) {
          setReportPacket(null);
          setMessage(error.message);
        }
      })
      .finally(() => {
        if (mounted) {
          setReportLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [activeTab, selectedRunId]);

  useEffect(() => {
    if (!compareRunId || compareRunId === selectedRunId) {
      setCompareTelemetry(null);
      return;
    }
    let mounted = true;
    Promise.all([getTelemetry(compareRunId, 3), getRunNavigation(compareRunId, 3).catch(() => null)])
      .then(([series, navigation]) => {
        if (mounted) {
          setCompareTelemetry(telemetryWithNavigation(series, navigation));
        }
      })
      .catch(() => {
        if (mounted) {
          setCompareTelemetry(null);
        }
      });
    return () => {
      mounted = false;
    };
  }, [compareRunId, selectedRunId]);

  useEffect(() => {
    if (!playing || !telemetry?.history.length) {
      return;
    }
    const timer = window.setInterval(() => {
      setCurrentIndex((index) => (index + 1 >= telemetry.history.length ? 0 : index + 1));
    }, Math.max(18, 70 / playbackSpeed));
    return () => window.clearInterval(timer);
  }, [playing, playbackSpeed, telemetry]);

  const rememberJob = (job: JobSummary) => {
    setActiveJob(job);
    setJobHistory((items) => [job, ...items.filter((item) => item.id !== job.id)].slice(0, 30));
  };

  const pollJob = async (jobId: string) => {
    for (let attempt = 0; attempt < 360; attempt += 1) {
      const job = await getJob(jobId);
      rememberJob(job);
      if (job.status === "completed") {
        return job;
      }
      if (job.status === "failed" || job.status === "cancelled") {
        throw new Error(job.message || "Job failed");
      }
      await sleep(350);
    }
    throw new Error("Timed out waiting for job");
  };

  const waitForJob = async (jobId: string) => {
    if (!("EventSource" in window)) {
      return pollJob(jobId);
    }
    return new Promise<JobSummary>((resolve, reject) => {
      let settled = false;
      let streamed = false;
      const source = new EventSource(jobEventsUrl(jobId));
      const fallback = window.setTimeout(() => {
        if (!streamed && !settled) {
          settled = true;
          source.close();
          pollJob(jobId).then(resolve).catch(reject);
        }
      }, 1200);
      const finish = (handler: () => void) => {
        if (settled) {
          return;
        }
        settled = true;
        window.clearTimeout(fallback);
        source.close();
        handler();
      };
      source.onmessage = (event) => {
        streamed = true;
        const job = JSON.parse(event.data) as JobSummary;
        rememberJob(job);
        if (job.status === "completed") {
          finish(() => resolve(job));
        }
        if (job.status === "failed" || job.status === "cancelled") {
          finish(() => reject(new Error(job.message || "Job failed")));
        }
      };
      source.onerror = () => {
        if (!streamed) {
          finish(() => {
            pollJob(jobId).then(resolve).catch(reject);
          });
        }
      };
    });
  };

  const runTool = async (action: string, params: Record<string, unknown>, nextTab?: TabId) => {
    setBusyAction(action);
    setMessage("");
    try {
      const queued = await startJob(action, params);
      rememberJob(queued);
      const job = await waitForJob(queued.id);
      const result = job.result;
      if (!result) {
        throw new Error("Job completed without a result");
      }
      setResults((items) => [result, ...items].slice(0, 12));
      if (result.output_id && action === "run") {
        await refreshRuns(result.output_id);
      } else {
        await refreshRuns();
      }
      if (nextTab) {
        setActiveTab(nextTab);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusyAction("");
    }
  };

  const cancelActiveJob = async (jobId: string) => {
    try {
      const response = await cancelJob(jobId);
      rememberJob(response.job);
      setMessage("Cancellation requested");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Cancel failed");
    }
  };

  const retryExistingJob = async (_action: string, jobId: string) => {
    try {
      const job = await retryJob(jobId);
      rememberJob(job);
      await waitForJob(job.id);
      await refreshRuns();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Retry failed");
    }
  };

  const validateSelected = async () => {
    setBusyAction("validate");
    try {
      const validation = await validateScenario(selectedScenario);
      setResults((items) => [
        {
          action: "validate",
          status: validation.valid ? "completed" : "failed",
          message: validation.errors?.join("; ") ?? "",
          output_id: null,
          output_dir: null,
          data: validation,
          artifacts: []
        },
        ...items
      ]);
      setActiveTab("reports");
    } finally {
      setBusyAction("");
    }
  };

  const parseScenarioText = () => JSON.parse(scenarioText) as Record<string, unknown>;

  const validateDraft = async () => {
    setBusyAction("validate_draft");
    setMessage("");
    try {
      const parsed = parseScenarioText();
      const validation = await validateScenarioJson(parsed);
      setScenarioValidation(validation);
      setResults((items) => [
        {
          action: "validate draft",
          status: validation.valid ? "completed" : "failed",
          message: validation.errors?.join("; ") ?? "",
          output_id: null,
          output_dir: null,
          data: validation,
          artifacts: []
        },
        ...items
      ]);
    } catch (error) {
      setScenarioValidation({ valid: false, errors: [error instanceof Error ? error.message : "Invalid JSON"] });
      setMessage(error instanceof Error ? error.message : "Invalid JSON");
    } finally {
      setBusyAction("");
    }
  };

  const saveDraft = async () => {
    setBusyAction("save_draft");
    setMessage("");
    try {
      const parsed = parseScenarioText();
      const draft = await createScenarioDraft(parsed, String(parsed.name ?? "browser_scenario"));
      setDraftInfo(draft);
      setScenarioValidation({ valid: draft.valid, errors: draft.errors, path: draft.path });
      setResults((items) => [
        {
          action: "save draft",
          status: draft.valid ? "completed" : "failed",
          message: draft.errors.join("; "),
          output_id: null,
          output_dir: draft.path || null,
          data: draft,
          artifacts: []
        },
        ...items
      ]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Draft save failed");
    } finally {
      setBusyAction("");
    }
  };

  const runDraft = async () => {
    try {
      const parsed = parseScenarioText();
      await runTool("run", { scenario: parsed, run_name: String(parsed.name ?? "browser_scenario") }, "replay");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Draft run failed");
    }
  };

  const openExample = async (card: ExamplesGalleryCard) => {
    setMessage("");
    setSelectedScenario(card.id);
    setActiveTab("editor");
  };

  const cloneExample = async (card: ExamplesGalleryCard) => {
    setBusyAction("clone_example");
    setMessage("");
    try {
      const detail = await getScenario(card.id);
      const cloned = {
        ...detail.raw,
        name: `${String(detail.raw.name ?? detail.name)} Clone`
      };
      setSelectedScenario(card.id);
      setScenarioText(JSON.stringify(cloned, null, 2));
      setScenarioValidation(null);
      setDraftInfo(null);
      setActiveTab("editor");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Example clone failed");
    } finally {
      setBusyAction("");
    }
  };

  const runExample = async (card: ExamplesGalleryCard) => {
    await runTool("run", { scenario_id: card.id }, "replay");
  };

  const recordReportStudioExport = (request: ReportStudioExportRequest, payload: ReportStudioExportPayload | null) => {
    setResults((items) => [
      {
        action: "report_studio_export",
        status: payload ? "completed" : "failed",
        message: payload ? `${request.format.toUpperCase()} packet prepared in browser` : "No report packet loaded",
        output_id: selectedRunId || null,
        output_dir: runDetail?.run_dir ?? null,
        data: { request, payload },
        artifacts: runDetail?.artifacts ?? []
      },
      ...items
    ]);
  };

  const chartRows = useMemo(() => {
    if (!telemetry) {
      return [];
    }
    if (chartMode === "controls") {
      return telemetry.controls;
    }
    if (chartMode === "sensors") {
      return telemetry.sensors;
    }
    return telemetry.history;
  }, [chartMode, telemetry]);

  const availableChartChannels = useMemo(() => {
    if (!telemetry) {
      return [];
    }
    if (chartMode === "controls") {
      return telemetry.channels.controls ?? [];
    }
    if (chartMode === "sensors") {
      return telemetry.channels.sensors ?? [];
    }
    return telemetry.channels.history ?? [];
  }, [chartMode, telemetry]);

  const chartChannels = useMemo(() => {
    const selected = channelSelections[chartMode].filter((channel) => availableChartChannels.includes(channel));
    if (selected.length) {
      return selected.slice(0, 6);
    }
    return DEFAULT_CHANNELS[chartMode].filter((channel) => availableChartChannels.includes(channel)).slice(0, 6);
  }, [availableChartChannels, channelSelections, chartMode]);

  const addChartChannel = (channel: string) => {
    if (!channel) {
      return;
    }
    setInspectedChannel(channel);
    setChannelSelections((current) => {
      const existing = current[chartMode];
      if (existing.includes(channel)) {
        return current;
      }
      return { ...current, [chartMode]: [...existing, channel].slice(-6) };
    });
  };

  const removeChartChannel = (channel: string) => {
    setChannelSelections((current) => ({ ...current, [chartMode]: current[chartMode].filter((item) => item !== channel) }));
    setInspectedChannel((current) => (current === channel ? "" : current));
  };

  const acknowledgeAlarm = (id: string) => {
    setAcknowledgedAlarms((current) => ({ ...current, [id]: true }));
  };

  const jumpToReplayTime = (timeS: number) => {
    const rows = telemetry?.history ?? [];
    if (!rows.length || !Number.isFinite(timeS)) {
      return;
    }
    let nearestIndex = 0;
    let nearestDelta = Number.POSITIVE_INFINITY;
    rows.forEach((row, index) => {
      const value = numeric(row.time_s);
      if (value === null) {
        return;
      }
      const delta = Math.abs(value - timeS);
      if (delta < nearestDelta) {
        nearestDelta = delta;
        nearestIndex = index;
      }
    });
    setPlaying(false);
    setActiveTab("replay");
    setCurrentIndex(nearestIndex);
  };

  const jumpToTelemetryTime = (timeS: number) => {
    const rows = telemetry?.history ?? [];
    if (!rows.length || !Number.isFinite(timeS)) {
      return;
    }
    let nearestIndex = 0;
    let nearestDelta = Number.POSITIVE_INFINITY;
    rows.forEach((row, index) => {
      const value = numeric(row.time_s);
      if (value === null) {
        return;
      }
      const delta = Math.abs(value - timeS);
      if (delta < nearestDelta) {
        nearestDelta = delta;
        nearestIndex = index;
      }
    });
    setPlaying(false);
    setCurrentIndex(nearestIndex);
  };

  const adjustReplayScale = (delta: number) => {
    setReplayScale((value) => Number(clamp(value + delta, REPLAY_SCALE_MIN, REPLAY_SCALE_MAX).toFixed(2)));
  };

  const toggleReplayFullscreen = async () => {
    setReplayFullscreen((value) => !value);
  };

  const final = summaryFinal(runDetail);
  const currentRow = telemetry?.history[currentIndex];
  const chartRow = chartRows[Math.min(currentIndex, Math.max(chartRows.length - 1, 0))];
  const activeAlarms = activeAlarmCount(alarms);
  const activeParameterKey = chartChannels.includes(inspectedChannel) ? inspectedChannel : chartChannels[0];
  const replayStageStyle = { "--replay-scale": replayScale } as CSSProperties;
  const reportArtifacts = runDetail?.artifacts.filter((artifact) => artifact.kind === "report" || artifact.kind === "plot").slice(0, 8) ?? [];
  const dataArtifacts = runDetail?.artifacts.filter((artifact) => artifact.kind === "csv" || artifact.kind === "json").slice(0, 8) ?? [];
  const latestResult = results[0];
  const activeTabInfo = TABS.find((tab) => tab.id === activeTab) ?? TABS[0];
  const compareRunLabel = runs.find((run) => run.id === compareRunId)?.scenario ?? compareRunId;
  const replayRows = telemetry?.history ?? [];
  const replayOverlayState = useMemo(
    () =>
      buildReplayOverlayState(replayRows, currentIndex, {
        trailMode: trailColorMode,
        trailLegend: buildTrailColorLegendDescriptor(replayRows, trailColorMode),
        cameraMode,
        showVelocity,
        showAcceleration,
        showWind,
        showSensors
      }),
    [cameraMode, currentIndex, replayRows, showAcceleration, showSensors, showVelocity, showWind, trailColorMode]
  );
  const faultList = faults
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return (
    <main className={`workbench ${activeTab === "replay" ? "sim-mode" : ""}`}>
      <header className="workbench-top">
        <div className="brand-lockup">
          <button className="home-action" onClick={onHome} aria-label="Return home">
            <Home size={16} />
            Home
          </button>
          <div>
            <p className="eyebrow">AeroLab</p>
            <h1>Flight Simulator</h1>
          </div>
        </div>
        <nav className="tabs" aria-label="Workbench tabs">
          {TABS.map((tab) => (
            <button key={tab.id} className={activeTab === tab.id ? "active" : ""} onClick={() => setActiveTab(tab.id)}>
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="status-cluster">
          <span>
            <Activity size={16} />
            {activeJob && activeJob.status !== "completed" ? `${activeJob.action}: ${activeJob.status}` : busyAction || runDetail?.status || "standby"}
          </span>
          <span>
            <Gauge size={16} />
            {currentTime(telemetry?.history ?? [], currentIndex)}
          </span>
        </div>
      </header>

      <section className="workbench-scroll">
        {activeJob && activeJob.status !== "completed" && (
          <div className="job-rail">
            <Loader2 className="spin" size={17} />
            <strong>{activeJob.action.replaceAll("_", " ")}</strong>
            <span>{activeJob.status}</span>
            <span>{activeJob.message}</span>
            <div className="job-progress" aria-label="Job progress">
              <i style={{ width: `${Math.max(3, Math.round(activeJob.progress * 100))}%` }} />
            </div>
          </div>
        )}

        <section className="console-overview">
          <div>
            <p className="eyebrow">Simulation Surface</p>
            <h2>{activeTabInfo.title}</h2>
            <p>{activeTabInfo.subtitle}</p>
          </div>
          <div className="console-facts" aria-label="Workspace summary">
            <span>
              <strong>{runs.length}</strong>
              runs
            </span>
            <span>
              <strong>{scenarios.length}</strong>
              scenarios
            </span>
            <span>
              <strong>{telemetry?.sample_count ?? 0}</strong>
              samples
            </span>
          </div>
        </section>

        {activeTab === "replay" && (
          <div className="replay-layout">
            <section className={`replay-stage ${replayFullscreen ? "is-expanded" : ""}`} style={replayStageStyle}>
              <div className="stage-header">
                <div>
                  <p>{runDetail?.scenario ?? "No run selected"}</p>
                  <h2>{formatMetric(currentRow?.altitude_m, " m", 1)} altitude</h2>
                </div>
                <div className="stage-actions">
                  <div className="mini-segment">
                    {(["range", "coast", "night"] as EnvironmentMode[]).map((mode) => (
                      <button key={mode} className={environmentMode === mode ? "active" : ""} onClick={() => setEnvironmentMode(mode)}>
                        {mode}
                      </button>
                    ))}
                  </div>
                  <div className="mini-segment">
                    {(["chase", "orbit", "cockpit", "map", "rangeSafety"] as CameraMode[]).map((mode) => (
                      <button key={mode} className={cameraMode === mode ? "active" : ""} onClick={() => setCameraMode(mode)}>
                        {mode === "rangeSafety" ? "Range Safety" : mode}
                      </button>
                    ))}
                  </div>
                  <button className="icon-action" onClick={() => setPlaying((value) => !value)} disabled={!telemetry?.history.length}>
                    {playing ? <RotateCcw size={18} /> : <Play size={18} />}
                    {playing ? "Loop" : "Play"}
                  </button>
                  <div className="viewer-tools" aria-label="Replay viewport controls">
                    <button type="button" aria-label="Shrink replay viewport" onClick={() => adjustReplayScale(-REPLAY_SCALE_STEP)} disabled={replayScale <= REPLAY_SCALE_MIN}>
                      <ZoomOut size={16} />
                    </button>
                    <span>{Math.round(replayScale * 100)}%</span>
                    <button type="button" aria-label="Enlarge replay viewport" onClick={() => adjustReplayScale(REPLAY_SCALE_STEP)} disabled={replayScale >= REPLAY_SCALE_MAX}>
                      <ZoomIn size={16} />
                    </button>
                    <button type="button" aria-label={replayFullscreen ? "Exit replay fullscreen" : "Open replay fullscreen"} onClick={toggleReplayFullscreen}>
                      {replayFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                    </button>
                  </div>
                </div>
              </div>
              <ReplayScene
                rows={replayRows}
                currentIndex={currentIndex}
                environmentMode={environmentMode}
                cameraMode={cameraMode}
                showTrail={showTrail}
                showAxes={showAxes}
                showWind={showWind}
                showVelocity={showVelocity}
                showAcceleration={showAcceleration}
                showSensors={showSensors}
                trailColorMode={trailColorMode}
              />
              <ReplaySceneOverlayLegend overlayState={replayOverlayState} compact={replayFullscreen} />
              <div className="scrubber">
                <button
                  className="timeline-toggle"
                  type="button"
                  onClick={() => setPlaying((value) => !value)}
                  disabled={!telemetry?.history.length}
                  aria-label={playing ? "Pause replay" : "Play replay"}
                >
                  {playing ? <Pause size={17} /> : <Play size={17} />}
                  <span>{playing ? "Pause" : "Play"}</span>
                </button>
                <input
                  type="range"
                  min="0"
                  max={Math.max((telemetry?.history.length ?? 1) - 1, 0)}
                  value={currentIndex}
                  onChange={(event) => setCurrentIndex(Number(event.target.value))}
                />
                <div className="speed-strip" aria-label="Playback speed">
                  {[0.5, 1, 2, 4].map((speed) => (
                    <button key={speed} className={playbackSpeed === speed ? "active" : ""} onClick={() => setPlaybackSpeed(speed)}>
                      {speed}x
                    </button>
                  ))}
                </div>
                <span>{telemetry?.sample_count ?? 0} samples</span>
              </div>
            </section>

            <aside className="replay-side">
              <SelectField label="Run" value={selectedRunId} onChange={setSelectedRunId} options={runOptions} />
              <div className="metric-grid">
                <div>
                  <span>Speed</span>
                  <strong>{formatMetric(currentRow?.speed_mps ?? runDetail?.summary.max_speed_mps, " m/s", 1)}</strong>
                </div>
                <div>
                  <span>Load</span>
                  <strong>{formatMetric(currentRow?.load_factor_g ?? runDetail?.summary.max_load_factor_g, " g", 2)}</strong>
                </div>
                <div>
                  <span>Qbar</span>
                  <strong>{formatMetric(currentRow?.qbar_pa ?? runDetail?.summary.max_qbar_pa, " Pa", 0)}</strong>
                </div>
                <div>
                  <span>Target Range</span>
                  <strong>{formatMetric(currentRow?.target_range_m ?? runDetail?.summary.min_target_range_m, " m", 1)}</strong>
                </div>
                <div>
                  <span>Closing</span>
                  <strong>{formatMetric(currentRow?.closing_speed_mps ?? runDetail?.summary.max_closing_speed_mps, " m/s", 1)}</strong>
                </div>
                <div>
                  <span>Interceptor</span>
                  <strong>{formatMetric(currentRow?.interceptor_range_m ?? runDetail?.summary.min_interceptor_range_m, " m", 1)}</strong>
                </div>
                <div>
                  <span>Fuzes</span>
                  <strong>{formatMetric(runDetail?.summary.interceptor_fuze_count, "", 0)}</strong>
                </div>
                <div>
                  <span>Final Alt</span>
                  <strong>{formatMetric(final.altitude_m, " m", 1)}</strong>
                </div>
                <div>
                  <span>Active Alarms</span>
                  <strong>{activeAlarms}</strong>
                </div>
              </div>
              <section className="side-section">
                <div className="section-title">
                  <Camera size={16} />
                  <h3>View</h3>
                </div>
                <div className="readout-grid">
                  <span>{cameraMode}</span>
                  <span>{environmentMode}</span>
                  <span>{trailColorMode}</span>
                </div>
                <div className="toggle-row dense">
                  <button className={showTrail ? "active" : ""} onClick={() => setShowTrail((value) => !value)}>Trail</button>
                  <button className={showAxes ? "active" : ""} onClick={() => setShowAxes((value) => !value)}>Axes</button>
                  <button className={showWind ? "active" : ""} onClick={() => setShowWind((value) => !value)}>Wind</button>
                  <button className={showVelocity ? "active" : ""} onClick={() => setShowVelocity((value) => !value)}>Velocity</button>
                  <button className={showAcceleration ? "active" : ""} onClick={() => setShowAcceleration((value) => !value)}>Accel</button>
                  <button className={showSensors ? "active" : ""} onClick={() => setShowSensors((value) => !value)}>Sensors</button>
                </div>
                <label className="field compact-field">
                  <span>Trail Color</span>
                  <select value={trailColorMode} onChange={(event) => setTrailColorMode(event.target.value as TrailColorMode)}>
                    {(["plain", "speed", "qbar", "load", "altitude"] as TrailColorMode[]).map((mode) => (
                      <option key={mode} value={mode}>
                        {mode}
                      </option>
                    ))}
                  </select>
                </label>
              </section>
              <ActiveAlarmsPanel alarms={alarms} acknowledged={acknowledgedAlarms} onAcknowledge={acknowledgeAlarm} onJump={jumpToReplayTime} />
              <section className="side-section">
                <div className="section-title">
                  <ShieldAlert size={16} />
                  <h3>Events</h3>
                </div>
                <div className="event-list">
                  {(runDetail?.events ?? []).slice(0, 6).map((event, index) => (
                    <div className="event-item" key={`${String(event.type)}-${index}`}>
                      <span>{formatMetric(event.time_s, "s", 2)}</span>
                      <strong>{String(event.type ?? "event").replaceAll("_", " ")}</strong>
                      <p>{String(event.description ?? "")}</p>
                    </div>
                  ))}
                  {runDetail && runDetail.events.length === 0 && <div className="empty-state">No events</div>}
                </div>
              </section>
              <AlarmHistoryPanel alarms={alarms} acknowledged={acknowledgedAlarms} onAcknowledge={acknowledgeAlarm} onJump={jumpToReplayTime} />
            </aside>

            <section className="telemetry-panel wide">
              <div className="telemetry-header">
                <div className="section-title">
                  <BarChart3 size={16} />
                  <h3>Telemetry</h3>
                </div>
                <div className="telemetry-tools">
                  <div className="mini-segment">
                    {(["flight", "intercept", "controls", "sensors"] as ChartMode[]).map((mode) => (
                      <button key={mode} className={chartMode === mode ? "active" : ""} onClick={() => setChartMode(mode)}>
                        {mode}
                      </button>
                    ))}
                  </div>
                  <select aria-label="Add telemetry channel" value="" onChange={(event) => addChartChannel(event.target.value)}>
                    <option value="">add channel</option>
                    {availableChartChannels.map((channel) => (
                      <option key={channel} value={channel}>
                        {channelLabelWithUnit(telemetry?.metadata, channel)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="channel-strip">
                {chartChannels.map((channel) => (
                  <span key={channel} className={`channel-chip ${activeParameterKey === channel ? "active" : ""}`}>
                    <button type="button" onClick={() => setInspectedChannel(channel)}>
                      {channelLabel(telemetry?.metadata, channel)}
                    </button>
                    <button type="button" aria-label={`Remove ${channel}`} onClick={() => removeChartChannel(channel)}>
                      x
                    </button>
                  </span>
                ))}
              </div>
              <ParameterInfoPanel channel={activeParameterKey} row={chartRow} metadata={telemetry?.metadata} />
              <TelemetryChart title={chartMode} rows={chartRows} channels={chartChannels} currentIndex={currentIndex} metadata={telemetry?.metadata} />
            </section>
          </div>
        )}

        {activeTab === "telemetry" && (
          <div className="telemetry-ops-shell">
            <section className="telemetry-ops-runbar">
              <SelectField label="Run" value={selectedRunId} onChange={setSelectedRunId} options={runOptions} />
              <SelectField label="Compare" value={compareRunId} onChange={setCompareRunId} options={runOptions.filter((run) => run.id !== selectedRunId)} />
              <div className="telemetry-ops-runmeta">
                <span>{runDetail?.scenario ?? "no selected run"}</span>
                <strong>{telemetry?.sample_count ?? 0} samples</strong>
                <span>{compareTelemetry ? `compare: ${compareRunLabel}` : "comparison optional"}</span>
              </div>
            </section>
            <OperationsTelemetryPanel
              telemetry={telemetry}
              currentIndex={currentIndex}
              onJumpIndex={setCurrentIndex}
              onJumpTime={jumpToTelemetryTime}
              metadata={telemetry?.metadata}
              compareTelemetry={compareTelemetry}
              compareRunLabel={compareRunLabel}
              alarms={alarms}
              events={runDetail?.events}
            />
          </div>
        )}

        {activeTab === "launch" && (
          <div className="tool-grid">
            <ActionCard title="Scenario" icon={<Route size={18} />} running={busyAction === "run"} onRun={() => runTool("run", { scenario_id: selectedScenario }, "replay")}>
              <SelectField label="Scenario" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
              <button className="secondary-action" onClick={validateSelected} disabled={busyAction === "validate"}>
                Validate
              </button>
            </ActionCard>
            <ActionCard
              title="Compare"
              icon={<ScanLine size={18} />}
              running={busyAction === "compare_runs"}
              onRun={() => runTool("compare_runs", { run_a_id: selectedRunId, run_b_id: compareRunId }, "reports")}
            >
              <SelectField label="A" value={selectedRunId} onChange={setSelectedRunId} options={runOptions} />
              <SelectField label="B" value={compareRunId} onChange={setCompareRunId} options={runOptions} />
            </ActionCard>
            <ActionCard title="Report" icon={<FileJson size={18} />} running={busyAction === "report"} onRun={() => runTool("report", { run_id: selectedRunId }, "reports")}>
              <SelectField label="Run" value={selectedRunId} onChange={setSelectedRunId} options={runOptions} />
            </ActionCard>
            <ActionCard title="Engagement" icon={<ScanLine size={18} />} running={busyAction === "engagement_report"} onRun={() => runTool("engagement_report", { run_id: selectedRunId }, "reports")}>
              <SelectField label="Run" value={selectedRunId} onChange={setSelectedRunId} options={runOptions} />
            </ActionCard>
            <ActionCard
              title="Sensors"
              icon={<RadioTower size={18} />}
              running={busyAction === "sensor_report"}
              onRun={() => runTool("sensor_report", { run_id: selectedRunId }, "reports")}
            >
              <SelectField label="Run" value={selectedRunId} onChange={setSelectedRunId} options={runOptions} />
            </ActionCard>
          </div>
        )}

        {activeTab === "campaigns" && (
          <div className="stacked-surface">
            <CampaignDesigner
              scenarios={scenarios}
              capabilities={capabilities}
              busyAction={busyAction}
              initialDraft={{ scenarioId: selectedScenario }}
              onDraftChange={(draft) => {
                if (draft.scenarioId && draft.scenarioId !== selectedScenario) {
                  setSelectedScenario(draft.scenarioId);
                }
              }}
              onRunPlan={({ action, params }) => runTool(action, params, "reports")}
            />
            <div className="tool-grid compact-tool-grid">
              <ActionCard title="Batch" icon={<Boxes size={18} />} running={busyAction === "batch"} onRun={() => runTool("batch", {}, "reports")} />
              <ActionCard
                title="Monte Carlo"
                icon={<Sparkles size={18} />}
                running={busyAction === "monte_carlo"}
                onRun={() => runTool("monte_carlo", { scenario_id: selectedScenario, samples: Number(mcSamples), seed: 77, mass_sigma_kg: 0.2, wind_sigma_mps: 0.1 }, "reports")}
              >
                <SelectField label="Scenario" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
                <TextField label="Samples" value={mcSamples} onChange={setMcSamples} />
              </ActionCard>
              <ActionCard
                title="Sweep"
                icon={<Settings2 size={18} />}
                running={busyAction === "sweep"}
                onRun={() => runTool("sweep", { scenario_id: selectedScenario, parameter: sweepParameter, values: sweepValues, max_runs: 20 }, "reports")}
              >
                <SelectField label="Scenario" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
                <TextField label="Path" value={sweepParameter} onChange={setSweepParameter} />
                <TextField label="Values" value={sweepValues} onChange={setSweepValues} />
              </ActionCard>
              <ActionCard
                title="Faults"
                icon={<ShieldAlert size={18} />}
                running={busyAction === "fault_campaign"}
                onRun={() => runTool("fault_campaign", { scenario_id: selectedScenario, faults: faultList }, "reports")}
              >
                <SelectField label="Scenario" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
                <TextField label="Faults" value={faults} onChange={setFaults} />
              </ActionCard>
            </div>
          </div>
        )}

        {activeTab === "engineering" && (
          <div className="tool-grid">
            <ActionCard title="Trim" icon={<Gauge size={18} />} running={busyAction === "trim"} onRun={() => runTool("trim", { vehicle_id: selectedVehicle, speed_mps: 120, altitude_m: 1000 }, "reports")}>
              <SelectField label="Vehicle" value={selectedVehicle} onChange={setSelectedVehicle} options={vehicleOptions} />
            </ActionCard>
            <ActionCard
              title="Trim Sweep"
              icon={<BarChart3 size={18} />}
              running={busyAction === "trim_sweep"}
              onRun={() => runTool("trim_sweep", { vehicle_id: selectedVehicle, speeds, altitudes }, "reports")}
            >
              <SelectField label="Vehicle" value={selectedVehicle} onChange={setSelectedVehicle} options={vehicleOptions} />
              <TextField label="Speeds" value={speeds} onChange={setSpeeds} />
              <TextField label="Altitudes" value={altitudes} onChange={setAltitudes} />
            </ActionCard>
            <ActionCard
              title="Linearize"
              icon={<Compass size={18} />}
              running={busyAction === "linearize"}
              onRun={() => runTool("linearize", { scenario_id: selectedScenario, time_s: Number(linearTime) }, "reports")}
            >
              <SelectField label="Scenario" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
              <TextField label="Time" value={linearTime} onChange={setLinearTime} />
            </ActionCard>
            <ActionCard
              title="Stability"
              icon={<Layers3 size={18} />}
              running={busyAction === "stability"}
              onRun={() => runTool("stability", { scenario_id: selectedScenario, time_s: Number(linearTime) }, "reports")}
            >
              <SelectField label="Scenario" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
              <TextField label="Time" value={linearTime} onChange={setLinearTime} />
            </ActionCard>
            <ActionCard
              title="Linear Model"
              icon={<Braces size={18} />}
              running={busyAction === "linear_model_report"}
              onRun={() => runTool("linear_model_report", { scenario_id: selectedScenario, time_s: Number(linearTime) }, "reports")}
            >
              <SelectField label="Scenario" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
              <TextField label="Time" value={linearTime} onChange={setLinearTime} />
            </ActionCard>
          </div>
        )}

        {activeTab === "models" && (
          <div className="stacked-surface">
            <ExamplesGallery
              cards={examplesGallery}
              selectedId={selectedScenario}
              onOpen={openExample}
              onClone={cloneExample}
              onRun={runExample}
            />
            <div className="tool-grid compact-tool-grid">
              <ActionCard title="Vehicle" icon={<FileJson size={18} />} running={busyAction === "inspect_vehicle"} onRun={() => runTool("inspect_vehicle", { vehicle_id: selectedVehicle }, "reports")}>
                <SelectField label="Vehicle" value={selectedVehicle} onChange={setSelectedVehicle} options={vehicleOptions} />
              </ActionCard>
              <ActionCard title="Diff" icon={<ScanLine size={18} />} running={busyAction === "config_diff"} onRun={() => runTool("config_diff", { vehicle_a_id: selectedVehicle, vehicle_b_id: secondVehicle }, "reports")}>
                <SelectField label="A" value={selectedVehicle} onChange={setSelectedVehicle} options={vehicleOptions} />
                <SelectField label="B" value={secondVehicle} onChange={setSecondVehicle} options={vehicleOptions} />
              </ActionCard>
              <ActionCard title="Scenario" icon={<Route size={18} />} running={busyAction === "generate_scenario"} onRun={() => runTool("generate_scenario", { name: generatedName }, "reports")}>
                <TextField label="Name" value={generatedName} onChange={setGeneratedName} />
              </ActionCard>
              <ActionCard title="Aero" icon={<Compass size={18} />} running={busyAction === "aero_report"} onRun={() => runTool("aero_report", { vehicle_id: selectedVehicle }, "reports")}>
                <SelectField label="Vehicle" value={selectedVehicle} onChange={setSelectedVehicle} options={vehicleOptions} />
                <button className="secondary-action" onClick={() => runTool("inspect_aero", { vehicle_id: selectedVehicle }, "reports")}>Inspect</button>
                <button className="secondary-action" onClick={() => runTool("aero_sweep", { vehicle_id: selectedVehicle }, "reports")}>Sweep</button>
              </ActionCard>
              <ActionCard title="Propulsion" icon={<Activity size={18} />} running={busyAction === "thrust_curve_report"} onRun={() => runTool("thrust_curve_report", { vehicle_id: selectedVehicle }, "reports")}>
                <SelectField label="Vehicle" value={selectedVehicle} onChange={setSelectedVehicle} options={vehicleOptions} />
                <button className="secondary-action" onClick={() => runTool("inspect_propulsion", { vehicle_id: selectedVehicle }, "reports")}>Inspect</button>
              </ActionCard>
              <ActionCard
                title="Environment"
                icon={<RadioTower size={18} />}
                running={busyAction === "environment_report"}
                onRun={() => runTool("environment_report", { environment_id: selectedEnvironment }, "reports")}
              >
                <SelectField label="Environment" value={selectedEnvironment} onChange={setSelectedEnvironment} options={environmentOptions} />
              </ActionCard>
            </div>
          </div>
        )}

        {activeTab === "editor" && (
          <div className="editor-shell">
            <section className="editor-panel scenario-builder-shell">
              <div className="editor-header">
                <div className="section-title">
                  <TerminalSquare size={17} />
                  <div>
                    <p className="eyebrow">Mission Design Tool</p>
                    <h3>Scenario Builder v2</h3>
                  </div>
                </div>
                <SelectField label="Base" value={selectedScenario} onChange={setSelectedScenario} options={scenarioOptions} />
              </div>
              <ScenarioBuilderV2
                scenarioText={scenarioText}
                onScenarioTextChange={(value) => {
                  setScenarioText(value);
                  setScenarioValidation(null);
                  setDraftInfo(null);
                }}
                vehicles={vehicles}
                environments={environments}
                selectedVehicle={selectedVehicle}
                selectedEnvironment={selectedEnvironment}
                onSelectedVehicleChange={setSelectedVehicle}
                onSelectedEnvironmentChange={setSelectedEnvironment}
                onValidate={validateDraft}
                onSave={saveDraft}
                onRun={runDraft}
                busyAction={busyAction}
                validation={scenarioValidation}
              />
              {draftInfo && (
                <div className="result-head">
                  <strong>{draftInfo.name}</strong>
                  <span>{draftInfo.path}</span>
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === "reports" && (
          <div className="reports-layout">
            <section className="report-panel report-studio-panel">
              <div className="section-row">
                <div className="section-title">
                  <FileJson size={16} />
                  <h3>Mission Packet</h3>
                </div>
                {reportLoading && <Loader2 className="spin" size={16} />}
              </div>
              <ReportStudio packet={reportPacket} onExportRequest={recordReportStudioExport} />
            </section>
            <section className="report-panel">
              <div className="section-title">
                <FileJson size={16} />
                <h3>Latest</h3>
              </div>
              {latestResult ? (
                <>
                  <div className="result-head">
                    <strong>{latestResult.action}</strong>
                    <span>{latestResult.output_dir ?? "data only"}</span>
                  </div>
                  <div className="artifact-links">
                    {latestResult.artifacts.slice(0, 24).map((artifact) => (
                      <a key={artifact.path} href={artifact.url} target="_blank" rel="noreferrer">
                        {artifact.name}
                      </a>
                    ))}
                  </div>
                  <pre>{compactJson(latestResult.data)}</pre>
                </>
              ) : (
                <div className="empty-state">No results yet</div>
              )}
            </section>
            <section className="report-panel">
              <div className="section-title">
                <RadioTower size={16} />
                <h3>Run Artifacts</h3>
              </div>
              <SelectField label="Run" value={selectedRunId} onChange={setSelectedRunId} options={runOptions} />
              <div className="artifact-links spacious">
                {[...reportArtifacts, ...dataArtifacts].map((artifact) => (
                  <a key={artifact.path} href={artifact.url} target="_blank" rel="noreferrer">
                    {artifact.name}
                  </a>
                ))}
              </div>
            </section>
            <section className="report-panel">
              <div className="section-title">
                <Settings2 size={16} />
                <h3>Surface</h3>
              </div>
              <div className="metric-grid">
                <div>
                  <span>Storage</span>
                  <strong>{storageStatus?.persistent ? "persistent" : "local"}</strong>
                </div>
                <div>
                  <span>Writable</span>
                  <strong>{storageStatus?.writable ? "yes" : "check"}</strong>
                </div>
              </div>
              <div className="capability-list">
                {capabilities.map((capability) => (
                  <span key={capability.id}>{capability.label}</span>
                ))}
              </div>
            </section>
            <LiveProgressPanel jobs={jobHistory} onCancel={cancelActiveJob} onRetry={retryExistingJob} />
          </div>
        )}
      </section>

      {message && <div className="toast">{message}</div>}
    </main>
  );
}
