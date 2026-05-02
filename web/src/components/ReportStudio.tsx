import { Bell, Check, Clock, Download, FileJson, FolderOpen, Gauge, Radar, Square } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  DEFAULT_REPORT_STUDIO_SECTIONS,
  REPORT_STUDIO_SECTION_DEFINITIONS,
  availableReportStudioTelemetryChannels,
  buildReportStudioReportSummary,
  buildReportStudioExportPayload,
  buildReportStudioExportRequest,
  defaultReportStudioSections,
  defaultReportStudioTelemetryChannels,
  describeReportStudioSections,
  normalizeReportStudioTelemetryChannels,
  normalizeReportStudioSections,
  type ReportStudioExportFormat,
  type ReportStudioExportPayload,
  type ReportStudioExportRequest,
  type ReportStudioPacket,
  type ReportStudioReadySummary,
  type ReportStudioSectionDescription,
  type ReportStudioSectionId
} from "../reportStudio";

type ReportStudioProps = {
  packet?: ReportStudioPacket | null;
  selectedSections?: ReportStudioSectionId[];
  selectedTelemetryChannels?: string[];
  exportFormat?: ReportStudioExportFormat;
  onSelectionChange?: (sections: ReportStudioSectionId[]) => void;
  onTelemetryChannelsChange?: (channels: string[]) => void;
  onExportFormatChange?: (format: ReportStudioExportFormat) => void;
  onExportRequest?: (request: ReportStudioExportRequest, payload: ReportStudioExportPayload | null) => void;
  onPayloadReady?: (
    request: ReportStudioExportRequest,
    payload: ReportStudioExportPayload | null,
    summary: ReportStudioReadySummary
  ) => void;
};

const SECTION_ICONS: Record<ReportStudioSectionId, ReactNode> = {
  summary: <FileJson size={16} />,
  events: <Clock size={16} />,
  alarms: <Bell size={16} />,
  telemetry: <Gauge size={16} />,
  engagement: <Radar size={16} />,
  artifacts: <FolderOpen size={16} />
};

const EXPORT_FORMATS: ReportStudioExportFormat[] = ["json", "markdown", "html"];

