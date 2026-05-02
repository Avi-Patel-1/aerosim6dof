import type { TelemetryChannelMetadata, TelemetryRange, TelemetryRow } from "../types";
import { channelLabel, formatTelemetryValue, metadataFor } from "../telemetry";

type ParameterInfoPanelProps = {
  channel: string | undefined;
  row: TelemetryRow | undefined;
  metadata?: Record<string, TelemetryChannelMetadata>;
};

function rangeText(range: TelemetryRange | null | undefined): string {
  if (!range) {
    return "";
  }
  const min = range.min ?? "-inf";
  const max = range.max ?? "+inf";
  return range.label ? `${range.label}: ${min} to ${max}` : `${min} to ${max}`;
}

export function ParameterInfoPanel({ channel, row, metadata }: ParameterInfoPanelProps) {
  if (!channel) {
    return (
      <section className="parameter-panel">
        <div>
          <span>Parameter</span>
          <strong>No channel selected</strong>
        </div>
      </section>
    );
  }

  const details = metadataFor(metadata, channel);
  const ranges = [
    ["Valid", details?.valid_range],
    ["Caution", details?.caution_range],
    ["Warning", details?.warning_range],
    ["Fatal", details?.fatal_range]
  ].filter(([, range]) => Boolean(rangeText(range as TelemetryRange | null | undefined)));

  return (
    <section className="parameter-panel">
      <div className="parameter-heading">
        <span>Selected parameter</span>
        <strong>{channelLabel(metadata, channel)}</strong>
        <code>{channel}</code>
      </div>
      <dl className="parameter-grid">
        <div>
          <dt>Current</dt>
          <dd>{formatTelemetryValue(row, channel, metadata)}</dd>
        </div>
        <div>
          <dt>Unit</dt>
          <dd>{details?.unit || "-"}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{details?.source ?? "unknown"}</dd>
        </div>
        <div>
          <dt>Subsystem</dt>
          <dd>{details?.group ?? "Unknown"}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{(details?.role ?? "truth").replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt>Derived</dt>
          <dd>{details?.derived ? "yes" : "no"}</dd>
        </div>
      </dl>
      <p>{details?.description || "Telemetry channel discovered from run output."}</p>
      {ranges.length > 0 && (
        <div className="parameter-ranges" aria-label="Parameter limits">
          {ranges.map(([label, range]) => (
            <span key={label as string}>
              <b>{label as string}</b>
              {rangeText(range as TelemetryRange)}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
