import { channelLabelWithUnit } from "../telemetry";
import type { TelemetryChannelMetadata, TelemetryRange, TelemetryRow } from "../types";

type TelemetryChartProps = {
  title: string;
  rows: TelemetryRow[];
  channels: string[];
  currentIndex: number;
  metadata?: Record<string, TelemetryChannelMetadata>;
};

const COLORS = ["#ededf3", "#cdddff", "#c3c3cc", "#9aa0b8", "#70707d", "#b7bed8"];

function asNumber(value: TelemetryRow[string]): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function rangeLines(metadata: TelemetryChannelMetadata | undefined): { value: number; className: string; label: string }[] {
  if (!metadata) {
    return [];
  }
  const collect = (range: TelemetryRange | null | undefined, className: string, fallback: string) => {
    if (!range) {
      return [];
    }
    const label = range.label || fallback;
    return [range.min, range.max]
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
      .map((value) => ({ value, className, label }));
  };
  return [
    ...collect(metadata.caution_range, "limit-line caution", "caution"),
    ...collect(metadata.warning_range, "limit-line warning", "warning"),
    ...collect(metadata.fatal_range, "limit-line fatal", "fatal")
  ];
}

export function TelemetryChart({ title, rows, channels, currentIndex, metadata }: TelemetryChartProps) {
  const width = 720;
  const height = 178;
  const padding = { top: 18, right: 18, bottom: 24, left: 42 };
  const usableWidth = width - padding.left - padding.right;
  const usableHeight = height - padding.top - padding.bottom;
  const times = rows.map((row) => asNumber(row.time_s)).filter((value): value is number => value !== null);
  const minTime = times.length ? Math.min(...times) : 0;
  const maxTime = times.length ? Math.max(...times) : 1;
  const values = channels.flatMap((channel) =>
    rows.map((row) => asNumber(row[channel])).filter((value): value is number => value !== null)
  );
  const minValue = values.length ? Math.min(...values) : 0;
  const maxValue = values.length ? Math.max(...values) : 1;
  const spanValue = maxValue - minValue || 1;
  const spanTime = maxTime - minTime || 1;
  const currentTime = asNumber(rows[currentIndex]?.time_s) ?? minTime;
  const currentX = padding.left + ((currentTime - minTime) / spanTime) * usableWidth;
  const activeLimits = channels.length === 1 ? rangeLines(metadata?.[channels[0]]).filter((line) => line.value >= minValue && line.value <= maxValue) : [];

  const pointFor = (row: TelemetryRow, channel: string) => {
    const time = asNumber(row.time_s);
    const value = asNumber(row[channel]);
    if (time === null || value === null) {
      return null;
    }
    const x = padding.left + ((time - minTime) / spanTime) * usableWidth;
    const y = padding.top + usableHeight - ((value - minValue) / spanValue) * usableHeight;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  };

  return (
    <section className="chart-panel">
      <div className="chart-header">
        <h3>{title}</h3>
        <div className="legend">
          {channels.map((channel, index) => (
            <span key={channel}>
              <i style={{ background: COLORS[index % COLORS.length] }} />
              {channelLabelWithUnit(metadata, channel)}
            </span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        <rect x="0" y="0" width={width} height={height} rx="0" className="chart-bg" />
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="axis" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} className="axis" />
        {[0.25, 0.5, 0.75].map((ratio) => {
          const y = padding.top + usableHeight * ratio;
          return <line key={ratio} x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="grid-line" />;
        })}
        {activeLimits.map((line, index) => {
          const y = padding.top + usableHeight - ((line.value - minValue) / spanValue) * usableHeight;
          return (
            <g key={`${line.className}-${line.value}-${index}`}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} className={line.className} />
              <text x={width - padding.right - 96} y={y - 4} className="limit-label">
                {line.label}
              </text>
            </g>
          );
        })}
        {channels.map((channel, index) => {
          const points = rows
            .map((row) => pointFor(row, channel))
            .filter((point): point is string => point !== null)
            .join(" ");
          return <polyline key={channel} points={points} fill="none" stroke={COLORS[index % COLORS.length]} strokeWidth="2.4" />;
        })}
        <line x1={currentX} y1={padding.top} x2={currentX} y2={height - padding.bottom} className="cursor-line" />
        <text x={padding.left} y={height - 7} className="axis-label">
          {minTime.toFixed(1)}s
        </text>
        <text x={width - padding.right - 40} y={height - 7} className="axis-label">
          {maxTime.toFixed(1)}s
        </text>
        <text x={8} y={padding.top + 8} className="axis-label">
          {maxValue.toFixed(1)}
        </text>
        <text x={8} y={height - padding.bottom} className="axis-label">
          {minValue.toFixed(1)}
        </text>
      </svg>
    </section>
  );
}
