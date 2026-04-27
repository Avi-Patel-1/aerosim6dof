"""Envelope calculations."""

from __future__ import annotations

from typing import Any


def qbar_load_points(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    return [{"qbar_pa": float(r["qbar_pa"]), "load_factor_g": float(r["load_factor_g"])} for r in rows]


def envelope_exceedances(rows: list[dict[str, Any]], qbar_limit_pa: float, load_limit_g: float) -> list[dict[str, float]]:
    out = []
    for r in rows:
        if float(r["qbar_pa"]) > qbar_limit_pa or float(r["load_factor_g"]) > load_limit_g:
            out.append(
                {
                    "time_s": float(r["time_s"]),
                    "qbar_pa": float(r["qbar_pa"]),
                    "load_factor_g": float(r["load_factor_g"]),
                }
            )
    return out

