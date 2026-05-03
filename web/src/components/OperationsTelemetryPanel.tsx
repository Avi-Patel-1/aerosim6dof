import {
  Bell,
  Clipboard,
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
import { channelLabel, channelLabelWithUnit } from "../telemetry";
import type { AlarmSummary, TelemetryChannelMetadata, TelemetryRow, TelemetrySeries } from "../types";
import {
  buildTelemetryOpsLayoutPayload,
  deleteTelemetryChartLayout,
  downloadTelemetryCsv,
  groupTruthSensorEstimateChannels,
  listPinnedTelemetryChannels,
  listTelemetryChartLayouts,
  numericStatsForChannel,
  parseTelemetryOpsLayoutPayload,
  saveTelemetryChartLayout,
  selectedTelemetryRowsToCsvText,
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
  sampleIndex: number;
  numericCount: number;
};

type SavedLayout = {
  id: string;
  name: string;
  subsystem: SubsystemId;
  channels: string[];
  pinned: string[];
  selectedChannel: string;
  query: string;
  savedAt: string;
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
  const candidate = override ?? telemetry?.metadata;
  return candidate && typeof candidate === "object" ? candidate : undefined;
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

function nearestDefinedSample(rows: TelemetryRow[], currentIndex: number, key: string): { value: TelemetryRow[string] | undefined; index: number } {
  if (!rows.length) {
    return { value: undefined, index: -1 };
  }
  const boundedIndex = Math.min(Math.max(currentIndex, 0), rows.length - 1);
  const direct = rows[boundedIndex]?.[key];
  if (direct !== null && direct !== undefined && direct !== "") {
    return { value: direct, index: boundedIndex };
  }
  for (let index = boundedIndex - 1; index >= 0; index -= 1) {
    const value = rows[index]?.[key];
    if (value !== null && value !== undefined && value !== "") {
      return { value, index };
    }
  }
  for (let index = boundedIndex + 1; index < rows.length; index += 1) {
    const value = rows[index]?.[key];
    if (value !== null && value !== undefined && value !== "") {
      return { value, index };
    }
  }
  return { value: undefined, index: -1 };
}

function channelSummaries(rows: TelemetryRow[], currentIndex: number, channels: string[], metadata?: Record<string, TelemetryChannelMetadata>): ChannelSummary[] {
  return channels.map((key) => {
    const stats = numericStatsForChannel(rows, key, currentIndex);
    const sample = nearestDefinedSample(rows, currentIndex, key);
    const unit = metadata?.[key]?.unit ?? "";
    const current = sample.value === undefined ? "-" : typeof sample.value === "number" ? formatStat(sample.value, unit) : formatStat(sample.value);
    return {
      key,
      current,
      min: formatStat(stats.min, unit),
      max: formatStat(stats.max, unit),
      rawCurrent: sample.value,
      sampleIndex: sample.index,
      numericCount: stats.count
    };
  });
}

function isSubsystemId(value: string): value is SubsystemId {
  return SUBSYSTEMS.some((subsystem) => subsystem.id === value);
}

function readLayouts(): SavedLayout[] {
  return listTelemetryChartLayouts()
    .map((layout) => ({ layout, payload: parseTelemetryOpsLayoutPayload(layout.config) }))
    .filter((item): item is { layout: TelemetryChartLayout; payload: NonNullable<ReturnType<typeof parseTelemetryOpsLayoutPayload>> } => item.payload !== null)
    .map(({ layout, payload }) => ({
      id: layout.id,
      name: layout.name,
      subsystem: isSubsystemId(payload.subsystem) ? payload.subsystem : "vehicle",
      channels: unique(payload.channels.length ? payload.channels : layout.channels),
      pinned: payload.pinned,
      selectedChannel: payload.selectedChannel,
      query: payload.query,
      savedAt: payload.savedAt
    }));
}

function writeLayout(layout: SavedLayout): SavedLayout[] {
  const existing = listTelemetryChartLayouts().find((item) => item.name === layout.name && parseTelemetryOpsLayoutPayload(item.config));
  const payload = buildTelemetryOpsLayoutPayload({
    subsystem: layout.subsystem,
    channels: layout.channels,
    pinned: layout.pinned,
    selectedChannel: layout.selectedChannel,
    query: layout.query
  });
  saveTelemetryChartLayout({
    id: existing?.id,
    name: layout.name,
    channels: layout.channels,
    config: payload
  });
  return readLayouts();
}

function removeLayout(name: string): SavedLayout[] {
  const layout = listTelemetryChartLayouts().find((item: TelemetryChartLayout) => item.name === name && parseTelemetryOpsLayoutPayload(item.config));
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
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

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
  const comparisonGroups = groupTruthSensorEstimateChannels(selectedChannel || chartChannels[0] || "", keys, metadata);
  const currentTime = asTime(rows[safeIndex]);
  const csvChannels = useMemo(() => unique(["time_s", ...chartChannels]).filter((key) => key === "time_s" || keys.includes(key)), [chartChannels, keys]);
  const selectedCsvText = useMemo(
    () =>
      selectedTelemetryRowsToCsvText([{ id: telemetry?.run_id ?? "run", rows }], csvChannels, {
        includeRunId: true,
        includeRowIndex: true
      }),
    [csvChannels, rows, telemetry?.run_id]
  );

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
    setLayouts(writeLayout({ id: "", name, subsystem: activeSubsystem, channels: selectedChannels, pinned: pinnedChannels, selectedChannel, query, savedAt: "" }));
    setLayoutName(name);
  };

  const loadLayout = (layout: SavedLayout) => {
    const layoutChannels = layout.channels.filter((key) => keys.includes(key));
    const layoutPinned = layout.pinned.filter((key) => keys.includes(key));
    const preferredChannel = layout.selectedChannel && [...layoutChannels, ...layoutPinned].includes(layout.selectedChannel) ? layout.selectedChannel : layoutChannels[0] ?? layoutPinned[0] ?? "";
    setActiveSubsystem(layout.subsystem);
    setSelectedChannels(layoutChannels);
    setPinnedChannels(layoutPinned);
    setSelectedChannel(preferredChannel);
    setQuery(layout.query);
    setLayoutName(layout.name);
  };

  const exportCsv = () => {
    if (!chartChannels.length) {
      return;
    }
    downloadTelemetryCsv(`operations-telemetry-${telemetry?.run_id ?? "run"}.csv`, selectedCsvText);
  };

  const copyCsvText = async () => {
    if (!selectedCsvText || typeof navigator === "undefined" || !navigator.clipboard) {
      setCopyState("failed");
      return;
    }
    try {
      await navigator.clipboard.writeText(selectedCsvText);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
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
          <button type="button" className="secondary-action" onClick={copyCsvText} disabled={!chartChannels.length}>
            <Clipboard size={16} />
            {copyState === "copied" ? "CSV copied" : "Copy CSV text"}
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

          <div className="operations-channel-list" role="list" aria-label={`${activeSubsystem} telemetry channels`}>
            {visibleKeys.map((key) => {
              const selected = selectedChannels.includes(key);
              const pinned = pinnedChannels.includes(key);
              return (
                <div key={key} className={`operations-channel-option ${selected ? "selected" : ""}`} role="listitem">
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
            <details className="operations-csv-text">
              <summary>Selected CSV text ({csvChannels.length} columns)</summary>
              <textarea readOnly spellCheck={false} rows={4} value={selectedCsvText} aria-label="Selected telemetry CSV text" />
              {copyState === "failed" && <p className="empty-state">Clipboard unavailable; CSV text remains selectable here.</p>}
            </details>
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
                  <tr key={summary.key} className={selectedChannel === summary.key ? "active" : ""}>
                    <td>
                      <button type="button" className="table-link-button" onClick={() => setSelectedChannel(summary.key)}>
                        {channelLabelWithUnit(metadata, summary.key)}
                      </button>
                    </td>
                    <td>{summary.current}</td>
                    <td>{summary.min}</td>
                    <td>{summary.max}</td>
                    <td>
                      <code>{summary.key}</code>
                      {summary.sampleIndex >= 0 && summary.sampleIndex !== safeIndex && <small> sample {summary.sampleIndex}</small>}
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
              {comparisonGroups.flatMap((group) =>
                group.channels.length
                  ? group.channels.map((suggestion) => (
                      <button
                        key={`${group.role}-${suggestion.channel}`}
                        type="button"
                        className={chartChannels.includes(suggestion.channel) ? "active" : ""}
                        onClick={() => toggleChannel(suggestion.channel)}
                      >
                        <span>{group.label}</span>
                        <strong>{channelLabelWithUnit(metadata, suggestion.channel)}</strong>
                      </button>
                    ))
                  : [
                      <button key={group.role} type="button" disabled>
                        <span>{group.label}</span>
                        <strong>No close match</strong>
                      </button>
                    ]
              )}
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
                    {layout.savedAt && <span>Saved {new Date(layout.savedAt).toLocaleString()}</span>}
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