export function ReportStudio({
  packet,
  selectedSections,
  selectedTelemetryChannels,
  exportFormat,
  onSelectionChange,
  onTelemetryChannelsChange,
  onExportFormatChange,
  onExportRequest,
  onPayloadReady
}: ReportStudioProps) {
  const packetDefaults = useMemo(() => defaultReportStudioSections(packet), [packet]);
  const telemetryDefaults = useMemo(() => defaultReportStudioTelemetryChannels(packet), [packet]);
  const [localSections, setLocalSections] = useState<ReportStudioSectionId[]>(packetDefaults);
  const [localTelemetryChannels, setLocalTelemetryChannels] = useState<string[]>(telemetryDefaults);
  const [localFormat, setLocalFormat] = useState<ReportStudioExportFormat>(exportFormat ?? "json");

  useEffect(() => {
    if (!selectedSections) {
      setLocalSections(packetDefaults);
    }
  }, [packetDefaults, selectedSections]);

  useEffect(() => {
    if (!selectedTelemetryChannels) {
      setLocalTelemetryChannels(telemetryDefaults);
    }
  }, [telemetryDefaults, selectedTelemetryChannels]);

  useEffect(() => {
    if (exportFormat) {
      setLocalFormat(exportFormat);
    }
  }, [exportFormat]);

  const activeSections = normalizeReportStudioSections(selectedSections ?? localSections, DEFAULT_REPORT_STUDIO_SECTIONS);
  const activeTelemetryChannels = normalizeReportStudioTelemetryChannels(
    selectedTelemetryChannels ?? localTelemetryChannels,
    packet
  );
  const activeFormat = exportFormat ?? localFormat;
  const availableTelemetryChannels = useMemo(() => availableReportStudioTelemetryChannels(packet), [packet]);
  const sectionDescriptions = useMemo(
    () => describeReportStudioSections(packet, activeSections),
    [packet, activeSections]
  );
  const selectedDescriptions = sectionDescriptions.filter((section) => section.included);
  const request = useMemo(
    () =>
      buildReportStudioExportRequest({
        packet,
        sections: activeSections,
        telemetryChannels: activeTelemetryChannels,
        format: activeFormat
      }),
    [packet, activeSections, activeTelemetryChannels, activeFormat]
  );
  const exportPayload = useMemo(
    () => (packet ? buildReportStudioExportPayload(packet, request) : null),
    [packet, request]
  );
  const reportSummary = useMemo(
    () => buildReportStudioReportSummary(packet, activeSections, activeTelemetryChannels),
    [packet, activeSections, activeTelemetryChannels]
  );

  useEffect(() => {
    onPayloadReady?.(request, exportPayload, reportSummary);
  }, [request, exportPayload, reportSummary, onPayloadReady]);

  function updateSections(nextSections: ReportStudioSectionId[]) {
    const normalized = normalizeReportStudioSections(nextSections, DEFAULT_REPORT_STUDIO_SECTIONS);
    if (!selectedSections) {
      setLocalSections(normalized);
    }
    onSelectionChange?.(normalized);
  }

  function updateTelemetryChannels(nextChannels: string[]) {
    const normalized = normalizeReportStudioTelemetryChannels(nextChannels, packet);
    if (!selectedTelemetryChannels) {
      setLocalTelemetryChannels(normalized);
    }
    onTelemetryChannelsChange?.(normalized);
  }

  function toggleSection(section: ReportStudioSectionId) {
    const selected = new Set(activeSections);
    if (selected.has(section)) {
      if (selected.size === 1) {
        return;
      }
      selected.delete(section);
    } else {
      selected.add(section);
    }
    updateSections(REPORT_STUDIO_SECTION_DEFINITIONS.map((definition) => definition.id).filter((id) => selected.has(id)));
  }

  function changeFormat(format: ReportStudioExportFormat) {
    if (!exportFormat) {
      setLocalFormat(format);
    }
    onExportFormatChange?.(format);
  }

  function toggleTelemetryChannel(channelId: string) {
    const selected = new Set(activeTelemetryChannels);
    if (selected.has(channelId)) {
      if (selected.size === 1) {
        return;
      }
      selected.delete(channelId);
    } else {
      selected.add(channelId);
    }
    updateTelemetryChannels(availableTelemetryChannels.map((channel) => channel.id).filter((id) => selected.has(id)));
  }

  function requestExport() {
    onExportRequest?.(request, exportPayload);
  }

  return (
    <section className="report-studio" aria-label="Report Studio">
      <header className="report-studio-header">
        <div>
          <span>Report Studio</span>
          <h2>{packet?.summary?.data.scenario ? String(packet.summary.data.scenario) : packet?.packet_id ?? "No packet loaded"}</h2>
        </div>
        <div className="report-studio-actions">
          <select
            aria-label="Export format"
            value={activeFormat}
            onChange={(event) => changeFormat(event.target.value as ReportStudioExportFormat)}
          >
            {EXPORT_FORMATS.map((format) => (
              <option value={format} key={format}>
                {format.toUpperCase()}
              </option>
            ))}
          </select>
          <button type="button" onClick={requestExport} disabled={!packet}>
            <Download size={16} />
            Export
          </button>
        </div>
      </header>

      <div className="report-studio-grid">
        <section className="report-studio-section-picker" aria-label="Packet sections">
          <ReportStudioSummaryCard summary={reportSummary} />
          {sectionDescriptions.map((section) => (
            <button
              type="button"
              className={`report-studio-section ${section.included ? "selected" : ""}`}
              aria-pressed={section.included}
              key={section.id}
              onClick={() => toggleSection(section.id)}
            >
              <span className="report-studio-section-icon">{SECTION_ICONS[section.id]}</span>
              <span>
                <strong>{section.label}</strong>
                <small>{section.summary}</small>
              </span>
              {section.included ? <Check size={16} /> : <Square size={16} />}
            </button>
          ))}
          {availableTelemetryChannels.length > 0 && activeSections.includes("telemetry") ? (
            <div className="report-studio-card">
              <div>
                <span>channels</span>
                <strong>Telemetry Selection</strong>
              </div>
              {availableTelemetryChannels.map((channel) => (
                <button
                  type="button"
                  className={`report-studio-section ${activeTelemetryChannels.includes(channel.id) ? "selected" : ""}`}
                  aria-pressed={activeTelemetryChannels.includes(channel.id)}
                  key={channel.id}
                  onClick={() => toggleTelemetryChannel(channel.id)}
                >
                  <span className="report-studio-section-icon">
                    <Gauge size={16} />
                  </span>
                  <span>
                    <strong>{channel.label}</strong>
                    <small>
                      {channel.source}.{channel.channel}
                      {channel.unit ? ` (${channel.unit})` : ""}
                    </small>
                  </span>
                  {activeTelemetryChannels.includes(channel.id) ? <Check size={16} /> : <Square size={16} />}
                </button>
              ))}
            </div>
          ) : null}
        </section>

        <section className="report-studio-preview" aria-label="Selected packet sections">
          <div className="report-studio-preview-head">
            <h3>Selected Sections</h3>
            <span>{selectedDescriptions.length}</span>
          </div>
          <div className="report-studio-section-list">
            {selectedDescriptions.map((section) => (
              <ReportStudioSectionCard section={section} key={section.id} />
            ))}
          </div>
        </section>

        <section className="report-studio-payload" aria-label="Ready export payload">
          <div className="report-studio-preview-head">
            <h3>Ready Payload</h3>
            <span>{activeFormat}</span>
          </div>
          <pre>{JSON.stringify(exportPayload ?? request, null, 2)}</pre>
        </section>
      </div>
    </section>
  );
}

function ReportStudioSummaryCard({ summary }: { summary: ReportStudioReadySummary }) {
  return (
    <article className={`report-studio-card ${summary.ready ? "" : "muted"}`}>
      <div>
        <span>{summary.ready ? "ready" : "waiting"}</span>
        <strong>{summary.title}</strong>
      </div>
      <p>{summary.subtitle}</p>
      <dl>
        <div>
          <dt>Sections</dt>
          <dd>
            {summary.available_section_count}/{summary.section_count}
          </dd>
        </div>
        <div>
          <dt>Channels</dt>
          <dd>{summary.telemetry_channel_count}</dd>
        </div>
      </dl>
    </article>
  );
}

function ReportStudioSectionCard({ section }: { section: ReportStudioSectionDescription }) {
  return (
    <article className={`report-studio-card ${section.available ? "" : "muted"}`}>
      <div>
        <span>{section.available ? "available" : "missing"}</span>
        <strong>{section.label}</strong>
      </div>
      <p>{section.description}</p>
      <dl>
        <div>
          <dt>Payload</dt>
          <dd>{String(section.payloadKey)}</dd>
        </div>
        <div>
          <dt>Items</dt>
          <dd>{section.itemCount}</dd>
        </div>
      </dl>
    </article>
  );
}
