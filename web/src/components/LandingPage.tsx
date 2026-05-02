import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getRuns, getTelemetry } from "../api";
import type { ReplayHandoff, RunSummary, TelemetryRow, TelemetrySeries } from "../types";
import { ReplayScene } from "./ReplayScene";

type LandingPageProps = {
  mode?: "idle" | "returning";
  onEnter: (handoff?: ReplayHandoff) => void;
  onReturnComplete?: () => void;
};

export function LandingPage({ mode = "idle", onEnter, onReturnComplete }: LandingPageProps) {
  const rootRef = useRef<HTMLElement | null>(null);
  const sceneRef = useRef<HTMLElement | null>(null);
  const screenRef = useRef<HTMLSpanElement | null>(null);
  const previewRunRef = useRef<RunSummary | null>(null);
  const previewTelemetryRef = useRef<TelemetrySeries | null>(null);
  const previewIndexRef = useRef(0);
  const [entering, setEntering] = useState(false);
  const [previewRun, setPreviewRun] = useState<RunSummary | null>(null);
  const [previewTelemetry, setPreviewTelemetry] = useState<TelemetrySeries | null>(null);
  const [previewRows, setPreviewRows] = useState<TelemetryRow[]>([]);
  const [previewIndex, setPreviewIndex] = useState(0);
  const returning = mode === "returning";
  const previewReady = Boolean(previewTelemetry?.history.length);

  const syncZoomTarget = () => {
    const root = rootRef.current;
    const screen = screenRef.current;
    if (!root || !screen) {
      return;
    }
    const rect = screen.getBoundingClientRect();
    const centerX = rect.left + rect.width * 0.5;
    const centerY = rect.top + rect.height * 0.5;
    const scale = Math.min(
      8.4,
      Math.max(4.2, window.innerWidth / Math.max(rect.width, 1) * 1.16, window.innerHeight / Math.max(rect.height, 1) * 1.12)
    );
    const tx = window.innerWidth * 0.5 - centerX * scale;
    const ty = window.innerHeight * 0.5 - centerY * scale;
    root.style.setProperty("--zoom-scale", scale.toFixed(4));
    root.style.setProperty("--zoom-tx", `${tx.toFixed(1)}px`);
    root.style.setProperty("--zoom-ty", `${ty.toFixed(1)}px`);
    const transform = `translate(${tx.toFixed(1)}px, ${ty.toFixed(1)}px) scale(${scale.toFixed(4)})`;
    root.style.setProperty("--zoom-transform", transform);
    return transform;
  };

  useLayoutEffect(() => {
    syncZoomTarget();
    window.addEventListener("resize", syncZoomTarget);
    return () => window.removeEventListener("resize", syncZoomTarget);
  }, []);

  useEffect(() => {
    let mounted = true;
    let retryTimer: number | undefined;

    const loadPreview = () => {
      let selectedRun: RunSummary | null = null;
      getRuns()
        .then((runs) => {
          const previewRun = runs.find((run) => run.id.includes("nominal_ascent")) ?? runs.find((run) => run.id.startsWith("web_runs~")) ?? runs[0];
          if (!previewRun) {
            return null;
          }
          selectedRun = previewRun;
          return getTelemetry(previewRun.id, 3);
        })
        .then((series) => {
          if (!mounted) {
            return;
          }
          if (series?.history.length) {
            previewRunRef.current = selectedRun;
            previewTelemetryRef.current = series;
            setPreviewRun(selectedRun);
            setPreviewTelemetry(series);
            setPreviewRows(series.history);
            setPreviewIndex((index) => Math.min(index, series.history.length - 1));
            return;
          }
          retryTimer = window.setTimeout(loadPreview, 1800);
        })
        .catch(() => {
          if (mounted) {
            previewRunRef.current = null;
            previewTelemetryRef.current = null;
            setPreviewRun(null);
            setPreviewTelemetry(null);
            setPreviewRows([]);
            retryTimer = window.setTimeout(loadPreview, 1800);
          }
        });
    };

    loadPreview();
    return () => {
      mounted = false;
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, []);

  useEffect(() => {
    if (!previewRows.length || returning) {
      return;
    }
    const timer = window.setInterval(() => {
      setPreviewIndex((index) => {
        const next = index + 1 >= previewRows.length ? 0 : index + 1;
        previewIndexRef.current = next;
        return next;
      });
    }, 120);
    return () => window.clearInterval(timer);
  }, [previewRows.length, returning]);

  useEffect(() => {
    previewRunRef.current = previewRun;
  }, [previewRun]);

  useEffect(() => {
    previewTelemetryRef.current = previewTelemetry;
  }, [previewTelemetry]);

  useEffect(() => {
    previewIndexRef.current = previewIndex;
  }, [previewIndex]);

  useEffect(() => {
    if (!returning) {
      return;
    }
    const transform = syncZoomTarget();
    const scene = sceneRef.current;
    let reverseTimer: number | undefined;
    if (scene && transform) {
      scene.style.transition = "none";
      scene.style.transform = transform;
      scene.getBoundingClientRect();
      reverseTimer = window.setTimeout(() => {
        scene.style.transition = "";
        scene.style.transform = "translate(0, 0) scale(1)";
      }, 30);
    }
    const timer = window.setTimeout(() => onReturnComplete?.(), 1420);
    return () => {
      if (reverseTimer !== undefined) {
        window.clearTimeout(reverseTimer);
      }
      window.clearTimeout(timer);
    };
  }, [onReturnComplete, returning]);

  const enter = () => {
    if (entering || returning || !previewReady) {
      return;
    }
    const transform = syncZoomTarget();
    if (sceneRef.current && transform) {
      sceneRef.current.style.transform = transform;
    }
    setEntering(true);
    window.setTimeout(() => {
      const telemetry = previewTelemetryRef.current;
      const handoff = telemetry?.history.length
        ? {
            runId: telemetry.run_id,
            run: previewRunRef.current,
            telemetry,
            index: Math.min(previewIndexRef.current, telemetry.history.length - 1),
            environmentMode: "night" as const,
            cameraMode: "chase" as const,
            playing: true
          }
        : undefined;
      onEnter(handoff);
    }, 1450);
  };

  return (
    <main ref={rootRef} className={`mercury-intro ${entering ? "entering" : ""} ${returning ? "returning" : ""}`}>
      <nav className="intro-nav" aria-label="Intro">
        <span>AeroSim 6DOF</span>
        <button onClick={enter} disabled={returning || !previewReady}>Open simulator</button>
      </nav>

      <section ref={sceneRef} className="observatory-scene" aria-label="Mountain top command center">
        <div className="sky-layer" aria-hidden="true" />
        <div className="mountain-range far" aria-hidden="true" />
        <div className="mountain-range near" aria-hidden="true" />
        <div className="glass-wall" aria-hidden="true" />
        <div className="floor-grid" aria-hidden="true" />

        <button className="command-console" onClick={enter} disabled={returning || !previewReady} aria-label="Enter AeroSim 6DOF simulator">
          <span className="monitor-stand" aria-hidden="true" />
          <span className="monitor-shell">
            <span ref={screenRef} className="monitor-screen">
              <span className="screen-preview" aria-hidden="true">
                {previewRows.length ? (
                  <ReplayScene
                    rows={previewRows}
                    currentIndex={previewIndex}
                    environmentMode="night"
                    cameraMode="chase"
                    showTrail={false}
                    showAxes={false}
                    showWind={false}
                    compact
                  />
                ) : (
                  <>
                    <span className="screen-path" />
                    <span className="screen-horizon" />
                  </>
                )}
              </span>
              <span className="screen-kicker">LIVE 6DOF</span>
              <span className="screen-status">{previewReady ? "READY" : "SYNCING"}</span>
            </span>
          </span>
        </button>

        <div className="intro-copy">
          <p>Mountain desk flight lab</p>
          <h1>AeroSim 6DOF</h1>
          <button onClick={enter} disabled={returning || !previewReady}>Enter simulation</button>
        </div>
      </section>
    </main>
  );
}
