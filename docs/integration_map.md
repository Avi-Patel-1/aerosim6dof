# AeroLab Integration Map

AeroLab is the browser surface for the existing simulation, campaign, trade-space,
and estimation tooling. The Python command-line tools remain the source of truth:
the web app runs or reads the same scenario configs, output directories, CSVs,
JSON summaries, SVG plots, and HTML reports.

## Browser Surfaces

| Surface | What it answers | Backend source | Primary artifacts |
| --- | --- | --- | --- |
| Replay | What happened during this run? | `aerosim6dof.simulation`, run index, telemetry API | `history.csv`, `truth.csv`, `controls.csv`, `sensors.csv`, `events.json` |
| Telemetry | Which subsystem caused the behavior? | telemetry metadata, alarms, run CSVs, report packet data | selected-channel exports, report packet telemetry sections |
| Estimation | How did truth, sensors, and estimates differ? | navigation endpoint and estimation/fusion report pipeline | `estimation_summary.json`, `residuals.csv`, `estimation_metrics.csv`, `estimation_report.html` |
| Engagement | How did target/interceptor geometry evolve? | target/interceptor CSVs, engagement reports, missile comparison packet | `targets.csv`, `interceptors.csv`, `engagement_report.html`, comparison summaries |
| Launch | Can this scenario run, compare, and report cleanly? | FastAPI action/job routes over existing CLI analysis functions | new run directories, compare reports, sensor reports, engagement reports |
| Campaigns | How robust is this scenario across many runs? | batch, Monte Carlo, sweep, and fault-campaign runners | campaign indexes, summaries, reports, and generated run directories |
| Trade Space | Which candidate settings rank best? | trade-space analysis primitives adapted from the Monte Carlo explorer workflow | ranking, Pareto, reliability, UQ, sensitivity, surrogate, and optimization outputs |
| Engineering | What trim, stability, and linear behavior does the model imply? | trim, trim sweep, linearization, stability, linear-model-report actions | trim JSON, sweep CSVs, linearization JSON, stability summaries, reports |
| Models | What assumptions are in the configs? | vehicle, aero, propulsion, environment, and config analysis actions | model inspection JSON, aero/propulsion/environment reports, generated scenario templates |
| Editor | How do I build a mission safely? | scenario schema, validation, examples, vehicles, environments | scenario drafts and validation advisories |
| Reports | What can I package and share? | report studio, action artifacts, job state, storage index | mission packets, HTML reports, SVG plots, CSV/JSON artifacts |

## Source Project Mapping

- `aerosim6dof` owns the 6DOF simulation runtime, CLI commands, FastAPI API,
  React workbench, replay scene, scenario editor, reports, and hosted deployment.
- `mission-tradespace-explorer` remains a standalone Monte Carlo and
  trade-space CLI toolkit. Its practical workflow is represented in AeroLab by
  the **Trade Space** and **Campaigns** tabs, where studies are driven from real
  AeroLab run outputs.
- `navfusion-lab` remains a standalone sensor-fusion and navigation sandbox.
  Its practical workflow is represented in AeroLab by the **Estimation** tab,
  where users compare truth, sensors, and fused estimates from 6DOF run outputs.

## How To Use The Unified GUI

1. Open [https://aerosim6dof.onrender.com](https://aerosim6dof.onrender.com).
2. Enter the simulator and choose a packaged or generated run.
3. Use **Replay** to inspect trajectory, targets, interceptors, events, and
   alarms.
4. Use **Telemetry** for subsystem-level channel search, pinning, comparison,
   export, and limit review.
5. Use **Estimation** for truth-vs-sensor-vs-estimate residuals and navigation
   report artifacts.
6. Use **Engagement** for target/interceptor and missile showcase comparisons.
7. Use **Campaigns** and **Trade Space** for repeatability, robustness, design
   ranking, reliability, uncertainty, and surrogate/optimization studies.
8. Use **Engineering** and **Models** to inspect trim, stability, vehicle,
   aero, propulsion, environment, and config assumptions.
9. Use **Reports** to collect HTML, SVG, CSV, JSON, job history, and mission
   packet exports.

## Preservation Guarantees

The integration is additive. Existing command-line entry points remain valid,
checked-in examples are not rewritten, and generated browser outputs are kept
under web output directories or configured storage roots. The old Monte Carlo
and sensor-fusion repositories are preserved as independent source projects.
