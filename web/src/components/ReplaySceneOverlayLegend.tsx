import type { CSSProperties } from "react";
import {
  REPLAY_TRAIL_COLOR_PROFILES,
  getReplayCameraPreset,
  type ImpactContactDescriptor,
  type RangeMarkerDescriptor,
  type ReplayCameraPresetId,
  type ReplayTrailColorMode,
  type ReplayVectorOverlayDescriptor,
  type SensorConeDescriptor,
  type TrailColorDescriptor,
  type TrailColorLegendStop
} from "../replayVisuals";

export type ReplaySceneOverlayLegendProps = {
  vectors?: ReplayVectorOverlayDescriptor[];
  sensorCones?: SensorConeDescriptor[];
  rangeMarkers?: RangeMarkerDescriptor[];
  contacts?: ImpactContactDescriptor[];
  trail?: TrailColorDescriptor;
  trailMode?: ReplayTrailColorMode;
  cameraMode?: ReplayCameraPresetId;
  compact?: boolean;
  className?: string;
};

type LegendItem = {
  id: string;
  label: string;
  value?: string;
  color: string;
  muted?: boolean;
};

const styles = {
  shell: {
    position: "absolute",
    right: 16,
    bottom: 16,
    zIndex: 4,
    width: "min(280px, calc(100% - 32px))",
    padding: "12px",
    border: "1px solid rgba(237, 237, 243, 0.18)",
    borderRadius: 6,
    background: "rgba(17, 17, 25, 0.78)",
    color: "#ededf3",
    backdropFilter: "blur(12px)",
    boxShadow: "0 14px 42px rgba(0, 0, 0, 0.28)",
    pointerEvents: "none"
  },
  compactShell: {
    width: "min(230px, calc(100% - 24px))",
    right: 12,
    bottom: 12,
    padding: "10px"
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 10
  },
  title: {
    margin: 0,
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "uppercase"
  },
  camera: {
    color: "#cdddff",
    fontSize: 11,
    fontWeight: 650,
    whiteSpace: "nowrap"
  },
  section: {
    display: "grid",
    gap: 6,
    marginTop: 8
  },
  sectionTitle: {
    color: "#c3c3cc",
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "uppercase"
  },
  item: {
    display: "grid",
    gridTemplateColumns: "12px minmax(0, 1fr) auto",
    alignItems: "center",
    gap: 8,
    minHeight: 20,
    fontSize: 11
  },
  swatch: {
    width: 10,
    height: 10,
    borderRadius: 2,
    boxShadow: "0 0 0 1px rgba(237, 237, 243, 0.18)"
  },
  itemLabel: {
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap"
  },
  itemValue: {
    color: "#c3c3cc",
    fontVariantNumeric: "tabular-nums",
    whiteSpace: "nowrap"
  },
  gradient: {
    height: 8,
    borderRadius: 999,
    boxShadow: "inset 0 0 0 1px rgba(237, 237, 243, 0.18)"
  },
  gradientLabels: {
    display: "flex",
    justifyContent: "space-between",
    gap: 8,
    color: "#c3c3cc",
    fontSize: 10,
    fontVariantNumeric: "tabular-nums"
  }
} satisfies Record<string, CSSProperties>;

