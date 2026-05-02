import { AlertTriangle, Boxes, CheckCircle2, Clipboard, FileJson, Play, RotateCcw, Settings2, ShieldAlert, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  CAMPAIGN_KIND_LABELS,
  buildCampaignPlanModel,
  createDefaultCampaignDraft,
  faultsFromCapabilities,
  parseCsvList,
  type CampaignActionPayload,
  type CampaignDesignerDraft,
  type CampaignPlanKind,
  type CampaignValidation,
  type CampaignValidationIssue
} from "../campaignDesigner";
import type { Capability, ScenarioSummary } from "../types";

export type CampaignDesignerProps = {
  scenarios: ScenarioSummary[];
  capabilities?: Capability[];
  initialDraft?: Partial<CampaignDesignerDraft>;
  busyAction?: string | null;
  onDraftChange?: (draft: CampaignDesignerDraft, payload: CampaignActionPayload, validation: CampaignValidation) => void;
  onRunPlan?: (payload: CampaignActionPayload, draft: CampaignDesignerDraft, validation: CampaignValidation) => void | Promise<void>;
};

type FieldProps = {
  label: string;
  children: ReactNode;
};

const KIND_ICONS: Record<CampaignPlanKind, ReactNode> = {
  batch: <Boxes size={16} />,
  monte_carlo: <Sparkles size={16} />,
  sweep: <Settings2 size={16} />,
  fault_campaign: <ShieldAlert size={16} />
};

const KIND_ORDER: CampaignPlanKind[] = ["batch", "monte_carlo", "sweep", "fault_campaign"];

function Field({ label, children }: FieldProps) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function numberInputValue(value: number): string {
  return Number.isFinite(value) ? String(value) : "";
}

function readNumber(value: string): number {
  return value.trim() === "" ? Number.NaN : Number(value);
}

function firstScenarioId(scenarios: ScenarioSummary[]): string {
  return scenarios.find((scenario) => scenario.id === "nominal_ascent")?.id ?? scenarios[0]?.id ?? "nominal_ascent";
}

function scenarioOptionLabel(scenario: ScenarioSummary): string {
  return `${scenario.name} (${scenario.id})`;
}

function FieldIssues({ issues }: { issues?: CampaignValidationIssue[] }) {
  if (!issues?.length) {
    return null;
  }
  return (
    <span className="scenario-builder-v2-hint">
      {issues.map((issue) => issue.message).join(" ")}
    </span>
  );
}

