"""Engagement report generation for target/interceptor runs."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

from aerosim6dof.reports.csv_writer import read_csv
from aerosim6dof.reports.json_writer import write_json
from aerosim6dof.reports.svg import write_time_plot


def engagement_report(run_dir: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    run = Path(run_dir)
    out = Path(out_dir) if out_dir is not None else run
    out.mkdir(parents=True, exist_ok=True)
    history = read_csv(run / "history.csv") if (run / "history.csv").exists() else []
    targets = read_csv(run / "targets.csv") if (run / "targets.csv").exists() else []
    interceptors = read_csv(run / "interceptors.csv") if (run / "interceptors.csv").exists() else []
    target_ids = sorted({str(row.get("target_id", "")) for row in targets if row.get("target_id")})
    interceptor_ids = sorted({str(row.get("interceptor_id", "")) for row in interceptors if row.get("interceptor_id")})
    target_miss = _finite_min(row.get("target_range_m") for row in history)
    interceptor_miss = _finite_min(row.get("interceptor_range_m") for row in history)
    intercept_time = _first_time(history, "interceptor_fuzed")
    plots: list[Path] = []
    if history:
        plot_dir = out / "engagement_plots"
        range_plot = plot_dir / "engagement_ranges.svg"
        write_time_plot(range_plot, history, ["target_range_m", "interceptor_range_m"], "Engagement Ranges", "range (m)")
        plots.append(range_plot)
        closing_plot = plot_dir / "engagement_closing_speed.svg"
        write_time_plot(closing_plot, history, ["closing_speed_mps", "interceptor_closing_speed_mps"], "Closing Speeds", "closing speed (m/s)")
        plots.append(closing_plot)
    summary = {
        "target_count": len(target_ids),
        "interceptor_count": len(interceptor_ids),
        "target_ids": target_ids,
        "interceptor_ids": interceptor_ids,
        "min_target_range_m": target_miss,
        "min_interceptor_range_m": interceptor_miss,
        "first_interceptor_fuze_time_s": intercept_time,
        "plots": [str(path.relative_to(out)) for path in plots],
    }
    write_json(out / "engagement_report.json", summary)
    report_path = _write_html(out, summary, plots)
    summary["report"] = str(report_path)
    return summary


def _write_html(out: Path, summary: dict[str, Any], plots: list[Path]) -> Path:
    cards = "\n".join(
        f"<div class=\"card\"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
        for label, value in [
            ("Targets", str(summary["target_count"])),
            ("Interceptors", str(summary["interceptor_count"])),
            ("Best target range", _fmt(summary.get("min_target_range_m"), " m")),
            ("Best interceptor range", _fmt(summary.get("min_interceptor_range_m"), " m")),
            ("First fuze", _fmt(summary.get("first_interceptor_fuze_time_s"), " s")),
        ]
    )
    plot_html = "\n".join(
        f'<figure><img src="{html.escape(str(path.relative_to(out)))}" alt="{html.escape(path.stem)}"><figcaption>{html.escape(path.stem.replace("_", " "))}</figcaption></figure>'
        for path in plots
    )
    target_list = ", ".join(html.escape(item) for item in summary.get("target_ids", [])) or "-"
    interceptor_list = ", ".join(html.escape(item) for item in summary.get("interceptor_ids", [])) or "-"
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Engagement Report</title>
  <style>
    body {{ margin: 32px; font-family: Arial, sans-serif; color: #ededf3; background: #171721; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ font-weight: 400; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 22px 0; }}
    .card {{ border: 1px solid #70707d; background: #1e1e2a; padding: 14px; }}
    .card span {{ display: block; color: #c3c3cc; font-size: 12px; text-transform: uppercase; }}
    .card strong {{ display: block; margin-top: 8px; font-size: 24px; font-weight: 400; }}
    figure {{ border: 1px solid #70707d; background: #111119; padding: 12px; }}
    img {{ width: 100%; display: block; }}
    figcaption, p {{ color: #c3c3cc; }}
  </style>
</head>
<body>
<main>
  <h1>Engagement Report</h1>
  <p>Target and interceptor geometry derived from simulator output logs.</p>
  <section class="cards">{cards}</section>
  <p><strong>Targets:</strong> {target_list}</p>
  <p><strong>Interceptors:</strong> {interceptor_list}</p>
  {plot_html}
</main>
</body>
</html>
"""
    path = out / "engagement_report.html"
    path.write_text(doc)
    return path


def _finite_min(values: Any) -> float | None:
    finite: list[float] = []
    for value in values:
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            finite.append(float(value))
    return min(finite) if finite else None


def _first_time(rows: list[dict[str, Any]], key: str) -> float | None:
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)) and float(value) > 0.5 and isinstance(row.get("time_s"), (int, float)):
            return float(row["time_s"])
    return None


def _fmt(value: Any, unit: str = "") -> str:
    if isinstance(value, float) and math.isfinite(value):
        return f"{value:.3g}{unit}"
    if isinstance(value, int):
        return f"{value}{unit}"
    return "-"
