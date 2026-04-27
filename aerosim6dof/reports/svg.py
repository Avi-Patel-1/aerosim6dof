"""Dependency-free SVG plot generation."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import numpy as np


COLORS = ["#0f62fe", "#24a148", "#da1e28", "#8a3ffc", "#ff832b", "#007d79"]


def write_time_plot(
    path: str | Path,
    rows: list[dict[str, Any]],
    y_keys: list[str],
    title: str,
    y_label: str | None = None,
) -> None:
    xs = [_finite_or_none(r.get("time_s")) for r in rows]
    series = [[_finite_or_none(r.get(k)) for r in rows] for k in y_keys]
    _write_xy(path, xs, series, y_keys, title, "time (s)", y_label or ", ".join(y_keys))


def write_xy_plot(
    path: str | Path,
    rows: list[dict[str, Any]],
    x_key: str,
    y_keys: list[str],
    title: str,
    x_label: str | None = None,
    y_label: str | None = None,
) -> None:
    xs = [_finite_or_none(r.get(x_key)) for r in rows]
    series = [[_finite_or_none(r.get(k)) for r in rows] for k in y_keys]
    _write_xy(path, xs, series, y_keys, title, x_label or x_key, y_label or ", ".join(y_keys))


def _write_xy(
    path: str | Path,
    xs: list[float | None],
    series: list[list[float | None]],
    labels: list[str],
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    width, height, pad = 820, 320, 54
    if not xs or not series:
        p.write_text(_empty_svg(width, height, title))
        return
    finite_xs = [x for x in xs if x is not None]
    finite_ys = [y for ys in series for y in ys if y is not None]
    if not finite_xs or not finite_ys:
        p.write_text(_empty_svg(width, height, title))
        return
    xmin, xmax = min(finite_xs), max(finite_xs)
    ymin, ymax = min(finite_ys), max(finite_ys)
    if abs(xmax - xmin) < 1e-12:
        xmax += 1.0
        xmin -= 1.0
    if abs(ymax - ymin) < 1e-12:
        ymax += 1.0
        ymin -= 1.0
    def px(x: float) -> float:
        return pad + (x - xmin) / (xmax - xmin) * (width - 2 * pad)
    def py(y: float) -> float:
        return height - pad - (y - ymin) / (ymax - ymin) * (height - 2 * pad)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{pad}" y="28" font-family="Arial" font-size="18" font-weight="700">{html.escape(title)}</text>',
        f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#1f2933"/>',
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#1f2933"/>',
        f'<text x="{pad}" y="{height-14}" font-family="Arial" font-size="12">{html.escape(x_label)}</text>',
        f'<text x="{width-pad-170}" y="{height-14}" font-family="Arial" font-size="12">{html.escape(y_label)}</text>',
        f'<text x="{pad+4}" y="{pad+14}" font-family="Arial" font-size="11">{ymax:.3g}</text>',
        f'<text x="{pad+4}" y="{height-pad-6}" font-family="Arial" font-size="11">{ymin:.3g}</text>',
    ]
    for idx, ys in enumerate(series):
        color = COLORS[idx % len(COLORS)]
        for segment in _finite_segments(xs, ys):
            if len(segment) == 1:
                x, y = segment[0]
                lines.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="2.2" fill="{color}"/>')
            else:
                pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in segment)
                lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{pts}"/>')
        lx = width - pad - 160
        ly = 46 + idx * 18
        lines.append(f'<line x1="{lx}" y1="{ly-4}" x2="{lx+22}" y2="{ly-4}" stroke="{color}" stroke-width="2.2"/>')
        lines.append(f'<text x="{lx+28}" y="{ly}" font-family="Arial" font-size="12">{html.escape(labels[idx])}</text>')
    lines.append("</svg>")
    p.write_text("\n".join(lines))


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _finite_segments(xs: list[float | None], ys: list[float | None]) -> list[list[tuple[float, float]]]:
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for x, y in zip(xs, ys):
        if x is None or y is None:
            if current:
                segments.append(current)
                current = []
            continue
        current.append((x, y))
    if current:
        segments.append(current)
    return segments


def _empty_svg(width: int, height: int, title: str) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            f'<text x="40" y="40" font-family="Arial" font-size="18" font-weight="700">{html.escape(title)}</text>',
            '<text x="40" y="78" font-family="Arial" font-size="13">No data available.</text>',
            "</svg>",
        ]
    )
