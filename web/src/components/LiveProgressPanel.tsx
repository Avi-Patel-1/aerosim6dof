import { Activity, RefreshCw, XCircle } from "lucide-react";
import type { JobSummary } from "../types";
import {
  collectLiveProgressStates,
  formatElapsedLabel,
  formatLiveProgressLabel,
  isTerminalProgressPhase,
  sortLiveProgressJobs,
  type LiveProgressMap,
  type LiveProgressState
} from "../liveProgress";

type LiveProgressPanelProps = {
  jobs?: JobSummary[] | Record<string, JobSummary>;
  progress?: LiveProgressMap | Map<string, LiveProgressState>;
  limit?: number;
  showCompleted?: boolean;
  now?: Date;
  onCancel?: (jobId: string, progress: LiveProgressState) => void;
  onRetry?: (action: string, jobId: string, progress: LiveProgressState) => void;
};

function actionLabel(action: string): string {
  return (action || "job").replaceAll("_", " ");
}

export function LiveProgressPanel({
  jobs,
  progress,
  limit = 8,
  showCompleted = true,
  now = new Date(),
  onCancel,
  onRetry
}: LiveProgressPanelProps) {
  const allStates = sortLiveProgressJobs(collectLiveProgressStates(jobs, progress));
  const visibleStates = allStates.filter((state) => showCompleted || !isTerminalProgressPhase(state.phase)).slice(0, limit);

  return (
    <section className="report-panel live-progress-panel">
      <div className="section-title">
        <Activity size={16} />
        <h3>Live Progress</h3>
      </div>
      <div className="job-list">
        {visibleStates.map((state) => {
          const terminal = isTerminalProgressPhase(state.phase);
          const canCancel = Boolean(onCancel && state.cancellable && !terminal);
          const canRetry = Boolean(onRetry && (state.phase === "failed" || state.phase === "cancelled"));
          return (
            <article className="job-item" key={state.job_id}>
              <div>
                <strong>{actionLabel(state.action)}</strong>
                <span>{formatLiveProgressLabel(state)}</span>
              </div>
              <div className="job-progress dark" aria-label={`${actionLabel(state.action)} progress`}>
                <i style={{ width: `${Math.max(3, Math.round(state.percent))}%` }} />
              </div>
              <p>{state.message || state.phase}</p>
              <div className="artifact-links">
                <span>{formatElapsedLabel(state.created_at || state.updated_at, now)}</span>
                {state.run_id && <span>{state.run_id}</span>}
                {state.artifact?.url && (
                  <a href={String(state.artifact.url)} target="_blank" rel="noreferrer">
                    {String(state.artifact.name ?? "artifact")}
                  </a>
                )}
              </div>
              {(canCancel || canRetry) && (
                <div className="artifact-links">
                  {canCancel && (
                    <button type="button" className="secondary-action" onClick={() => onCancel?.(state.job_id, state)}>
                      <XCircle size={14} />
                      Cancel
                    </button>
                  )}
                  {canRetry && (
                    <button type="button" className="secondary-action" onClick={() => onRetry?.(state.action, state.job_id, state)}>
                      <RefreshCw size={14} />
                      Retry
                    </button>
                  )}
                </div>
              )}
            </article>
          );
        })}
        {visibleStates.length === 0 && <div className="empty-state">No active jobs</div>}
      </div>
    </section>
  );
}
