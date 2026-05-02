import { Bell, Check, Crosshair, History } from "lucide-react";
import type { AlarmSeverity, AlarmSummary } from "../types";
import { alarmStatus, alarmTime, groupedAlarms, SEVERITY_ORDER } from "../alarms";

type AlarmPanelsProps = {
  alarms: AlarmSummary[];
  acknowledged: Record<string, boolean>;
  onAcknowledge: (id: string) => void;
  onJump: (timeS: number) => void;
};

const SEVERITY_LABELS: Record<AlarmSeverity, string> = {
  critical: "Critical",
  warning: "Warning",
  caution: "Caution",
  info: "Info"
};

export function ActiveAlarmsPanel({ alarms, acknowledged, onAcknowledge, onJump }: AlarmPanelsProps) {
  const groups = groupedAlarms(alarms);
  const visibleGroups = SEVERITY_ORDER.filter((severity) => groups[severity].length > 0);

  return (
    <section className="side-section alarm-panel">
      <div className="section-title">
        <Bell size={16} />
        <h3>Active Alarms</h3>
      </div>
      {visibleGroups.length === 0 && <div className="empty-state">No alarms</div>}
      {visibleGroups.map((severity) => (
        <div className="alarm-group" key={severity}>
          <div className={`alarm-group-title severity-${severity}`}>
            <span>{SEVERITY_LABELS[severity]}</span>
            <strong>{groups[severity].length}</strong>
          </div>
          <div className="alarm-stack">
            {groups[severity].map((alarm) => (
              <article className={`alarm-item severity-${alarm.severity}`} key={alarm.id}>
                <div className="alarm-item-head">
                  <strong>{alarm.name}</strong>
                  <span className={`alarm-status ${alarmStatus(alarm, acknowledged[alarm.id])}`}>{alarmStatus(alarm, acknowledged[alarm.id])}</span>
                </div>
                <p>{alarm.message}</p>
                <div className="alarm-meta">
                  <span>{alarm.subsystem || alarm.source}</span>
                  <span>{alarmTime(alarm.first_triggered_time_s)}</span>
                  <span>{alarm.threshold}</span>
                </div>
                <div className="alarm-actions">
                  <button type="button" onClick={() => onJump(alarm.first_triggered_time_s)}>
                    <Crosshair size={14} />
                    Jump
                  </button>
                  <button type="button" onClick={() => onAcknowledge(alarm.id)} disabled={acknowledged[alarm.id]}>
                    <Check size={14} />
                    {acknowledged[alarm.id] ? "Ack" : "Acknowledge"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

export function AlarmHistoryPanel({ alarms, acknowledged, onAcknowledge, onJump }: AlarmPanelsProps) {
  return (
    <section className="side-section alarm-history-panel">
      <div className="section-title">
        <History size={16} />
        <h3>Alarm History</h3>
      </div>
      <div className="alarm-history-list">
        {alarms.map((alarm) => (
          <article className={`alarm-history-item severity-${alarm.severity}`} key={alarm.id}>
            <div>
              <span>{alarm.severity}</span>
              <strong>{alarm.name}</strong>
              <p>{alarm.source} / {alarm.subsystem}</p>
            </div>
            <dl>
              <div>
                <dt>first</dt>
                <dd>{alarmTime(alarm.first_triggered_time_s)}</dd>
              </div>
              <div>
                <dt>last</dt>
                <dd>{alarmTime(alarm.last_triggered_time_s)}</dd>
              </div>
              <div>
                <dt>clear</dt>
                <dd>{alarmTime(alarm.cleared_time_s)}</dd>
              </div>
            </dl>
            <div className="alarm-actions compact">
              <button type="button" onClick={() => onJump(alarm.first_triggered_time_s)}>
                Jump
              </button>
              <button type="button" onClick={() => onAcknowledge(alarm.id)} disabled={acknowledged[alarm.id]}>
                {acknowledged[alarm.id] ? "Ack" : "Ack"}
              </button>
            </div>
          </article>
        ))}
        {alarms.length === 0 && <div className="empty-state">No alarm history</div>}
      </div>
    </section>
  );
}
