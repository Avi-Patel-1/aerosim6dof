import type { Capability, ScenarioSummary } from "./types";

export type CampaignPlanKind = "batch" | "monte_carlo" | "sweep" | "fault_campaign";

export type CampaignActionName = "batch" | "monte_carlo" | "sweep" | "fault_campaign";

export type CampaignDesignerDraft = {
  kind: CampaignPlanKind;
  scenarioId: string;
  samples: number;
  seed: number;
  massSigmaKg: number;
  windSigmaMps: number;
  sweepParameter: string;
  sweepValues: string;
  sweepMaxRuns: number;
  faultText: string;
  faultMaxRuns: number;
};

export type CampaignActionPayload = {
  action: CampaignActionName;
  params: Record<string, unknown>;
};

export type CampaignValidationIssue = {
  field: string;
  message: string;
};

export type CampaignValidation = {
  valid: boolean;
  errors: CampaignValidationIssue[];
  warnings: CampaignValidationIssue[];
  estimatedRuns: number;
};

export type CampaignIssueMap = Partial<Record<keyof CampaignDesignerDraft | "dispersions" | "batch", CampaignValidationIssue[]>>;

export type CampaignSummaryRow = {
  label: string;
  value: string;
};

export type CampaignPlanSummary = {
  title: string;
  description: string;
  rows: CampaignSummaryRow[];
};

export type CampaignPlanModel = {
  kind: CampaignPlanKind;
  label: string;
  payload: CampaignActionPayload;
  validation: CampaignValidation;
  summary: CampaignPlanSummary;
  issueMap: CampaignIssueMap;
  canLaunch: boolean;
  runCountLabel: string;
  launchRouteHint: string;
};

export const DEFAULT_FAULT_OPTIONS = [
  "barometer_bias",
  "gps_dropout",
  "imu_bias",
  "mag_dropout",
  "pitot_blockage",
  "stuck_elevator",
  "thrust_loss"
];

export const CAMPAIGN_KIND_LABELS: Record<CampaignPlanKind, string> = {
  batch: "Batch",
  monte_carlo: "Monte Carlo",
  sweep: "Parameter Sweep",
  fault_campaign: "Fault Campaign"
};

const DEFAULT_SWEEP_VALUES = "0.82,0.86";
const MONTE_CARLO_SAMPLE_LIMIT = 50;
const SWEEP_RUN_LIMIT = 100;
const FAULT_RUN_LIMIT = 50;
const DECIMAL_VALUE_PATTERN = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;
const DOTTED_PATH_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$/;

export function createDefaultCampaignDraft(scenarioId = "nominal_ascent", faultOptions = DEFAULT_FAULT_OPTIONS): CampaignDesignerDraft {
  return {
    kind: "monte_carlo",
    scenarioId,
    samples: 8,
    seed: 77,
    massSigmaKg: 0.2,
    windSigmaMps: 0.1,
    sweepParameter: "guidance.throttle",
    sweepValues: DEFAULT_SWEEP_VALUES,
    sweepMaxRuns: 20,
    faultText: faultOptions.slice(0, 2).join(","),
    faultMaxRuns: 12
  };
}

export function scenarioLabel(scenarios: ScenarioSummary[], scenarioId: string): string {
  const scenario = scenarios.find((item) => item.id === scenarioId);
  return scenario?.name || scenarioId || "No scenario selected";
}

export function faultsFromCapabilities(capabilities: Capability[] = []): string[] {
  const faultCampaign = capabilities.find((capability) => capability.id === "fault_campaign");
  return faultCampaign?.faults?.length ? [...faultCampaign.faults].sort() : DEFAULT_FAULT_OPTIONS;
}

export function parseCsvList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseSweepValues(value: string): Array<number | string> {
  return parseCsvList(value).map((item) => {
    const numeric = DECIMAL_VALUE_PATTERN.test(item) ? Number(item) : Number.NaN;
    return Number.isFinite(numeric) ? numeric : item;
  });
}

