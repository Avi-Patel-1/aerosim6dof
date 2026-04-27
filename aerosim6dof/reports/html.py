"""HTML report writer."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def write_report(out_dir: str | Path, summary: dict[str, Any], events: list[dict[str, Any]], plot_files: list[Path]) -> Path:
    out = Path(out_dir)
    rows = "\n".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(_fmt(v))}</td></tr>"
        for k, v in summary.items()
        if k != "final"
    )
    event_items = "\n".join(
        f"<li><strong>{html.escape(str(e.get('type', 'event')))}</strong> at {float(e.get('time_s', 0.0)):.3f} s - {html.escape(str(e.get('description', '')))}</li>"
        for e in events
    ) or "<li>No threshold events recorded.</li>"
    plot_html = "\n".join(
        f'<figure><img src="{html.escape(str(p.relative_to(out)))}" alt="{html.escape(p.stem)}"><figcaption>{html.escape(p.stem.replace("_", " "))}</figcaption></figure>'
        for p in plot_files
    )
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(str(summary.get("scenario", "run")))} report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; background: #f7f8fa; }}
    main {{ max-width: 1120px; margin: 0 auto; }}
    h1, h2 {{ margin-bottom: 0.35rem; }}
    table {{ border-collapse: collapse; background: white; margin: 18px 0; min-width: 420px; }}
    th, td {{ border: 1px solid #d9dee7; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef2f7; }}
    figure {{ background: white; border: 1px solid #d9dee7; margin: 18px 0; padding: 12px; }}
    img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ font-size: 12px; color: #52616f; margin-top: 8px; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(str(summary.get("scenario", "run")))} Flight Report</h1>
  <p>Generated from simulator truth, control, sensor, and event logs.</p>
  <h2>Summary</h2>
  <table>{rows}</table>
  <h2>Events</h2>
  <ul>{event_items}</ul>
  <h2>Plots</h2>
  {plot_html}
</main>
</body>
</html>
"""
    path = out / "report.html"
    path.write_text(doc)
    return path


def write_batch_report(out_dir: str | Path, batch_summary: dict[str, Any], filename: str = "batch_report.html") -> Path:
    out = Path(out_dir)
    runs = list(batch_summary.get("runs", []))
    rows = "\n".join(_batch_row(out, run) for run in runs) or "<tr><td colspan=\"8\">No runs found.</td></tr>"
    count = int(batch_summary.get("count", len(runs)))
    max_alt = _best(runs, "max_altitude_m")
    max_speed = _best(runs, "max_speed_mps")
    worst_load = _best(runs, "max_load_factor_g")
    is_monte_carlo = batch_summary.get("kind") == "monte_carlo" or "monte_carlo" in filename
    title = "Monte Carlo Flight Report" if is_monte_carlo else "Batch Flight Report"
    description = "Aggregate summary across dispersed scenario samples." if is_monte_carlo else "Aggregate summary across scenario runs."
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; background: #f7f8fa; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 18px 0; }}
    .card {{ background: white; border: 1px solid #d9dee7; padding: 14px; }}
    .metric {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin-top: 18px; }}
    th, td {{ border: 1px solid #d9dee7; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef2f7; }}
    a {{ color: #0f62fe; text-decoration: none; }}
  </style>
</head>
<body>
<main>
  <h1>{title}</h1>
  <p>{description}</p>
  <section class="cards">
    <div class="card"><div>Runs</div><div class="metric">{count}</div></div>
    <div class="card"><div>Highest altitude</div><div class="metric">{_fmt(max_alt)} m</div></div>
    <div class="card"><div>Highest speed</div><div class="metric">{_fmt(max_speed)} m/s</div></div>
    <div class="card"><div>Highest load</div><div class="metric">{_fmt(worst_load)} g</div></div>
  </section>
  <table>
    <thead>
      <tr>
        <th>Scenario</th><th>Duration (s)</th><th>Final altitude (m)</th><th>Max altitude (m)</th>
        <th>Max speed (m/s)</th><th>Max load (g)</th><th>Events</th><th>Report</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</main>
</body>
</html>
"""
    path = out / filename
    path.write_text(doc)
    return path


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if value is None:
        return "-"
    return str(value)


def _best(runs: list[dict[str, Any]], key: str) -> float | None:
    values = [float(run[key]) for run in runs if key in run and isinstance(run[key], (int, float))]
    return max(values) if values else None


def _batch_row(out: Path, run: dict[str, Any]) -> str:
    scenario = str(run.get("scenario", "run"))
    run_dir_value = run.get("run_dir")
    run_dir = Path(str(run_dir_value)) if run_dir_value else out / scenario
    if not run_dir.is_absolute():
        run_dir = out / run_dir.name if not (run_dir / "report.html").exists() else run_dir
    report_path = run_dir / "report.html"
    if report_path.exists():
        try:
            href = str(report_path.relative_to(out))
        except ValueError:
            href = str(report_path)
        link = f'<a href="{html.escape(href)}">open</a>'
    else:
        link = "-"
    final = run.get("final", {}) if isinstance(run.get("final"), dict) else {}
    return (
        "<tr>"
        f"<td>{html.escape(scenario)}</td>"
        f"<td>{html.escape(_fmt(run.get('duration_s')))}</td>"
        f"<td>{html.escape(_fmt(final.get('altitude_m')))}</td>"
        f"<td>{html.escape(_fmt(run.get('max_altitude_m')))}</td>"
        f"<td>{html.escape(_fmt(run.get('max_speed_mps')))}</td>"
        f"<td>{html.escape(_fmt(run.get('max_load_factor_g')))}</td>"
        f"<td>{html.escape(_fmt(run.get('event_count')))}</td>"
        f"<td>{link}</td>"
        "</tr>"
    )
