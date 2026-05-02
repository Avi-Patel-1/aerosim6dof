import type { TelemetryChannelMetadata, TelemetryRow } from "./types";

export function fallbackChannelLabel(channel: string): string {
  return channel
    .split("_")
    .filter(Boolean)
    .map((part) => {
      const lower = part.toLowerCase();
      if (["gps", "imu", "agl"].includes(lower)) {
        return lower.toUpperCase();
      }
      if (lower === "qbar") {
        return "Qbar";
      }
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(" ");
}

export function metadataFor(metadata: Record<string, TelemetryChannelMetadata> | undefined, channel: string): TelemetryChannelMetadata | undefined {
  return metadata?.[channel];
}

export function channelLabel(metadata: Record<string, TelemetryChannelMetadata> | undefined, channel: string): string {
  return metadataFor(metadata, channel)?.display_name || fallbackChannelLabel(channel);
}

export function channelUnit(metadata: Record<string, TelemetryChannelMetadata> | undefined, channel: string): string {
  return metadataFor(metadata, channel)?.unit || "";
}

export function channelLabelWithUnit(metadata: Record<string, TelemetryChannelMetadata> | undefined, channel: string): string {
  const label = channelLabel(metadata, channel);
  const unit = channelUnit(metadata, channel);
  return unit ? `${label} (${unit})` : label;
}

export function formatTelemetryValue(row: TelemetryRow | undefined, channel: string, metadata?: Record<string, TelemetryChannelMetadata>): string {
  const value = row?.[channel];
  const unit = channelUnit(metadata, channel);
  if (typeof value === "number" && Number.isFinite(value)) {
    const abs = Math.abs(value);
    const digits = abs >= 100 ? 1 : abs >= 10 ? 2 : 3;
    return `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
  }
  if (typeof value === "string") {
    return value;
  }
  return "-";
}