export function buildCampaignActionPayload(draft: CampaignDesignerDraft): CampaignActionPayload {
  if (draft.kind === "batch") {
    return { action: "batch", params: {} };
  }
  if (draft.kind === "monte_carlo") {
    return {
      action: "monte_carlo",
      params: {
        scenario_id: draft.scenarioId,
        samples: draft.samples,
        seed: draft.seed,
        mass_sigma_kg: draft.massSigmaKg,
        wind_sigma_mps: draft.windSigmaMps
      }
    };
  }
  if (draft.kind === "sweep") {
    return {
      action: "sweep",
      params: {
        scenario_id: draft.scenarioId,
        parameter: draft.sweepParameter.trim(),
        values: parseSweepValues(draft.sweepValues),
        max_runs: draft.sweepMaxRuns
      }
    };
  }
  return {
    action: "fault_campaign",
    params: {
      scenario_id: draft.scenarioId,
      faults: parseCsvList(draft.faultText),
      max_runs: draft.faultMaxRuns
    }
  };
}

export function estimateCampaignRuns(draft: CampaignDesignerDraft, options: { scenarios?: ScenarioSummary[]; faultOptions?: string[] } = {}): number {
  if (draft.kind === "batch") {
    return options.scenarios?.length ?? 0;
  }
  if (draft.kind === "monte_carlo") {
    return Number.isInteger(draft.samples) ? Math.max(0, draft.samples) : 0;
  }
  if (draft.kind === "sweep") {
    return parseSweepValues(draft.sweepValues).length;
  }
  const faults = parseCsvList(draft.faultText);
  return faults.length || options.faultOptions?.length || DEFAULT_FAULT_OPTIONS.length;
}

export function issueMapFromValidation(validation: CampaignValidation): CampaignIssueMap {
  const issueMap: CampaignIssueMap = {};
  for (const issue of [...validation.errors, ...validation.warnings]) {
    const key = issue.field as keyof CampaignIssueMap;
    issueMap[key] = [...(issueMap[key] ?? []), issue];
  }
  return issueMap;
}

