"""Aerodynamic coefficient and force/moment model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from aerosim6dof.core.interpolation import Table1D
from aerosim6dof.core.vectors import clamp

from .aero_database import AeroCoefficientDatabase, AeroQuery
from .geometry import ReferenceGeometry


@dataclass(frozen=True)
class AeroSample:
    force_body_n: np.ndarray
    moment_body_nm: np.ndarray
    alpha_rad: float
    beta_rad: float
    qbar_pa: float
    mach: float
    cd: float
    cl: float
    cy: float
    cm: float
    cn: float
    cl_roll: float


class AerodynamicModel:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.tables: dict[str, Table1D] = {}
        tables = self.config.get("tables", {})
        for key, pairs in tables.items():
            self.tables[key] = Table1D.from_pairs(pairs)
        self.database = AeroCoefficientDatabase(self.config.get("database", {}))
        errors = self.database.validate()
        if errors:
            raise ValueError("; ".join(errors))

    def c(self, key: str, default: float) -> float:
        return float(self.config.get(key, default))

    def compute(
        self,
        density_kgpm3: float,
        speed_of_sound_mps: float,
        v_body_mps: np.ndarray,
        rates_rps: np.ndarray,
        controls_rad: dict[str, float],
        geometry: ReferenceGeometry,
    ) -> AeroSample:
        speed = max(1e-3, float(np.linalg.norm(v_body_mps)))
        vx, vy, vz = v_body_mps
        alpha = clamp(math.atan2(-vz, max(1e-6, vx)), math.radians(-35.0), math.radians(35.0))
        beta = clamp(math.asin(clamp(vy / speed, -1.0, 1.0)), math.radians(-30.0), math.radians(30.0))
        qbar = min(float(self.config.get("qbar_cap_pa", 250_000.0)), 0.5 * density_kgpm3 * speed * speed)
        mach = speed / max(speed_of_sound_mps, 1.0)
        de = float(controls_rad.get("elevator", 0.0))
        da = float(controls_rad.get("aileron", 0.0))
        dr = float(controls_rad.get("rudder", 0.0))
        p, q, r = rates_rps
        p_hat = p * geometry.span_m / (2.0 * speed)
        q_hat = q * geometry.chord_m / (2.0 * speed)
        r_hat = r * geometry.span_m / (2.0 * speed)
        alpha_deg = math.degrees(alpha)
        beta_deg = math.degrees(beta)
        compressibility = self._compressibility_factor(mach)
        cl_alpha_slope = self._scheduled("cl_alpha", 3.1, mach) * compressibility
        alpha_table = self.tables.get("cl_alpha_table")
        cl_alpha = alpha_table(alpha_deg) if alpha_table else cl_alpha_slope * alpha
        cd = (
            self.c("cd0", 0.075)
            + self.c("cd_alpha", 0.58) * alpha * alpha
            + self.c("cd_beta", 0.2) * beta * beta
            + self._mach_drag_rise(mach)
        )
        base_cl = cl_alpha
        cl_control = self._scheduled("cl_elevator", 0.48, mach) * de
        base_cy = self._scheduled("cy_beta", -0.82, mach) * beta
        cy_control = self._scheduled("cy_rudder", 0.35, mach) * dr
        base_cl_roll = self._scheduled("cl_beta", -0.04, mach) * beta
        cl_roll_control = self._scheduled("cl_da", 0.08, mach) * da + self._scheduled("cl_p", -0.45, mach) * p_hat + self.c("cl_dr_cross", 0.0) * dr
        base_cm = self._scheduled("cm_alpha", 0.78, mach) * alpha + self.c("cm_beta_cross", 0.0) * beta
        cm_control = self._scheduled("cm_de", 1.05, mach) * de + self._scheduled("cm_q", -9.0, mach) * q_hat
        base_cn = self._scheduled("cn_beta", 0.25, mach) * beta
        cn_control = self._scheduled("cn_dr", -0.18, mach) * dr + self._scheduled("cn_r", -0.35, mach) * r_hat + self.c("cn_da_cross", 0.0) * da
        if self.database.has_coefficients():
            overrides = self.database.interpolate(AeroQuery(alpha_deg=alpha_deg, beta_deg=beta_deg, mach=mach))
            cd = overrides.get("cd", cd)
            base_cl = overrides.get("cl", base_cl)
            base_cy = overrides.get("cy", base_cy)
            base_cm = overrides.get("cm", base_cm)
            base_cn = overrides.get("cn", base_cn)
            base_cl_roll = overrides.get("cl_roll", base_cl_roll)
        cl = base_cl + cl_control
        cy = base_cy + cy_control
        cm = base_cm + cm_control
        cn = base_cn + cn_control
        cl_roll = base_cl_roll + cl_roll_control
        cl, cd = self._apply_stall(alpha, cl, cd)
        cd, cl, cy, cm, cn, cl_roll = self._apply_uncertainty(cd, cl, cy, cm, cn, cl_roll)
        drag = -cd * qbar * geometry.area_m2 * (v_body_mps / speed)
        force = drag + np.array([0.0, cy * qbar * geometry.area_m2, cl * qbar * geometry.area_m2], dtype=float)
        moment = np.array(
            [
                cl_roll * qbar * geometry.area_m2 * geometry.span_m,
                cm * qbar * geometry.area_m2 * geometry.chord_m,
                cn * qbar * geometry.area_m2 * geometry.span_m,
            ],
            dtype=float,
        )
        return AeroSample(force, moment, alpha, beta, qbar, mach, cd, cl, cy, cm, cn, cl_roll)

    def _mach_drag_rise(self, mach: float) -> float:
        start = self.c("drag_rise_mach", 0.82)
        scale = self.c("drag_rise_cd", 0.08)
        if mach <= start:
            return 0.0
        return scale * min(4.0, (mach - start) ** 2 * 6.0)

    def _scheduled(self, key: str, default: float, mach: float) -> float:
        table = self.tables.get(f"{key}_by_mach")
        return table(mach) if table else self.c(key, default)

    def _compressibility_factor(self, mach: float) -> float:
        model = str(self.config.get("compressibility", "none"))
        if model == "prandtl_glauert" and mach < 0.98:
            return min(float(self.config.get("compressibility_cap", 1.8)), 1.0 / math.sqrt(max(0.05, 1.0 - mach * mach)))
        if model == "karman_tsien" and mach < 0.98:
            beta = math.sqrt(max(0.05, 1.0 - mach * mach))
            return min(float(self.config.get("compressibility_cap", 1.8)), 1.0 / (beta + mach * mach / (1.0 + beta) * 0.5))
        return 1.0

    def _apply_stall(self, alpha: float, cl: float, cd: float) -> tuple[float, float]:
        stall = self.config.get("stall", {})
        if not stall:
            return cl, cd
        alpha_stall = math.radians(float(stall.get("alpha_stall_deg", 18.0)))
        abs_alpha = abs(alpha)
        if abs_alpha <= alpha_stall:
            return cl, cd
        post_factor = float(stall.get("post_stall_lift_factor", 0.45))
        decay = max(0.2, 1.0 - (abs_alpha - alpha_stall) / math.radians(float(stall.get("full_stall_width_deg", 22.0))))
        stalled_cl = math.copysign(abs(cl) * (post_factor + (1.0 - post_factor) * decay), cl)
        stalled_cd = cd + float(stall.get("drag_rise", 0.75)) * math.sin(abs_alpha - alpha_stall) ** 2
        return stalled_cl, stalled_cd

    def _apply_uncertainty(
        self,
        cd: float,
        cl: float,
        cy: float,
        cm: float,
        cn: float,
        cl_roll: float,
    ) -> tuple[float, float, float, float, float, float]:
        unc = self.config.get("uncertainty", {})
        return (
            cd * float(unc.get("cd_scale", 1.0)) + float(unc.get("cd_bias", 0.0)),
            cl * float(unc.get("cl_scale", 1.0)) + float(unc.get("cl_bias", 0.0)),
            cy * float(unc.get("cy_scale", 1.0)) + float(unc.get("cy_bias", 0.0)),
            cm * float(unc.get("cm_scale", 1.0)) + float(unc.get("cm_bias", 0.0)),
            cn * float(unc.get("cn_scale", 1.0)) + float(unc.get("cn_bias", 0.0)),
            cl_roll * float(unc.get("cl_roll_scale", 1.0)) + float(unc.get("cl_roll_bias", 0.0)),
        )
