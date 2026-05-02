import type { ArtifactRef, JobSummary } from "./types";

export type LiveProgressPhase = "queued" | "running" | "completed" | "failed" | "cancelled" | "unknown";

export type LiveProgressArtifact = Partial<ArtifactRef> & Record<string, unknown>;

export type LiveProgressState = {
  job_id: string;
  action: string;
  phase: LiveProgressPhase;
  percent: number;
  message: string;
  run_id: string | null;
  artifact: LiveProgressArtifact | null;
  cancellable: boolean;
  created_at: string;
  updated_at: string;
};

export type LiveProgressMap = Record<string, LiveProgressState>;

const TERMINAL_PHASES = new Set<LiveProgressPhase>(["completed", "failed", "cancelled"]);

const PHASE_ALIASES: Record<string, LiveProgressPhase> = {
  active: "running",
  canceled: "cancelled",
  done: "completed",
  error: "failed",
  errored: "failed",
  executing: "running",
  finished: "completed",
  in_progress: "running",
  pending: "queued",
  started: "running",
  success: "completed",
  succeeded: "completed"
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : value == null ? fallback : String(value);
}

function asNumber(value: unknown, fallback = 0): number {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return "";
}

export function normalizeLivePhase(value: unknown): LiveProgressPhase {
  const text = asString(value, "unknown").trim().toLowerCase().replace(/[\s-]+/g, "_").replace(/[^a-z0-9_]/g, "");
  const phase = PHASE_ALIASES[text] ?? text;
  if (phase === "queued" || phase === "running" || phase === "completed" || phase === "failed" || phase === "cancelled") {
    return phase;
  }
  return "unknown";
}

export function normalizeLivePercent(value: unknown, phase?: unknown): number {
  const normalizedPhase = normalizeLivePhase(phase);
  if (normalizedPhase === "completed") {
    return 100;
  }
  let number = asNumber(value, 0);
  if (number >= 0 && number <= 1) {
    number *= 100;
  }
  return Math.max(0, Math.min(100, Math.round(number * 10) / 10));
}

export function isTerminalProgressPhase(value: unknown): boolean {
  return TERMINAL_PHASES.has(normalizeLivePhase(value));
}

export function parseLiveProgressPayload(data: string | unknown): LiveProgressState | null {
  let payload: unknown = data;
  if (typeof data === "string") {
    try {
      payload = JSON.parse(data);
    } catch {
      return null;
    }
  }
  if (!isRecord(payload)) {
    return null;
  }
  return "job_id" in payload ? progressEventToState(payload) : jobSummaryToProgressState(payload);
}

export function jobSummaryToProgressState(job: JobSummary | Record<string, unknown>): LiveProgressState | null {
  if (!isRecord(job)) {
    return null;
  }
  const record = job as Record<string, unknown>;
  const jobId = firstString(record.id, record.job_id);
  if (!jobId) {
    return null;
  }
  const events = Array.isArray(record.events) ? record.events.filter(isRecord) : [];
  const lastEvent = events.length > 0 ? events[events.length - 1] : undefined;
  const result = isRecord(record.result) ? record.result : null;
  const artifacts = result && Array.isArray(result.artifacts) ? result.artifacts.filter(isRecord) : [];
  const phase = normalizeLivePhase(record.status ?? record.phase);
  const updatedAt = firstString(record.finished_at_utc, lastEvent?.time_utc, record.started_at_utc, record.updated_at, record.created_at_utc, record.created_at);

  return {
    job_id: jobId,
    action: firstString(record.action),
    phase,
    percent: normalizeLivePercent(record.progress ?? record.percent, phase),
    message: firstString(record.message, lastEvent?.message),
    run_id: firstString(result?.output_id, record.run_id) || null,
    artifact: artifacts.length > 0 ? (artifacts[0] as LiveProgressArtifact) : null,
    cancellable: !isTerminalProgressPhase(phase),
    created_at: firstString(record.created_at_utc, record.created_at, updatedAt),
    updated_at: updatedAt
  };
}

