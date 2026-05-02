import {
  Bell,
  Download,
  Eye,
  Gauge,
  Layers3,
  Pin,
  PinOff,
  Save,
  Search,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { channelLabel, channelLabelWithUnit, formatTelemetryValue } from "../telemetry";
import type { AlarmSummary, TelemetryChannelMetadata, TelemetryRow, TelemetrySeries } from "../types";
import {
  deleteTelemetryChartLayout,
  downloadTelemetryCsv,
  listPinnedTelemetryChannels,
  listTelemetryChartLayouts,
  saveTelemetryChartLayout,
  telemetryRowsToCsv,
  togglePinnedTelemetryChannel,
  type TelemetryChartLayout
} from "../telemetryOps";
import { OperationsTelemetryChart } from "./OperationsTelemetryChart";

type SubsystemId =
  | "vehicle"
  | "gnc"
  | "propulsion"
  | "aerodynamics"
  | "environment"
  | "sensors"
  | "controls"
  | "faults"
  | "events"
  | "performance"
  | "engagement";

type OperationsEvent = Record<string, unknown>;

export type OperationsTelemetryPanelProps = {
  telemetry: TelemetrySeries | null | undefined;
  currentIndex: number;
  onJumpIndex?: (index: number) => void;
  onJumpTime?: (timeS: number) => void;
  metadata?: Record<string, TelemetryChannelMetadata>;
  compareTelemetry?: TelemetrySeries | null;
  compareRunLabel?: string;
  alarms?: AlarmSummary[];
  events?: OperationsEvent[];
};

type ChannelSummary = {
  key: string;
  current: string;
  min: string;
  max: string;
  rawCurrent: number | string | null | undefined;
};

type SavedLayout = {
  name: string;
  subsystem: SubsystemId;
  channels: string[];
  pinned: string[];
};

const SUBSYSTEMS: { id: SubsystemId; label: string; terms: string[]; defaults: string[] }[] = [
  { id: "vehicle", label: "Vehicle State", terms: ["vehicle", "truth", "state", "position", "velocity", "attitude"], defaults: ["altitude_m", "speed_mps", "roll_deg", "pitch_deg", "yaw_deg", "load_factor_g"] },
  { id: "gnc", label: "GNC State", terms: ["gnc", "guidance", "navigation", "control", "target", "range", "closing"], defaults: ["target_range_m", "closing_speed_mps", "cross_track_error_m", "heading_error_deg"] },
  { id: "propulsion", label: "Propulsion", terms: ["propulsion", "engine", "thrust", "throttle", "fuel", "motor"], defaults: ["throttle", "thrust_n", "fuel_mass_kg", "motor_rpm"] },
  { id: "aerodynamics", label: "Aerodynamics", terms: ["aero", "qbar", "alpha", "beta", "drag", "lift"], defaults: ["qbar_pa", "alpha_deg", "beta_deg", "drag_n", "lift_n"] },
  { id: "environment", label: "Environment", terms: ["environment", "wind", "density", "pressure", "temperature", "gravity"], defaults: ["wind_x_mps", "wind_y_mps", "air_density_kg_m3", "pressure_pa", "temperature_k"] },
  { id: "sensors", label: "Sensors", terms: ["sensor", "imu", "gps", "baro", "pitot", "radar", "measurement"], defaults: ["pitot_airspeed_mps", "baro_alt_m", "gps_z_m", "radar_agl_m"] },
  { id: "controls", label: "Controls/Actuators", terms: ["controls", "command", "actuator", "elevator", "aileron", "rudder"], defaults: ["elevator_deg", "aileron_deg", "rudder_deg", "throttle"] },
  { id: "faults", label: "Faults/Alarms", terms: ["fault", "alarm", "failure", "warning", "caution"], defaults: ["fault_active", "alarm_count"] },
  { id: "events", label: "Events", terms: ["event", "phase", "mode", "stage", "fuze"], defaults: ["event_count", "flight_phase"] },
  { id: "performance", label: "Derived Performance", terms: ["derived", "performance", "energy", "miss", "margin", "error"], defaults: ["specific_energy_j_kg", "miss_distance_m", "energy_margin", "max_load_factor_g"] },
  { id: "engagement", label: "Engagement", terms: ["engagement", "interceptor", "target", "relative", "fuze", "closing"], defaults: ["interceptor_range_m", "interceptor_closing_speed_mps", "relative_z_m", "target_range_m"] }
];

const DEFAULT_LAYOUT_NAME = "Mission overview";

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asTime(row: TelemetryRow | undefined): number | null {
  return asNumber(row?.time_s);
}

function allRows(telemetry: TelemetrySeries | null | undefined): TelemetryRow[] {
  if (!telemetry) {
    return [];
  }
  const groups = [telemetry.history, telemetry.truth, telemetry.controls, telemetry.sensors, telemetry.targets, telemetry.interceptors];
  const length = Math.max(...groups.map((rows) => rows?.length ?? 0), 0);
  return Array.from({ length }, (_, index) =>
    groups.reduce<TelemetryRow>((row, rows) => ({ ...row, ...(rows?.[index] ?? {}) }), {})
  );
}

function unique(items: string[]): string[] {
  return [...new Set(items.filter(Boolean))];
}

function metadataMap(telemetry: TelemetrySeries | null | undefined, override?: Record<string, TelemetryChannelMetadata>): Record<string, TelemetryChannelMetadata> | undefined {
  return override ?? telemetry?.metadata;
}

function channelKeys(telemetry: TelemetrySeries | null | undefined, metadata?: Record<string, TelemetryChannelMetadata>): string[] {
  const fromMetadata = Object.keys(metadata ?? {});
  const fromRows = allRows(telemetry).flatMap((row) => Object.keys(row));
  return unique([...fromMetadata, ...fromRows]).filter((key) => key !== "time_s").sort();
}

function channelText(metadata: Record<string, TelemetryChannelMetadata> | undefined, key: string): string {
  const meta = metadata?.[key];
  return [key, meta?.display_name, meta?.description, meta?.group, meta?.role, meta?.source].filter(Boolean).join(" ").toLowerCase();
}

function subsystemChannels(
  subsystem: SubsystemId,
  keys: string[],
  metadata: Record<string, TelemetryChannelMetadata> | undefined
): string[] {
  const config = SUBSYSTEMS.find((item) => item.id === subsystem) ?? SUBSYSTEMS[0];
  const direct = keys.filter((key) => {
    const text = channelText(metadata, key);
    return config.terms.some((term) => text.includes(term));
  });
  return unique([...config.defaults.filter((key) => keys.includes(key)), ...direct]);
}

function nearestIndexForTime(rows: TelemetryRow[], timeS: number): number {
  let nearest = 0;
  let delta = Number.POSITIVE_INFINITY;
  rows.forEach((row, index) => {
    const rowTime = asTime(row);
    if (rowTime === null) {
      return;
    }
    const nextDelta = Math.abs(rowTime - timeS);
    if (nextDelta < delta) {
      nearest = index;
      delta = nextDelta;
    }
  });
  return nearest;
}

function formatStat(value: number | string | null | undefined, unit = ""): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    const abs = Math.abs(value);
    const digits = abs >= 1000 ? 0 : abs >= 100 ? 1 : abs >= 10 ? 2 : 3;
    return `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
  }
  if (typeof value === "string") {
    return value || "-";
  }
  return "-";
}

function channelSummaries(rows: TelemetryRow[], currentIndex: number, channels: string[], metadata?: Record<string, TelemetryChannelMetadata>): ChannelSummary[] {
  return channels.map((key) => {
    const values = rows.map((row) => asNumber(row[key])).filter((value): value is number => value !== null);
    const unit = metadata?.[key]?.unit ?? "";
    return {
      key,
      current: formatTelemetryValue(rows[currentIndex], key, metadata),
      min: values.length ? formatStat(Math.min(...values), unit) : "-",
      max: values.length ? formatStat(Math.max(...values), unit) : "-",
      rawCurrent: rows[currentIndex]?.[key]
    };
  });
}

function truthSensorEstimateSuggestions(selected: string, keys: string[], metadata?: Record<string, TelemetryChannelMetadata>): { label: string; key: string | null }[] {
  const normalized = selected.replace(/^(truth_|sensor_|estimate_|estimated_|gps_|imu_|baro_|radar_|pitot_)/, "");
  const normalizedParts = normalized.split("_");
  const normalizedTail = normalizedParts[normalizedParts.length - 1] ?? normalized;
  const candidates = (terms: string[]) =>
    (keys.find((key) => {
      const text = channelText(metadata, key);
      return key.endsWith(normalized) && terms.some((term) => text.includes(term));
    }) ??
    keys.find((key) => terms.some((term) => key.includes(term)) && key.includes(normalizedTail)) ??
    null);
  return [
    { label: "Truth", key: candidates(["truth", "state", "history"]) },
    { label: "Sensor", key: candidates(["sensor", "gps", "imu", "baro", "radar", "pitot"]) },
    { label: "Estimate", key: candidates(["estimate", "estimated", "navigation", "filter", "gnc"]) }
  ];
}

function readLayouts(): SavedLayout[] {
  return listTelemetryChartLayouts()
    .filter((layout) => layout.config?.kind === "operations-telemetry")
    .map((layout) => ({
      name: layout.name,
      subsystem: typeof layout.config?.subsystem === "string" ? (layout.config.subsystem as SubsystemId) : "vehicle",
      channels: layout.channels,
      pinned: Array.isArray(layout.config?.pinned) ? layout.config.pinned.filter((item): item is string => typeof item === "string") : []
    }));
}

function writeLayout(layout: SavedLayout): SavedLayout[] {
  const existing = listTelemetryChartLayouts().find((item) => item.name === layout.name && item.config?.kind === "operations-telemetry");
  saveTelemetryChartLayout({
    id: existing?.id,
    name: layout.name,
    channels: layout.channels,
    config: {
      kind: "operations-telemetry",
      subsystem: layout.subsystem,
      pinned: layout.pinned
    }
  });
  return readLayouts();
}

function removeLayout(name: string): SavedLayout[] {
  const layout = listTelemetryChartLayouts().find((item: TelemetryChartLayout) => item.name === name && item.config?.kind === "operations-telemetry");
  if (layout) {
    deleteTelemetryChartLayout(layout.id);
  }
  return readLayouts();
}

export function OperationsTelemetryPanel({
  telemetry,
  currentIndex,
  onJumpIndex,
  onJumpTime,
  metadata: metadataOverride,
  compareTelemetry,
  compareRunLabel,
  alarms = [],
  events = []
}: OperationsTelemetryPanelProps) {
  const metadata = metadataMap(telemetry, metadataOverride);
  const rows = useMemo(() => allRows(telemetry), [telemetry]);
  const compareRows = useMemo(() => allRows(compareTelemetry), [compareTelemetry]);
  const keys = useMemo(() => channelKeys(telemetry, metadata), [telemetry, metadata]);
  const safeIndex = Math.min(Math.max(currentIndex, 0), Math.max(rows.length - 1, 0));
  const [activeSubsystem, setActiveSubsystem] = useState<SubsystemId>("vehicle");
  const [query, setQuery] = useState("");
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [pinnedChannels, setPinnedChannels] = useState<string[]>([]);
  const [selectedChannel, setSelectedChannel] = useState("");
  const [layoutName, setLayoutName] = useState(DEFAULT_LAYOUT_NAME);
  const [layouts, setLayouts] = useState<SavedLayout[]>([]);

  const subsystemKeys = useMemo(() => subsystemChannels(activeSubsystem, keys, metadata), [activeSubsystem, keys, metadata]);
  const visibleKeys = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const source = subsystemKeys.length ? subsystemKeys : keys;
    if (!needle) {
      return source;
    }
    return source.filter((key) => channelText(metadata, key).includes(needle));
  }, [keys, metadata, query, subsystemKeys]);

  useEffect(() => {
    setLayouts(readLayouts());
    setPinnedChannels(listPinnedTelemetryChannels().filter((key) => keys.includes(key)).slice(0, 8));
  }, [keys]);

  useEffect(() => {
    const defaults = subsystemKeys.slice(0, 5);
    setSelectedChannels((current) => {
      const retained = current.filter((key) => subsystemKeys.includes(key));
      return retained.length ? retained : defaults;
    });
    setSelectedChannel((current) => (current && subsystemKeys.includes(current) ? current : defaults[0] ?? subsystemKeys[0] ?? ""));
  }, [subsystemKeys]);

  const chartChannels = unique([...pinnedChannels, ...selectedChannels]).filter((key) => keys.includes(key)).slice(0, 10);
  const summaries = channelSummaries(rows, safeIndex, chartChannels, metadata);
  const selectedSuggestions = truthSensorEstimateSuggestions(selectedChannel || chartChannels[0] || "", keys, metadata);
  const currentTime = asTime(rows[safeIndex]);

  const toggleChannel = (key: string) => {
    setSelectedChannel(key);
    setSelectedChannels((current) => (current.includes(key) ? current.filter((item) => item !== key) : [...current, key].slice(-8)));
  };

  const togglePin = (key: string) => {
    const next = togglePinnedTelemetryChannel(key).filter((item) => keys.includes(item)).slice(0, 8);
    setPinnedChannels(next);
    setSelectedChannel(key);
  };

  const jumpToTime = (timeS: number) => {
    if (!Number.isFinite(timeS)) {
      return;
    }
    if (onJumpTime) {
      onJumpTime(timeS);
      return;
    }
    onJumpIndex?.(nearestIndexForTime(rows, timeS));
  };

  const saveLayout = () => {
    const name = layoutName.trim() || DEFAULT_LAYOUT_NAME;
    setLayouts(writeLayout({ name, subsystem: activeSubsystem, channels: selectedChannels, pinned: pinnedChannels }));
    setLayoutName(name);
  };

  const loadLayout = (layout: SavedLayout) => {
    setActiveSubsystem(layout.subsystem);
    setSelectedChannels(layout.channels.filter((key) => keys.includes(key)));
    setPinnedChannels(layout.pinned.filter((key) => keys.includes(key)));
    setSelectedChannel(layout.channels[0] ?? layout.pinned[0] ?? "");
    setLayoutName(layout.name);
  };

  const exportCsv = () => {
    if (!chartChannels.length) {
      return;
    }
    const csv = telemetryRowsToCsv([{ id: telemetry?.run_id ?? "run", rows }], ["time_s", ...chartChannels], { includeRunId: true, includeRowIndex: true });
    downloadTelemetryCsv(`operations-telemetry-${telemetry?.run_id ?? "run"}.csv`, csv);
  };

  return (
    <section className="operations-telemetry-panel">
      <header className="operations-telemetry-header">
        <div>
          <p className="eyebrow">Mission Control</p>
          <h2>Operations Telemetry</h2>
          <p>
            {telemetry?.run_id ?? "No run selected"} · {rows.length} samples · {currentTime === null ? "no cursor" : `${currentTime.toFixed(2)}s`}
          </p>
        </div>
        <div className="operations-telemetry-actions">
          <button type="button" className="secondary-action" onClick={exportCsv} disabled={!chartChannels.length}>
            <Download size={16} />
            Export selected
          </button>
          <label className="field compact-field">
            <span>Layout</span>
            <input value={layoutName} onChange={(event) => setLayoutName(event.target.value)} />
          </label>
          <button type="button" className="secondary-action" onClick={saveLayout}>
            <Save size={16} />
            Save
          </button>
        </div>
      </header>

      <div className="operations-subsystem-tabs" role="tablist" aria-label="Telemetry subsystems">
        {SUBSYSTEMS.map((subsystem) => (
          <button
            key={subsystem.id}
            type="button"
            role="tab"
            className={activeSubsystem === subsystem.id ? "active" : ""}
            onClick={() => setActiveSubsystem(subsystem.id)}
          >
            {subsystem.label}
          </button>
        ))}
      </div>

      <div className="operations-telemetry-grid">
        <aside className="operations-channel-browser">
          <label className="field operations-search">
            <span>
              <Search size={15} />
              Search parameters
            </span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="channel, unit, role, subsystem" />
          </label>

          {pinnedChannels.length > 0 && (
            <section className="operations-pinned-row" aria-label="Pinned channels">
              <div className="section-title">
                <Pin size={15} />
                <h3>Pinned</h3>
              </div>
              <div className="channel-strip">
                {pinnedChannels.map((key) => (
                  <span key={key} className="channel-chip pinned">
                    <button type="button" onClick={() => setSelectedChannel(key)}>
                      {channelLabel(metadata, key)}
                    </button>
                    <button type="button" aria-label={`Unpin ${channelLabel(metadata, key)}`} onClick={() => togglePin(key)}>
                      <PinOff size={13} />
                    </button>
                  </span>
                ))}
              </div>
            </section>
          )}

          <div className="operations-channel-list" role="listbox" aria-label={`${activeSubsystem} telemetry channels`}>
            {visibleKeys.map((key) => {
              const selected = selectedChannels.includes(key);
              const pinned = pinnedChannels.includes(key);
              return (
                <div key={key} className={`operations-channel-option ${selected ? "selected" : ""}`}>
                  <button type="button" onClick={() => toggleChannel(key)} aria-pressed={selected}>
                    <strong>{channelLabelWithUnit(metadata, key)}</strong>
                    <span>{key}</span>
                  </button>
                  <button type="button" className={pinned ? "active" : ""} aria-label={`${pinned ? "Unpin" : "Pin"} ${channelLabel(metadata, key)}`} onClick={() => togglePin(key)}>
                    <Pin size={14} />
                  </button>
                </div>
              );
            })}
            {visibleKeys.length === 0 && <div className="empty-state">No matching telemetry channels.</div>}
          </div>
        </aside>

        <main className="operations-telemetry-main">
          <section className="operations-chart-card">
            <div className="section-title">
              <Layers3 size={16} />
              <h3>{SUBSYSTEMS.find((item) => item.id === activeSubsystem)?.label ?? "Telemetry"}</h3>
            </div>
            <OperationsTelemetryChart
              title="Cursor-linked telemetry"
              rows={rows}
              channels={chartChannels}
              currentIndex={safeIndex}
              metadata={metadata}
              compareRows={compareRows.length ? compareRows : undefined}
              compareLabel={compareRunLabel}
              cursorTime={currentTime ?? undefined}
              onCursorTimeChange={jumpToTime}
              multiAxis
              showLimits
              pinnedChannels={pinnedChannels}
            />
          </section>

          <section className="operations-current-values">
            <div className="section-title">
              <Gauge size={16} />
              <h3>Current Values</h3>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Channel</th>
                  <th>Current</th>
                  <th>Min</th>
                  <th>Max</th>
                  <th>Raw key</th>
                </tr>
              </thead>
              <tbody>
                {summaries.map((summary) => (
                  <tr key={summary.key} className={selectedChannel === summary.key ? "active" : ""} onClick={() => setSelectedChannel(summary.key)}>
                    <td>{channelLabelWithUnit(metadata, summary.key)}</td>
                    <td>{summary.current}</td>
                    <td>{summary.min}</td>
                    <td>{summary.max}</td>
                    <td>
                      <code>{summary.key}</code>
                    </td>
                  </tr>
                ))}
                {summaries.length === 0 && (
                  <tr>
                    <td colSpan={5}>Select channels to populate the cursor table.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>

          <section className="operations-suggestion-panel">
            <div className="section-title">
              <Eye size={16} />
              <h3>Truth / Sensor / Estimate</h3>
            </div>
            <div className="operations-suggestion-grid">
              {selectedSuggestions.map((suggestion) => (
                <button
                  key={suggestion.label}
                  type="button"
                  className={suggestion.key && chartChannels.includes(suggestion.key) ? "active" : ""}
                  disabled={!suggestion.key}
                  onClick={() => suggestion.key && toggleChannel(suggestion.key)}
                >
                  <span>{suggestion.label}</span>
                  <strong>{suggestion.key ? channelLabelWithUnit(metadata, suggestion.key) : "No close match"}</strong>
                </button>
              ))}
            </div>
          </section>

          <section className="operations-compare-panel">
            <div className="section-title">
              <Layers3 size={16} />
              <h3>Compare Run</h3>
            </div>
            {compareTelemetry ? (
              <p>
                Comparing against <strong>{compareRunLabel || compareTelemetry.run_id}</strong> with {compareRows.length} samples.
              </p>
            ) : (
              <p className="empty-state">Comparison appears here when Workbench passes the existing compare run selector telemetry.</p>
            )}
          </section>

          <section className="operations-layouts-panel">
            <div className="section-title">
              <Save size={16} />
              <h3>Saved Layouts</h3>
            </div>
            <div className="operations-layout-list">
              {layouts.map((layout) => (
                <div key={layout.name} className="operations-layout-item">
                  <button type="button" onClick={() => loadLayout(layout)}>
                    <strong>{layout.name}</strong>
                    <span>
                      {layout.channels.length} channels · {layout.pinned.length} pinned
                    </span>
                  </button>
                  <button type="button" aria-label={`Delete ${layout.name}`} onClick={() => setLayouts(removeLayout(layout.name))}>
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
              {layouts.length === 0 && <div className="empty-state">No saved chart layouts.</div>}
            </div>
          </section>
        </main>

        <aside className="operations-context-rail">
          <section className="operations-alarm-panel">
            <div className="section-title">
              <Bell size={16} />
              <h3>Faults / Alarms</h3>
            </div>
            <div className="event-list">
              {alarms.slice(0, 8).map((alarm) => (
                <button key={alarm.id} type="button" className={`event-item ${alarm.severity}`} onClick={() => jumpToTime(alarm.first_triggered_time_s)}>
                  <span>{alarm.first_triggered_time_s.toFixed(2)}s</span>
                  <strong>{alarm.name}</strong>
                  <p>{alarm.message}</p>
                </button>
              ))}
              {alarms.length === 0 && <div className="empty-state">No alarms passed to the operations panel.</div>}
            </div>
          </section>

          <section className="operations-events-panel">
            <div className="section-title">
              <Bell size={16} />
              <h3>Events</h3>
            </div>
            <div className="event-list">
              {events.slice(0, 10).map((event, index) => {
                const timeS = asNumber(event.time_s);
                return (
                  <button key={`${String(event.type ?? "event")}-${index}`} type="button" className="event-item" onClick={() => timeS !== null && jumpToTime(timeS)}>
                    <span>{timeS === null ? "-" : `${timeS.toFixed(2)}s`}</span>
                    <strong>{String(event.type ?? event.name ?? "event").replaceAll("_", " ")}</strong>
                    <p>{String(event.description ?? event.message ?? "")}</p>
                  </button>
                );
              })}
              {events.length === 0 && <div className="empty-state">No events passed to the operations panel.</div>}
            </div>
          </section>
        </aside>
      </div>
    </section>
  );
}