export function ReplaySceneOverlayLegend({
  vectors = [],
  sensorCones = [],
  rangeMarkers = [],
  contacts = [],
  trail,
  trailMode = "plain",
  cameraMode = "chase",
  compact = false,
  className
}: ReplaySceneOverlayLegendProps) {
  const camera = getReplayCameraPreset(cameraMode);
  const activeVectors = vectors.filter((vector) => vector.visible);
  const activeSensors = sensorCones.filter((sensor) => sensor.visible);
  const activeRanges = rangeMarkers.filter((marker) => marker.visible).slice(0, compact ? 2 : 4);
  const activeContacts = contacts.filter((contact) => contact.visible);
  const trailStops = trail?.legendStops ?? fallbackTrailStops(trailMode);
  const trailLabel = trail?.profile.label ?? REPLAY_TRAIL_COLOR_PROFILES[trailMode].label;
  const hasOverlayItems = activeVectors.length + activeSensors.length + activeRanges.length + activeContacts.length > 0;

  return (
    <aside
      aria-label="Replay scene overlay legend"
      className={className}
      style={{ ...styles.shell, ...(compact ? styles.compactShell : undefined) }}
    >
      <div style={styles.header}>
        <h3 style={styles.title}>Scene overlays</h3>
        <span style={styles.camera}>{camera.label}</span>
      </div>

      <LegendSection
        title={`Trail: ${trailLabel}`}
        items={[]}
        beforeItems={<TrailGradient stops={trailStops} />}
      />

      {hasOverlayItems ? (
        <>
          <LegendSection title="Vectors" items={activeVectors.map(vectorItem)} />
          <LegendSection title="Sensors" items={activeSensors.map(sensorItem)} />
          <LegendSection title="Range" items={activeRanges.map(rangeItem)} />
          <LegendSection title="Contact" items={activeContacts.map(contactItem)} />
        </>
      ) : (
        <LegendSection
          title="Active"
          items={[
            {
              id: "none",
              label: "No optional overlays",
              color: "#70707d",
              muted: true
            }
          ]}
        />
      )}
    </aside>
  );
}

function LegendSection({ title, items, beforeItems }: { title: string; items: LegendItem[]; beforeItems?: JSX.Element }) {
  if (!beforeItems && items.length === 0) {
    return null;
  }
  return (
    <section style={styles.section}>
      <span style={styles.sectionTitle}>{title}</span>
      {beforeItems}
      {items.map((item) => (
        <div key={item.id} style={{ ...styles.item, opacity: item.muted ? 0.62 : 1 }}>
          <span style={{ ...styles.swatch, background: item.color }} />
          <span style={styles.itemLabel}>{item.label}</span>
          {item.value ? <span style={styles.itemValue}>{item.value}</span> : <span />}
        </div>
      ))}
    </section>
  );
}

function TrailGradient({ stops }: { stops: TrailColorLegendStop[] }) {
  const gradient = `linear-gradient(90deg, ${stops.map((stop) => `${stop.color} ${Math.round(stop.ratio * 100)}%`).join(", ")})`;
  return (
    <div>
      <div style={{ ...styles.gradient, background: gradient }} />
      <div style={styles.gradientLabels}>
        <span>{stops[0]?.label ?? ""}</span>
        <span>{stops[Math.floor(stops.length / 2)]?.label ?? ""}</span>
        <span>{stops[stops.length - 1]?.label ?? ""}</span>
      </div>
    </div>
  );
}

function vectorItem(vector: ReplayVectorOverlayDescriptor): LegendItem {
  return {
    id: vector.id,
    label: vector.label,
    value: vector.valueLabel,
    color: vector.color
  };
}

function sensorItem(sensor: SensorConeDescriptor): LegendItem {
  return {
    id: sensor.id,
    label: sensor.label,
    value: sensor.statusLabel,
    color: sensor.color,
    muted: !sensor.sensorValid
  };
}

function rangeItem(marker: RangeMarkerDescriptor): LegendItem {
  return {
    id: marker.id,
    label: marker.label,
    value: marker.metricLabel,
    color: marker.color
  };
}

function contactItem(contact: ImpactContactDescriptor): LegendItem {
  return {
    id: contact.id,
    label: contact.label,
    value: contact.clearanceM === null ? undefined : `${contact.clearanceM.toFixed(1)} m`,
    color: contact.color
  };
}

function fallbackTrailStops(mode: ReplayTrailColorMode): TrailColorLegendStop[] {
  const profile = REPLAY_TRAIL_COLOR_PROFILES[mode];
  const colors = profile.colors.length === 2 ? [profile.colors[0], profile.colors[0], profile.colors[1]] : profile.colors;
  return [
    { ratio: 0, color: colors[0], label: "low" },
    { ratio: 0.5, color: colors[1], label: "mid" },
    { ratio: 1, color: colors[2], label: "high" }
  ];
}
