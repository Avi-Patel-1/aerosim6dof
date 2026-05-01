# Mercury Design Implementation Checklist

Source of truth: `docs/DESIGN.md`

## Implementation Notes

- [done] The Mercury design reference is tracked in `docs/DESIGN.md`.
- [done] Color, spacing, radius, surface, and typography tokens are centralized in the frontend stylesheet and token module.
- [done] The landing page uses the mountain command-center direction with a live simulator preview inside the monitor.
- [done] Enter and return animations use the monitor screen as the measured transition target.
- [done] The workbench keeps the dark, spacious Mercury surface treatment while exposing the full simulator workflow.
- [done] Replay scene ground reference is aligned so low-altitude frames read more consistently against terrain.
- [done] Responsive behavior is documented against the design system below.

## Screens

| Screen | Required Design | Status | Implemented In |
|---|---|---:|---|
| Landing / Hero | Full-viewport mountain-top command center, centered display title, minimal text, pill CTA, semi-transparent nav, deep neutral palette. | done | `web/src/components/LandingPage.tsx`, `web/src/styles.css` |
| Landing monitor preview | Monitor contains a small live window of the simulator so the zoom target is the actual product surface. | done | `web/src/components/LandingPage.tsx`, `web/src/components/ReplayScene.tsx`, `web/src/styles.css` |
| Enter transition | Smooth measured zoom into monitor screen; no center-screen zoom. | done | `web/src/components/LandingPage.tsx`, `web/src/styles.css` |
| Return transition | Home button reverses out of the monitor/computer view. | done | `web/src/components/LandingPage.tsx`, `web/src/styles.css` |
| Replay simulator | Simulator-first surface with large Three.js canvas, spacious controls, telemetry below, no dense dashboard hero copy. | done | `web/src/components/Workbench.tsx`, `web/src/components/ReplayScene.tsx`, `web/src/styles.css` |
| Launch tools | Existing CLI-backed run/validate/compare/report controls are exposed through spacious action sections. | done | `web/src/components/Workbench.tsx`, `web/src/styles.css` |
| Campaigns | Monte Carlo, sweeps, and fault-campaign workflows exist as dedicated action sections. | done | `web/src/components/Workbench.tsx`, `web/src/styles.css` |
| Engineering | Trim, linearization, stability, and analysis workflows exist as dedicated sections. | done | `web/src/components/Workbench.tsx`, `web/src/styles.css` |
| Models | Scenarios, vehicles, environments, and capabilities are inspectable. | done | `web/src/components/Workbench.tsx`, `web/src/styles.css` |
| Editor | Guided scenario editing and guarded JSON editing exist. | done | `web/src/components/Workbench.tsx`, `web/src/styles.css` |
| Reports | Job history, result output, reports, plots, CSV, JSON artifacts exist. | done | `web/src/components/Workbench.tsx`, `web/src/styles.css` |

## Sections And Components

| Item | Required Design | Status | Implemented In |
|---|---|---:|---|
| Typography | Arcadia-style font stack, light display weights, no heavy headings. | done | `web/src/styles.css` |
| Colors | Mercury Blue only for primary actions; deep-space/midnight backgrounds; starlight/silver text. | done | `web/src/styles.css` |
| Spacing | 4px scale, spacious vertical rhythm, no dense card grid on landing. | done | `web/src/styles.css` |
| Buttons | Primary pill, header pill, ghost nav link, segmented pills. | done | `web/src/styles.css` |
| Cards / panels | Radius 0 for content panels, radius 4 for containers, no shadow elevation. | done | `web/src/styles.css` |
| Badges / status | Graphite or ghost-blue translucent status pills. | done | `web/src/styles.css` |
| Navigation | Minimal sticky transparent workbench nav and minimal landing nav. | done | `web/src/components/LandingPage.tsx`, `web/src/components/Workbench.tsx`, `web/src/styles.css` |
| Simulator controls | Environment, camera, playback, trail/axes/wind toggles. | done | `web/src/components/Workbench.tsx`, `web/src/styles.css` |
| Telemetry charts | Stark dark SVG chart with light axis/grid and channel chips. | done | `web/src/components/TelemetryChart.tsx`, `web/src/styles.css` |
| Animation | Monitor-targeted zoom, reverse home transition, subtle screen pulse. | done | `web/src/components/LandingPage.tsx`, `web/src/styles.css` |
| Responsive | Mobile layout stacks header, tabs, replay controls, and canvas. | done | `web/src/styles.css` |

## Remaining TODOs

- [missing] Replace CSS-generated mountain scene with a true full-bleed atmospheric photograph if a final approved image asset is provided. Current implementation uses CSS-built scenery to avoid shipping an unapproved placeholder photo.
