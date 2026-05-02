import { channelLabelWithUnit, formatTelemetryValue } from "../telemetry";
import type { TelemetryChannelMetadata, TelemetryRange, TelemetryRow } from "../types";

type OperationsTelemetryChartProps = {
  title: string;
  rows: TelemetryRow[];
  channels: string[];
  currentIndex: number;
  metadata?: Record<string, TelemetryChannelMetadata>;
  compareRows?: TelemetryRow[];
  compareLabel?: string;
  cursorTime?: number;
  onCursorTimeChange?: (timeS: number) => void;
  multiAxis?: boolean;
  showLimits?: boolean;
  pinnedChannels?: string[];
  readoutChannels?: string[];
};

type LimitLine = {
  value: number;
  className: string;
  label: string;
};

type LimitBand = {
  min: number;
  max: number;
  className: string;
  label: string;
};

type Scale = {
  min: number;
  max: number;
  span: number;
};

const COLORS = ["#ededf3", "#cdddff", "#9aa0b8", "#d7ddf2", "#70707d", "#b7bed8", "#ffffff", "#858aa1"];
const LIMIT_FILLS: Record<string, string> = {
  caution: "#cdddff",
  warning: "#ededf3",
  fatal: "#70707d"
};

function asNumber(value: TelemetryRow[string] | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function uniqueChannels(primary: string[], pinned: string[] | undefined): string[] {
  const seen = new Set<string>();
  return [...(pinned ?? []), ...primary].filter((channel) => {
    if (!channel || seen.has(channel)) {
      return false;
    }
    seen.add(channel);
    return true;
  }).slice(0, 8);
}

function rangeValues(range: TelemetryRange | null | undefined): number[] {
  if (!range) {
    return [];
  }
  return [range.min, range.max].filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

function limitLines(metadata: TelemetryChannelMetadata | undefined): LimitLine[] {
  if (!metadata) {
    return [];
  }
  const collect = (range: TelemetryRange | null | undefined, className: string, fallback: string): LimitLine[] => {
    const label = range?.label || fallback;
    return rangeValues(range).map((value) => ({ value, className: `limit-line ${className}`, label }));
  };
  return [
    ...collect(metadata.caution_range, "caution", "caution"),
    ...collect(metadata.warning_range, "warning", "warning"),
    ...collect(metadata.fatal_range, "fatal", "fatal")
  ];
}

function limitBands(metadata: TelemetryChannelMetadata | undefined): LimitBand[] {
  if (!metadata) {
    return [];
  }
  const collect = (range: TelemetryRange | null | undefined, className: string, fallback: string): LimitBand[] => {
    if (!range || typeof range.min !== "number" || typeof range.max !== "number" || !Number.isFinite(range.min) || !Number.isFinite(range.max)) {
      return [];
    }
    return [{ min: Math.min(range.min, range.max), max: Math.max(range.min, range.max), className, label: range.label || fallback }];
  };
  return [
    ...collect(metadata.caution_range, "caution", "caution"),
    ...collect(metadata.warning_range, "warning", "warning"),
    ...collect(metadata.fatal_range, "fatal", "fatal")
  ];
}

function valuesFor(rows: TelemetryRow[], channel: string): number[] {
  return rows.map((row) => asNumber(row[channel])).filter((value): value is number => value !== null);
}

function buildScale(values: number[]): Scale {
  if (!values.length) {
    return { min: 0, max: 1, span: 1 };
  }
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    const pad = Math.abs(min) > 1 ? Math.abs(min) * 0.05 : 1;
    min -= pad;
    max += pad;
  }
  const span = max - min || 1;
  const pad = span * 0.06;
  return { min: min - pad, max: max + pad, span: span + pad * 2 };
}

function nearestRow(rows: TelemetryRow[], timeS: number): TelemetryRow | undefined {
  let best: TelemetryRow | undefined;
  let bestDelta = Number.POSITIVE_INFINITY;
  rows.forEach((row) => {
    const sampleTime = asNumber(row.time_s);
    if (sampleTime === null) {
      return;
    }
    const delta = Math.abs(sampleTime - timeS);
    if (delta < bestDelta) {
      best = row;
      bestDelta = delta;
    }
  });
  return best;
}

function formatAxisValue(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1000) {
    return value.toFixed(0);
  }
  if (abs >= 100) {
    return value.toFixed(1);
  }
  if (abs >= 10) {
    return value.toFixed(2);
  }
  return value.toFixed(3);
}