export function validateCampaignDraft(draft: CampaignDesignerDraft, options: { scenarios?: ScenarioSummary[]; faultOptions?: string[] } = {}): CampaignValidation {
  const errors: CampaignValidationIssue[] = [];
  const warnings: CampaignValidationIssue[] = [];
  const scenarioIds = new Set((options.scenarios ?? []).map((scenario) => scenario.id));
  const faultOptions = options.faultOptions?.length ? options.faultOptions : DEFAULT_FAULT_OPTIONS;
  const knownFaults = new Set(faultOptions);
  let estimatedRuns = estimateCampaignRuns(draft, { scenarios: options.scenarios, faultOptions });

  if (draft.kind === "batch" && options.scenarios && options.scenarios.length === 0) {
    warnings.push({ field: "batch", message: "No scenario index is loaded yet; the backend batch action will still use its configured scenario directory." });
  }

  if (draft.kind !== "batch") {
    if (!draft.scenarioId) {
      errors.push({ field: "scenarioId", message: "Select a scenario." });
    } else if (scenarioIds.size > 0 && !scenarioIds.has(draft.scenarioId)) {
      errors.push({ field: "scenarioId", message: `Scenario ${draft.scenarioId} is not in the loaded scenario index.` });
    }
  }

  if (draft.kind === "monte_carlo") {
    if (!Number.isInteger(draft.samples) || draft.samples < 1 || draft.samples > MONTE_CARLO_SAMPLE_LIMIT) {
      errors.push({ field: "samples", message: `Samples must be an integer from 1 to ${MONTE_CARLO_SAMPLE_LIMIT}.` });
    }
    if (!Number.isInteger(draft.seed)) {
      errors.push({ field: "seed", message: "Seed must be an integer." });
    }
    if (!Number.isFinite(draft.massSigmaKg) || draft.massSigmaKg < 0) {
      errors.push({ field: "massSigmaKg", message: "Mass sigma must be zero or positive." });
    }
    if (!Number.isFinite(draft.windSigmaMps) || draft.windSigmaMps < 0) {
      errors.push({ field: "windSigmaMps", message: "Wind sigma must be zero or positive." });
    }
    if (draft.massSigmaKg === 0 && draft.windSigmaMps === 0) {
      warnings.push({ field: "dispersions", message: "Both dispersions are zero, so each sample will be nearly identical aside from seeded sensor effects." });
    }
  }

  if (draft.kind === "sweep") {
    const parameter = draft.sweepParameter.trim();
    const values = parseSweepValues(draft.sweepValues);
    if (!parameter) {
      errors.push({ field: "sweepParameter", message: "Enter a scenario parameter path." });
    } else if (!DOTTED_PATH_PATTERN.test(parameter)) {
      errors.push({ field: "sweepParameter", message: "Use a dotted scenario path such as guidance.throttle." });
    }
    if (values.length === 0) {
      errors.push({ field: "sweepValues", message: "Enter at least one sweep value." });
    }
    if (values.length === 1) {
      warnings.push({ field: "sweepValues", message: "Only one value is listed, so this will behave like a single scenario run." });
    }
    if (!Number.isInteger(draft.sweepMaxRuns) || draft.sweepMaxRuns < 1 || draft.sweepMaxRuns > SWEEP_RUN_LIMIT) {
      errors.push({ field: "sweepMaxRuns", message: `Max runs must be an integer from 1 to ${SWEEP_RUN_LIMIT}.` });
    } else if (values.length > draft.sweepMaxRuns) {
      errors.push({ field: "sweepValues", message: `The sweep expands to ${values.length} runs, above max runs ${draft.sweepMaxRuns}.` });
    }
  }

  if (draft.kind === "fault_campaign") {
    const faults = parseCsvList(draft.faultText);
    const unknown = faults.filter((fault) => !knownFaults.has(fault));
    if (unknown.length) {
      errors.push({ field: "faultText", message: `Unknown fault name${unknown.length === 1 ? "" : "s"}: ${unknown.join(", ")}.` });
    }
    if (!Number.isInteger(draft.faultMaxRuns) || draft.faultMaxRuns < 1 || draft.faultMaxRuns > FAULT_RUN_LIMIT) {
      errors.push({ field: "faultMaxRuns", message: `Max runs must be an integer from 1 to ${FAULT_RUN_LIMIT}.` });
    } else if (estimatedRuns > draft.faultMaxRuns) {
      errors.push({ field: "faultText", message: `The fault plan expands to ${estimatedRuns} runs, above max runs ${draft.faultMaxRuns}.` });
    }
    if (!faults.length) {
      warnings.push({ field: "faultText", message: "No explicit faults are selected, so the API will run every built-in fault." });
    }
  }

  return { valid: errors.length === 0, errors, warnings, estimatedRuns: Math.max(estimatedRuns, 0) };
}

export function runCountLabel(estimatedRuns: number): string {
  return `${estimatedRuns} planned run${estimatedRuns === 1 ? "" : "s"}`;
}