export function CampaignDesigner({
  scenarios,
  capabilities = [],
  initialDraft,
  busyAction,
  onDraftChange,
  onRunPlan
}: CampaignDesignerProps) {
  const faultOptions = useMemo(() => faultsFromCapabilities(capabilities), [capabilities]);
  const [draft, setDraft] = useState<CampaignDesignerDraft>(() => ({
    ...createDefaultCampaignDraft(initialDraft?.scenarioId ?? firstScenarioId(scenarios), faultOptions),
    ...initialDraft
  }));
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    setDraft((current) => {
      if (!scenarios.length) {
        return current;
      }
      const scenarioIds = new Set(scenarios.map((scenario) => scenario.id));
      if (current.scenarioId && scenarioIds.has(current.scenarioId)) {
        return current;
      }
      return { ...current, scenarioId: firstScenarioId(scenarios) };
    });
  }, [scenarios]);

  useEffect(() => {
    if (!initialDraft?.scenarioId) {
      return;
    }
    setDraft((current) => (current.scenarioId === initialDraft.scenarioId ? current : { ...current, scenarioId: initialDraft.scenarioId ?? current.scenarioId }));
  }, [initialDraft?.scenarioId]);

  const plan = useMemo(() => buildCampaignPlanModel(draft, { scenarios, faultOptions }), [draft, faultOptions, scenarios]);
  const { payload, summary, validation } = plan;
  const payloadJson = useMemo(() => JSON.stringify(payload, null, 2), [payload]);
  const selectedFaults = useMemo(() => new Set(parseCsvList(draft.faultText)), [draft.faultText]);
  const allFaultsSelected = draft.kind === "fault_campaign" && !draft.faultText.trim();
  const isBusy = Boolean(busyAction && busyAction === payload.action);
  const issues = [...validation.errors, ...validation.warnings];

  useEffect(() => {
    setCopyState("idle");
  }, [payloadJson]);

  useEffect(() => {
    onDraftChange?.(draft, payload, validation);
  }, [draft, onDraftChange, payload, validation]);

  const updateDraft = <Key extends keyof CampaignDesignerDraft>(key: Key, value: CampaignDesignerDraft[Key]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const toggleFault = (fault: string, checked: boolean) => {
    const next = new Set(allFaultsSelected ? faultOptions : Array.from(selectedFaults));
    if (checked) {
      next.add(fault);
    } else {
      next.delete(fault);
    }
    updateDraft("faultText", Array.from(next).sort().join(","));
  };

  const resetDraft = () => {
    setDraft(createDefaultCampaignDraft(draft.scenarioId || firstScenarioId(scenarios), faultOptions));
  };

  const copyPayload = async () => {
    try {
      await navigator.clipboard.writeText(payloadJson);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  const runPlan = async () => {
    if (!validation.valid || !onRunPlan) {
      return;
    }
    await onRunPlan(payload, draft, validation);
  };

  return (
    <section className="scenario-builder-v2" aria-label="Mission campaign designer">
      <div className="scenario-builder-v2-preset-bar" role="tablist" aria-label="Campaign type">
        {KIND_ORDER.map((kind) => (
          <button
            key={kind}
            className={`${draft.kind === kind ? "primary-action" : "secondary-action"} scenario-builder-v2-preset`}
            type="button"
            aria-pressed={draft.kind === kind}
            onClick={() => updateDraft("kind", kind)}
          >
            {KIND_ICONS[kind]}
            {CAMPAIGN_KIND_LABELS[kind]}
          </button>
        ))}
      </div>

      <div className="scenario-builder-v2-layout editor-layout">
        <section className="scenario-builder-v2-main builder-section">
          <div className="section-row">
            <div>
              <p className="eyebrow">Campaign Plan</p>
              <h3>{summary.title}</h3>
            </div>
            <span className={`validation-state ${validation.valid ? "ok" : "bad"}`}>
              {validation.valid ? "Ready" : "Needs edits"}
            </span>
          </div>

          {draft.kind !== "batch" && (
            <div className="guided-grid scenario-builder-v2-grid">
              <Field label="Scenario">
                <select value={draft.scenarioId} onChange={(event) => updateDraft("scenarioId", event.target.value)}>
                  {!scenarios.length && <option value={draft.scenarioId}>{draft.scenarioId}</option>}
                  {scenarios.map((scenario) => (
                    <option key={scenario.id} value={scenario.id}>
                      {scenarioOptionLabel(scenario)}
                    </option>
                  ))}
                </select>
                <FieldIssues issues={plan.issueMap.scenarioId} />
              </Field>
            </div>
          )}

          {draft.kind === "monte_carlo" && (
            <div className="guided-grid scenario-builder-v2-grid">
              <Field label="Samples">
                <input type="number" min={1} max={50} step={1} value={numberInputValue(draft.samples)} onChange={(event) => updateDraft("samples", readNumber(event.target.value))} />
                <FieldIssues issues={plan.issueMap.samples} />
              </Field>
              <Field label="Seed">
                <input type="number" step={1} value={numberInputValue(draft.seed)} onChange={(event) => updateDraft("seed", readNumber(event.target.value))} />
                <FieldIssues issues={plan.issueMap.seed} />
              </Field>
              <Field label="Mass sigma kg">
                <input
                  type="number"
                  min={0}
                  step={0.05}
                  value={numberInputValue(draft.massSigmaKg)}
                  onChange={(event) => updateDraft("massSigmaKg", readNumber(event.target.value))}
                />
                <FieldIssues issues={plan.issueMap.massSigmaKg} />
              </Field>
              <Field label="Wind sigma m/s">
                <input
                  type="number"
                  min={0}
                  step={0.05}
                  value={numberInputValue(draft.windSigmaMps)}
                  onChange={(event) => updateDraft("windSigmaMps", readNumber(event.target.value))}
                />
                <FieldIssues issues={plan.issueMap.windSigmaMps ?? plan.issueMap.dispersions} />
              </Field>
            </div>
          )}

          {draft.kind === "sweep" && (
            <div className="guided-grid scenario-builder-v2-grid">
              <Field label="Parameter path">
                <input value={draft.sweepParameter} onChange={(event) => updateDraft("sweepParameter", event.target.value)} />
                <FieldIssues issues={plan.issueMap.sweepParameter} />
              </Field>
              <Field label="Values">
                <input value={draft.sweepValues} onChange={(event) => updateDraft("sweepValues", event.target.value)} />
                <FieldIssues issues={plan.issueMap.sweepValues} />
              </Field>
              <Field label="Max runs">
                <input
                  type="number"
                  min={1}
                  max={100}
                  step={1}
                  value={numberInputValue(draft.sweepMaxRuns)}
                  onChange={(event) => updateDraft("sweepMaxRuns", readNumber(event.target.value))}
                />
                <FieldIssues issues={plan.issueMap.sweepMaxRuns} />
              </Field>
            </div>
          )}

          {draft.kind === "fault_campaign" && (
            <div className="builder-card-grid scenario-builder-v2-card-grid">
              <section className="builder-card scenario-builder-v2-card">
                <div className="section-row">
                  <strong>Fault Library</strong>
                  <button className="secondary-action" type="button" onClick={() => updateDraft("faultText", "")}>
                    All faults
                  </button>
                </div>
                <div className="guided-grid scenario-builder-v2-grid">
                  {faultOptions.map((fault) => (
                    <label className="field scenario-builder-v2-check" key={fault}>
                      <span>{fault}</span>
                      <input type="checkbox" checked={allFaultsSelected || selectedFaults.has(fault)} onChange={(event) => toggleFault(fault, event.target.checked)} />
                    </label>
                  ))}
                </div>
              </section>
              <section className="builder-card scenario-builder-v2-card">
                <Field label="Faults">
                  <input value={draft.faultText} onChange={(event) => updateDraft("faultText", event.target.value)} />
                  <FieldIssues issues={plan.issueMap.faultText} />
                </Field>
                <Field label="Max runs">
                  <input
                    type="number"
                    min={1}
                    max={50}
                    step={1}
                    value={numberInputValue(draft.faultMaxRuns)}
                    onChange={(event) => updateDraft("faultMaxRuns", readNumber(event.target.value))}
                  />
                  <FieldIssues issues={plan.issueMap.faultMaxRuns} />
                </Field>
              </section>
            </div>
          )}

          {draft.kind === "batch" && (
            <div className="builder-card scenario-builder-v2-card">
              <div className="section-row">
                <strong>Scenario Batch</strong>
                <span>{scenarios.length ? `${scenarios.length} loaded scenarios` : "scenario index pending"}</span>
              </div>
              <FieldIssues issues={plan.issueMap.batch} />
            </div>
          )}

          <div className="scenario-builder-v2-runbar editor-actions section-row">
            <button className="primary-action" type="button" onClick={runPlan} disabled={!validation.valid || isBusy || !onRunPlan}>
              <Play size={17} />
              {isBusy ? "Running" : "Run"}
            </button>
            <button className="secondary-action" type="button" onClick={resetDraft}>
              <RotateCcw size={16} />
              Reset
            </button>
            <span>{plan.runCountLabel}</span>
          </div>
        </section>

        <aside className="scenario-builder-v2-aside report-panel">
          <div className="action-card-title">
            <span>
              <FileJson size={18} />
            </span>
            <h3>Plan Summary</h3>
          </div>
          <p>{summary.description}</p>
          <p className="scenario-builder-v2-hint">Launch target: {plan.launchRouteHint}</p>
          <div className="metric-grid">
            {summary.rows.map((row) => (
              <div key={row.label}>
                <span>{row.label}</span>
                <strong>{row.value}</strong>
              </div>
            ))}
          </div>
          <div className="scenario-builder-v2-warning-panel">
            {issues.length ? (
              issues.map((issue) => (
                <p key={`${issue.field}-${issue.message}`}>
                  <AlertTriangle size={15} />
                  <span>{issue.message}</span>
                </p>
              ))
            ) : (
              <p>
                <CheckCircle2 size={15} />
                <span>UI validation passed.</span>
              </p>
            )}
          </div>
          <div className="scenario-builder-v2-json">
            <Field label="API payload">
              <textarea readOnly value={payloadJson} />
            </Field>
            <div className="editor-actions">
              <button className="secondary-action" type="button" onClick={copyPayload}>
                <Clipboard size={16} />
                Copy payload
              </button>
              {copyState !== "idle" && <span className="scenario-builder-v2-hint">{copyState === "copied" ? "Payload copied." : "Clipboard unavailable."}</span>}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
