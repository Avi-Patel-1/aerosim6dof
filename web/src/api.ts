import type { ExamplesGalleryCard } from "./examplesGallery";
import type { LiveProgressState } from "./liveProgress";
import type { ReportStudioPacket, ReportStudioSectionId } from "./reportStudio";
import type {
  ActionResult,
  AlarmSummary,
  Capability,
  ConfigSummary,
  JobSummary,
  MissileEngagementComparisonPacket,
  NavigationTelemetry,
  RunSummary,
  ScenarioDetail,
  ScenarioDraft,
  ScenarioSummary,
  ScenarioValidation,
  StorageStatus,
  TelemetrySeries
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function getScenarios(): Promise<ScenarioSummary[]> {
  return request<ScenarioSummary[]>("/api/scenarios");
}

export function getScenario(id: string): Promise<ScenarioDetail> {
  return request<ScenarioDetail>(`/api/scenarios/${encodeURIComponent(id)}`);
}

export function createScenarioDraft(scenario: Record<string, unknown>, name?: string): Promise<ScenarioDraft> {
  return request<ScenarioDraft>("/api/scenario-drafts", {
    method: "POST",
    body: JSON.stringify({ scenario, name })
  });
}

export function getVehicles(): Promise<ConfigSummary[]> {
  return request<ConfigSummary[]>("/api/vehicles");
}

export function getEnvironments(): Promise<ConfigSummary[]> {
  return request<ConfigSummary[]>("/api/environments");
}

export function getCapabilities(): Promise<Capability[]> {
  return request<Capability[]>("/api/capabilities");
}

export function getStorageStatus(): Promise<StorageStatus> {
  return request<StorageStatus>("/api/storage/status");
}

export function getStorageLayouts(): Promise<Record<string, unknown>[]> {
  return request<Record<string, unknown>[]>("/api/storage/layouts");
}

export function saveStorageLayout(id: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/storage/layouts/${encodeURIComponent(id)}`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function deleteStorageLayout(id: string): Promise<{ id: string; deleted: boolean }> {
  return request<{ id: string; deleted: boolean }>(`/api/storage/layouts/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export function getExamplesGallery(): Promise<ExamplesGalleryCard[]> {
  return request<ExamplesGalleryCard[]>("/api/examples-gallery");
}

export function getRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/api/runs");
}

export function getRun(id: string): Promise<RunSummary> {
  return request<RunSummary>(`/api/runs/${encodeURIComponent(id)}`);
}

export function getTelemetry(id: string, stride = 3): Promise<TelemetrySeries> {
  return request<TelemetrySeries>(`/api/runs/${encodeURIComponent(id)}/telemetry?stride=${stride}`);
}

export function getRunAlarms(id: string): Promise<AlarmSummary[]> {
  return request<AlarmSummary[]>(`/api/runs/${encodeURIComponent(id)}/alarms`);
}

export function getRunNavigation(id: string, stride = 3): Promise<NavigationTelemetry> {
  return request<NavigationTelemetry>(`/api/runs/${encodeURIComponent(id)}/navigation?stride=${stride}`);
}

export function getReportStudioPacket(id: string, sections?: ReportStudioSectionId[]): Promise<ReportStudioPacket> {
  const query = sections?.length ? `?sections=${encodeURIComponent(sections.join(","))}` : "";
  return request<ReportStudioPacket>(`/api/runs/${encodeURIComponent(id)}/report-studio${query}`);
}

export function getMissileEngagementComparison(maxRuns = 4, maxSamples = 260, runIds?: string[]): Promise<MissileEngagementComparisonPacket> {
  const params = new URLSearchParams();
  params.set("max_runs", String(maxRuns));
  params.set("max_samples", String(maxSamples));
  if (runIds?.length) {
    params.set("run_ids", runIds.join(","));
  }
  return request<MissileEngagementComparisonPacket>(`/api/missile-engagement-comparison?${params.toString()}`);
}

export function validateScenario(scenarioId: string): Promise<ScenarioValidation> {
  return request("/api/validate", {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId })
  });
}

export function validateScenarioJson(scenario: Record<string, unknown>): Promise<ScenarioValidation> {
  return request("/api/validate", {
    method: "POST",
    body: JSON.stringify({ scenario })
  });
}

export function createRun(scenarioId: string): Promise<RunSummary> {
  return request<RunSummary>("/api/runs", {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId })
  });
}

export function runAction(action: string, params: Record<string, unknown>): Promise<ActionResult> {
  return request<ActionResult>(`/api/actions/${encodeURIComponent(action)}`, {
    method: "POST",
    body: JSON.stringify({ params })
  });
}

export function startJob(action: string, params: Record<string, unknown>): Promise<JobSummary> {
  return request<JobSummary>(`/api/jobs/${encodeURIComponent(action)}`, {
    method: "POST",
    body: JSON.stringify({ params })
  });
}

export function getJobs(): Promise<JobSummary[]> {
  return request<JobSummary[]>("/api/jobs");
}

export function getJob(id: string): Promise<JobSummary> {
  return request<JobSummary>(`/api/jobs/${encodeURIComponent(id)}`);
}

export function cancelJob(id: string, reason = "cancelled from browser"): Promise<{ cancel: Record<string, unknown>; job: JobSummary }> {
  return request<{ cancel: Record<string, unknown>; job: JobSummary }>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export function retryJob(id: string): Promise<JobSummary> {
  return request<JobSummary>(`/api/jobs/${encodeURIComponent(id)}/retry`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function getJobProgress(id: string): Promise<LiveProgressState> {
  return request<LiveProgressState>(`/api/jobs/${encodeURIComponent(id)}/progress`);
}

export function jobEventsUrl(id: string): string {
  return `${API_BASE}/api/jobs/${encodeURIComponent(id)}/events`;
}
