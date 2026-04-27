"""Backward-compatible public simulation API."""

from __future__ import annotations

from aerosim6dof.core.quaternions import from_euler as euler_to_q
from aerosim6dof.core.quaternions import normalize as q_normalize
from aerosim6dof.core.quaternions import to_dcm as q_to_dcm
from aerosim6dof.core.quaternions import to_euler as q_to_euler
from aerosim6dof.environment.atmosphere import atmosphere
from aerosim6dof.scenario import Scenario
from aerosim6dof.simulation.runner import batch_run, linearize_scenario, monte_carlo_run, report_run, run_scenario
from aerosim6dof.vehicle.actuators import RateLimitedActuator
from aerosim6dof.vehicle.aerodynamics import AerodynamicModel
from aerosim6dof.vehicle.propulsion import PropulsionModel

__all__ = [
    "AerodynamicModel",
    "PropulsionModel",
    "RateLimitedActuator",
    "Scenario",
    "atmosphere",
    "batch_run",
    "euler_to_q",
    "linearize_scenario",
    "monte_carlo_run",
    "q_normalize",
    "q_to_dcm",
    "q_to_euler",
    "report_run",
    "run_scenario",
]