export function summarizeCampaignPlan(draft: CampaignDesignerDraft, scenarios: ScenarioSummary[] = [], faultOptions = DEFAULT_FAULT_OPTIONS): CampaignPlanSummary {
  const scenario = scenarioLabel(scenarios, draft.scenarioId);
  const estimatedRuns = estimateCampaignRuns(draft, { scenarios, faultOptions });
  if (draft.kind === "batch") {
    return {
      title: "Batch scenario suite",
      description: "Runs every checked-in example scenario through the existing batch action.",
      rows: [
        { label: "Action", value: "batch" },
        { label: "Scenario source", value: "examples/scenarios" },
        { label: "Estimated runs", value: scenarios.length ? String(estimatedRuns) : "Backend scenario directory" }
      ]
    };
  }
  if (draft.kind === "monte_carlo") {
    return {
      title: `${scenario} Monte Carlo`,
      description: `Runs ${estimatedRuns} seeded sample${estimatedRuns === 1 ? "" : "s"} with mass and wind dispersions.`,
      rows: [
        { label: "Action", value: "monte_carlo" },
        { label: "Scenario", value: scenario },
        { label: "Samples", value: String(draft.samples) },
        { label: "Seed", value: String(draft.seed) },
        { label: "Mass sigma", value: `${draft.massSigmaKg} kg` },
        { label: "Wind sigma", value: `${draft.windSigmaMps} m/s` }
      ]
    };
  }
  if (draft.kind === "sweep") {
    const values = parseSweepValues(draft.sweepValues);
    return {
      title: `${scenario} parameter sweep`,
      description: `Runs ${estimatedRuns} case${estimatedRuns === 1 ? "" : "s"} across ${draft.sweepParameter.trim() || "an unset parameter"}.`,
      rows: [
        { label: "Action", value: "sweep" },
        { label: "Scenario", value: scenario },
        { label: "Parameter", value: draft.sweepParameter.trim() || "-" },
        { label: "Values", value: values.map(String).join(", ") || "-" },
        { label: "Max runs", value: String(draft.sweepMaxRuns) }
      ]
    };
  }
  const faults = parseCsvList(draft.faultText);
  return {
    title: `${scenario} fault campaign`,
    description: `Runs ${estimatedRuns} fault case${estimatedRuns === 1 ? "" : "s"} through the existing fault campaign action.`,
    rows: [
      { label: "Action", value: "fault_campaign" },
      { label: "Scenario", value: scenario },
      { label: "Faults", value: faults.length ? faults.join(", ") : "All built-in faults" },
      { label: "Max runs", value: String(draft.faultMaxRuns) }
    ]
  };
}

export function buildCampaignPlanModel(
  draft: CampaignDesignerDraft,
  options: { scenarios?: ScenarioSummary[]; faultOptions?: string[] } = {}
): CampaignPlanModel {
  const scenarios = options.scenarios ?? [];
  const faultOptions = options.faultOptions?.length ? options.faultOptions : DEFAULT_FAULT_OPTIONS;
  const validation = validateCampaignDraft(draft, { scenarios, faultOptions });
  const payload = buildCampaignActionPayload(draft);
  const summary = summarizeCampaignPlan(draft, scenarios, faultOptions);
  return {
    kind: draft.kind,
    label: CAMPAIGN_KIND_LABELS[draft.kind],
    payload,
    validation,
    summary,
    issueMap: issueMapFromValidation(validation),
    canLaunch: validation.valid,
    runCountLabel: runCountLabel(validation.estimatedRuns),
    launchRouteHint: `/api/jobs/${payload.action} or /api/actions/${payload.action}`
  };
}

export function buildBatchCampaignModel(draft: CampaignDesignerDraft, options: { scenarios?: ScenarioSummary[]; faultOptions?: string[] } = {}): CampaignPlanModel {
  return buildCampaignPlanModel({ ...draft, kind: "batch" }, options);
}

export function buildMonteCarloCampaignModel(draft: CampaignDesignerDraft, options: { scenarios?: ScenarioSummary[]; faultOptions?: string[] } = {}): CampaignPlanModel {
  return buildCampaignPlanModel({ ...draft, kind: "monte_carlo" }, options);
}

export function buildSweepCampaignModel(draft: CampaignDesignerDraft, options: { scenarios?: ScenarioSummary[]; faultOptions?: string[] } = {}): CampaignPlanModel {
  return buildCampaignPlanModel({ ...draft, kind: "sweep" }, options);
}

export function buildFaultCampaignModel(draft: CampaignDesignerDraft, options: { scenarios?: ScenarioSummary[]; faultOptions?: string[] } = {}): CampaignPlanModel {
  return buildCampaignPlanModel({ ...draft, kind: "fault_campaign" }, options);
}
