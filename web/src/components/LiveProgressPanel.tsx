import { Activity, RefreshCw, XCircle } from "lucide-react";
import type { CSSProperties } from "react";
import type { JobSummary } from "../types";
import {
  buildCancelRequest,
  buildRetryRequest,
  canCancel as canCancelProgress,
  canRetry as canRetryProgress,
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

const controlRowStyle = {
  alignItems: "center",
  display: "flex",
  gap: "12px",
  justifyContent: "flex-end",
  marginTop: "2px"
} satisfies CSSProperties;

const controlButtonStyle = {
  alignItems: "center",
  display: "inline-flex",
  gap: "8px",
  minHeight: "36px",
  padding: "0 14px"
} satisfies CSSProperties;

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
          const cancelRequest = buildCancelRequest(state);
          const retryRequest = buildRetryRequest(state);
          const cancelEnabled = Boolean(onCancel && canCancelProgress(state) && cancelRequest.enabled);
          const retryEnabled = Boolean(onRetry && canRetryProgress(state) && retryRequest.enabled);
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
              {(cancelEnabled || retryEnabled) && (
                <div className="artifact-links" style={controlRowStyle}>
                  {cancelEnabled && (
                    <button
                      type="button"
                      className="secondary-action"
                      style={controlButtonStyle}
                      title={cancelRequest.path}
                      aria-label={`Cancel ${actionLabel(state.action)}`}
                      onClick={() => onCancel?.(state.job_id, state)}
                    >
                      <XCircle size={15} />
                      Cancel
                    </button>
                  )}
                  {retryEnabled && (
                    <button
                      type="button"
                      className="secondary-action"
                      style={controlButtonStyle}
                      title={retryRequest.path}
                      aria-label={`Retry ${actionLabel(state.action)}`}
                      onClick={() => onRetry?.(state.action, state.job_id, state)}
                    >
                      <RefreshCw size={15} />
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