export function progressEventToState(event: Record<string, unknown>): LiveProgressState | null {
  const jobId = firstString(event.job_id, event.id);
  if (!jobId) {
    return null;
  }
  const phase = normalizeLivePhase(event.phase ?? event.status);
  const artifact = isRecord(event.artifact) ? (event.artifact as LiveProgressArtifact) : null;
  const createdAt = firstString(event.created_at, event.created_at_utc, event.updated_at, event.updated_at_utc);
  const updatedAt = firstString(event.updated_at, event.updated_at_utc, createdAt);
  return {
    job_id: jobId,
    action: firstString(event.action),
    phase,
    percent: normalizeLivePercent(event.percent ?? event.progress, phase),
    message: firstString(event.message),
    run_id: firstString(event.run_id) || null,
    artifact,
    cancellable: Boolean(event.cancellable) && !isTerminalProgressPhase(phase),
    created_at: createdAt,
    updated_at: updatedAt
  };
}

export function mergeLiveProgress(previous: LiveProgressState | null | undefined, next: LiveProgressState): LiveProgressState {
  return {
    ...previous,
    ...next,
    created_at: previous?.created_at || next.created_at,
    updated_at: next.updated_at || previous?.updated_at || next.created_at,
    artifact: next.artifact ?? previous?.artifact ?? null,
    run_id: next.run_id ?? previous?.run_id ?? null,
    cancellable: next.cancellable && !isTerminalProgressPhase(next.phase)
  };
}

export function updateLiveProgressMap(map: LiveProgressMap, data: string | unknown): LiveProgressMap {
  const state = parseLiveProgressPayload(data);
  if (!state) {
    return map;
  }
  return {
    ...map,
    [state.job_id]: mergeLiveProgress(map[state.job_id], state)
  };
}

export function collectLiveProgressStates(jobs: JobSummary[] | Record<string, JobSummary> | null | undefined, progress: LiveProgressMap | Map<string, LiveProgressState> | null | undefined): LiveProgressState[] {
  const states = new Map<string, LiveProgressState>();
  const jobItems = Array.isArray(jobs) ? jobs : jobs ? Object.values(jobs) : [];
  for (const job of jobItems) {
    const state = jobSummaryToProgressState(job);
    if (state) {
      states.set(state.job_id, state);
    }
  }
  const progressItems = progress instanceof Map ? Array.from(progress.values()) : progress ? Object.values(progress) : [];
  for (const state of progressItems) {
    states.set(state.job_id, mergeLiveProgress(states.get(state.job_id), state));
  }
  return Array.from(states.values());
}

export function activeLiveProgressJobs(states: Iterable<LiveProgressState>): LiveProgressState[] {
  return Array.from(states)
    .filter((state) => !isTerminalProgressPhase(state.phase))
    .sort((a, b) => timestampMs(b.updated_at || b.created_at) - timestampMs(a.updated_at || a.created_at));
}

export function sortLiveProgressJobs(states: Iterable<LiveProgressState>): LiveProgressState[] {
  return Array.from(states).sort((a, b) => {
    const terminalDelta = Number(isTerminalProgressPhase(a.phase)) - Number(isTerminalProgressPhase(b.phase));
    if (terminalDelta !== 0) return terminalDelta;
    return timestampMs(b.updated_at || b.created_at) - timestampMs(a.updated_at || a.created_at);
  });
}

export function formatLiveProgressLabel(state: Pick<LiveProgressState, "phase" | "percent">): string {
  return `${state.phase} / ${Math.round(state.percent)}%`;
}

export function formatElapsedLabel(startedAt: string, now: Date = new Date()): string {
  const started = timestampMs(startedAt);
  if (!started) {
    return "elapsed --";
  }
  const seconds = Math.max(0, Math.floor((now.getTime() - started) / 1000));
  if (seconds < 60) {
    return `elapsed ${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) {
    return `elapsed ${minutes}m ${remainingSeconds.toString().padStart(2, "0")}s`;
  }
  const hours = Math.floor(minutes / 60);
  return `elapsed ${hours}h ${(minutes % 60).toString().padStart(2, "0")}m`;
}

export function timestampMs(value: string): number {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : 0;
}