export function OperationsTelemetryChart({
  title,
  rows,
  channels,
  currentIndex,
  metadata,
  compareRows = [],
  compareLabel = "compare",
  cursorTime,
  onCursorTimeChange,
  multiAxis = false,
  showLimits = true,
  pinnedChannels,
  readoutChannels
}: OperationsTelemetryChartProps) {
  const width = 860;
  const height = 248;
  const padding = { top: 20, right: multiAxis ? 74 : 24, bottom: 32, left: 54 };
  const usableWidth = width - padding.left - padding.right;
  const usableHeight = height - padding.top - padding.bottom;
  const visibleChannels = uniqueChannels(channels, pinnedChannels);
  const allRows = [...rows, ...compareRows];
  const times = allRows.map((row) => asNumber(row.time_s)).filter((value): value is number => value !== null);
  const minTime = times.length ? Math.min(...times) : 0;
  const maxTime = times.length ? Math.max(...times) : 1;
  const spanTime = maxTime - minTime || 1;
  const indexedTime = asNumber(rows[currentIndex]?.time_s);
  const activeTime = Math.min(Math.max(cursorTime ?? indexedTime ?? minTime, minTime), maxTime);
  const cursorX = padding.left + ((activeTime - minTime) / spanTime) * usableWidth;
  const activeRow = nearestRow(rows, activeTime) ?? rows[currentIndex];
  const activeCompareRow = compareRows.length ? nearestRow(compareRows, activeTime) : undefined;
  const singleChannelMetadata = visibleChannels.length === 1 ? metadata?.[visibleChannels[0]] : undefined;
  const activeLimitLines = showLimits && singleChannelMetadata ? limitLines(singleChannelMetadata) : [];
  const activeLimitBands = showLimits && singleChannelMetadata ? limitBands(singleChannelMetadata) : [];
  const limitValues = activeLimitLines.map((line) => line.value);
  const sharedScale = buildScale([
    ...visibleChannels.flatMap((channel) => valuesFor(rows, channel)),
    ...visibleChannels.flatMap((channel) => valuesFor(compareRows, channel)),
    ...(visibleChannels.length === 1 ? limitValues : [])
  ]);
  const channelScales = new Map(
    visibleChannels.map((channel) => [
      channel,
      buildScale([
        ...valuesFor(rows, channel),
        ...valuesFor(compareRows, channel),
        ...(visibleChannels.length === 1 ? limitValues : [])
      ])
    ])
  );
  const scaleFor = (channel: string) => (multiAxis ? channelScales.get(channel) ?? sharedScale : sharedScale);
  const yFor = (value: number, scale: Scale) => padding.top + usableHeight - ((value - scale.min) / scale.span) * usableHeight;
  const xFor = (timeS: number) => padding.left + ((timeS - minTime) / spanTime) * usableWidth;
  const readoutSet = readoutChannels?.length ? new Set(readoutChannels) : null;
  const legendChannels = visibleChannels.filter((channel) => !readoutSet || readoutSet.has(channel));
  const hasRenderableValues = visibleChannels.some((channel) => valuesFor(rows, channel).length > 0 || valuesFor(compareRows, channel).length > 0);

  const segmentsFor = (sourceRows: TelemetryRow[], channel: string): string[] => {
    const scale = scaleFor(channel);
    const segments: string[] = [];
    let current: string[] = [];
    sourceRows.forEach((row) => {
      const sampleTime = asNumber(row.time_s);
      const value = asNumber(row[channel]);
      if (sampleTime === null || value === null) {
        if (current.length) {
          segments.push(current.join(" "));
          current = [];
        }
        return;
      }
      current.push(`${xFor(sampleTime).toFixed(1)},${yFor(value, scale).toFixed(1)}`);
    });
    if (current.length) {
      segments.push(current.join(" "));
    }
    return segments;
  };

  const handlePointer = (event: { currentTarget: SVGSVGElement; clientX: number }) => {
    if (!onCursorTimeChange) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
    const svgX = ratio * width;
    const clampedX = Math.min(Math.max(svgX, padding.left), width - padding.right);
    const nextTime = minTime + ((clampedX - padding.left) / usableWidth) * spanTime;
    onCursorTimeChange(nextTime);
  };

  return (
    <section className="chart-panel operations-telemetry-chart">
      <div className="chart-header operations-chart-header">
        <h3>{title}</h3>
        <div className="legend operations-chart-legend">
          {legendChannels.map((channel, index) => (
            <span key={channel}>
              <i style={{ background: COLORS[index % COLORS.length] }} />
              <b>{channelLabelWithUnit(metadata, channel)}</b>
              <em>{formatTelemetryValue(activeRow, channel, metadata)}</em>
              {activeCompareRow && <small>{compareLabel}: {formatTelemetryValue(activeCompareRow, channel, metadata)}</small>}
            </span>
          ))}
        </div>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={title}
        onClick={handlePointer}
        onMouseMove={handlePointer}
      >
        <rect x="0" y="0" width={width} height={height} rx="0" className="chart-bg" />
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="axis" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} className="axis" />
        {[0.2, 0.4, 0.6, 0.8].map((ratio) => {
          const y = padding.top + usableHeight * ratio;
          return <line key={ratio} x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="grid-line" />;
        })}
        {[0.25, 0.5, 0.75].map((ratio) => {
          const x = padding.left + usableWidth * ratio;
          return <line key={ratio} x1={x} y1={padding.top} x2={x} y2={height - padding.bottom} className="grid-line" />;
        })}
        {activeLimitBands.map((band, index) => {
          const scale = scaleFor(visibleChannels[0]);
          const y1 = yFor(band.max, scale);
          const y2 = yFor(band.min, scale);
          const y = Math.max(padding.top, Math.min(y1, y2));
          const bandHeight = Math.max(1, Math.min(height - padding.bottom, Math.max(y1, y2)) - y);
          return (
            <rect
              key={`${band.className}-${band.min}-${band.max}-${index}`}
              x={padding.left}
              y={y}
              width={usableWidth}
              height={bandHeight}
              fill={LIMIT_FILLS[band.className]}
              opacity="0.07"
            />
          );
        })}
        {activeLimitLines.map((line, index) => {
          const scale = scaleFor(visibleChannels[0]);
          if (line.value < scale.min || line.value > scale.max) {
            return null;
          }
          const y = yFor(line.value, scale);
          return (
            <g key={`${line.className}-${line.value}-${index}`}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} className={line.className} />
              <text x={width - padding.right - 104} y={y - 5} className="limit-label">
                {line.label}
              </text>
            </g>
          );
        })}
        {visibleChannels.map((channel, index) =>
          segmentsFor(compareRows, channel).map((points, segmentIndex) => (
            <polyline
              key={`compare-${channel}-${segmentIndex}`}
              points={points}
              fill="none"
              stroke={COLORS[index % COLORS.length]}
              strokeWidth="1.8"
              strokeDasharray="8 6"
              opacity="0.38"
            />
          ))
        )}
        {visibleChannels.map((channel, index) =>
          segmentsFor(rows, channel).map((points, segmentIndex) => (
            <polyline
              key={`${channel}-${segmentIndex}`}
              points={points}
              fill="none"
              stroke={COLORS[index % COLORS.length]}
              strokeWidth={multiAxis ? "2.1" : "2.4"}
              opacity={multiAxis && visibleChannels.length > 1 ? "0.9" : "1"}
            />
          ))
        )}
        <line x1={cursorX} y1={padding.top} x2={cursorX} y2={height - padding.bottom} className="cursor-line" />
        <circle cx={cursorX} cy={height - padding.bottom} r="3.2" fill="#cdddff" opacity="0.92" />
        <text x={padding.left} y={height - 9} className="axis-label">
          {minTime.toFixed(1)}s
        </text>
        <text x={cursorX + 6 > width - padding.right - 50 ? cursorX - 50 : cursorX + 6} y={height - 9} className="axis-label">
          {activeTime.toFixed(2)}s
        </text>
        <text x={width - padding.right - 42} y={height - 9} className="axis-label">
          {maxTime.toFixed(1)}s
        </text>
        {!multiAxis && (
          <>
            <text x={9} y={padding.top + 8} className="axis-label">
              {formatAxisValue(sharedScale.max)}
            </text>
            <text x={9} y={height - padding.bottom} className="axis-label">
              {formatAxisValue(sharedScale.min)}
            </text>
          </>
        )}
        {multiAxis && visibleChannels.map((channel, index) => {
          const scale = scaleFor(channel);
          const x = width - padding.right + 8;
          const y = padding.top + 12 + index * 18;
          return (
            <g key={`axis-${channel}`}>
              <text x={x} y={y} className="axis-label" fill={COLORS[index % COLORS.length]}>
                {formatAxisValue(scale.max)}
              </text>
              <text x={x} y={y + 10} className="axis-label" fill={COLORS[index % COLORS.length]}>
                {formatAxisValue(scale.min)}
              </text>
            </g>
          );
        })}
        {!hasRenderableValues && (
          <text x={width / 2 - 58} y={height / 2} className="axis-label">
            No numeric telemetry
          </text>
        )}
      </svg>
    </section>
  );
}

export type { OperationsTelemetryChartProps };
