import type { AlarmSeverity, AlarmSummary } from "./types";

export const SEVERITY_ORDER: AlarmSeverity[] = ["critical", "warning", "caution", "info"];

export function groupedAlarms(alarms: AlarmSummary[]): Record<AlarmSeverity, AlarmSummary[]> {
  return SEVERITY_ORDER.reduce(
    (groups, severity) => {
      groups[severity] = alarms.filter((alarm) => alarm.severity === severity);
      return groups;
    },
    {} as Record<AlarmSeverity, AlarmSummary[]>
  );
}

export function activeAlarmCount(alarms: AlarmSummary[]): number {
  return alarms.filter((alarm) => alarm.active).length;
}

export function alarmTime(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)}s` : "-";
}

export function alarmStatus(alarm: AlarmSummary, acknowledged: boolean): string {
  if (alarm.active && acknowledged) {
    return "acknowledged";
  }
  return alarm.active ? "active" : "cleared";
}
