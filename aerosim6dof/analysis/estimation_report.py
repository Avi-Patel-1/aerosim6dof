"""Estimation fusion report entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aerosim6dof.estimation.fusion import write_estimation_fusion_report


def estimation_report(
    run_dir: str | Path,
    out_dir: str | Path | None = None,
    *,
    max_time_gap_s: float | None = None,
) -> dict[str, Any]:
    """Generate estimation fusion artifacts for an existing run directory."""

    return write_estimation_fusion_report(run_dir, out_dir, max_time_gap_s=max_time_gap_s)


__all__ = ["estimation_report"]
