"""Rigid-body dynamics evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aerosim6dof.constants import G0
from aerosim6dof.core.quaternions import derivative as quaternion_derivative
from aerosim6dof.core.quaternions import to_dcm
from aerosim6dof.environment.atmosphere import AtmosphereState, isa_atmosphere
from aerosim6dof.environment.gravity import gravity_vector
from aerosim6dof.vehicle.aerodynamics import AeroSample, AerodynamicModel
from aerosim6dof.vehicle.geometry import ReferenceGeometry
from aerosim6dof.vehicle.mass_properties import MassProperties
from aerosim6dof.vehicle.propulsion import PropulsionModel, PropulsionSample
from aerosim6dof.vehicle.state import VehicleState


@dataclass(frozen=True)
class DynamicsEvaluation:
    derivative: np.ndarray
    acceleration_inertial_mps2: np.ndarray
    acceleration_body_mps2: np.ndarray
    angular_accel_rps2: np.ndarray
    force_body_n: np.ndarray
    moment_body_nm: np.ndarray
    atmosphere: AtmosphereState
    aero: AeroSample
    propulsion: PropulsionSample
    wind_mps: np.ndarray
    airspeed_mps: float
    load_factor_g: float
    energy_j_per_kg: float


class DynamicsModel:
    def __init__(
        self,
        aero: AerodynamicModel,
        propulsion: PropulsionModel,
        mass_properties: MassProperties,
        geometry: ReferenceGeometry,
    ):
        self.aero = aero
        self.propulsion = propulsion
        self.mass_properties = mass_properties
        self.geometry = geometry

    def evaluate(
        self,
        t: float,
        state: VehicleState,
        controls_rad: dict[str, float],
        wind_mps: np.ndarray,
        dt: float | None = None,
    ) -> DynamicsEvaluation:
        rot = to_dcm(state.quaternion)
        env = isa_atmosphere(float(state.position_m[2]))
        v_air_body = rot.T @ (state.velocity_mps - wind_mps)
        aero = self.aero.compute(
            env.density,
            env.speed_of_sound,
            v_air_body,
            state.rates_rps,
            controls_rad,
            self.geometry,
        )
        prop = self.propulsion.sample(
            t,
            float(controls_rad.get("throttle", 0.0)),
            state.mass_kg,
            self.mass_properties.dry_mass_kg,
            dt=dt,
            airspeed_mps=float(np.linalg.norm(v_air_body)),
        )
        force_body = aero.force_body_n + prop.thrust_body_n
        moment_body = aero.moment_body_nm + prop.moment_body_nm
        grav = gravity_vector(float(state.position_m[2]))
        accel = rot @ force_body / max(state.mass_kg, 1e-6) + grav
        accel_mag = float(np.linalg.norm(accel))
        max_accel = 45.0 * G0
        if accel_mag > max_accel:
            accel = accel / accel_mag * max_accel
        inertia = self.mass_properties.inertia(state.mass_kg)
        inv_inertia = np.linalg.inv(inertia)
        angular_accel = inv_inertia @ (moment_body - np.cross(state.rates_rps, inertia @ state.rates_rps))
        angular_accel = np.clip(angular_accel, -np.deg2rad(1100.0), np.deg2rad(1100.0))
        qdot = quaternion_derivative(state.quaternion, state.rates_rps)
        mass_dot = -prop.mass_flow_kgps
        derivative = np.concatenate(
            [
                state.velocity_mps,
                accel,
                qdot,
                angular_accel,
                np.array([mass_dot], dtype=float),
            ]
        )
        accel_body = rot.T @ (accel - grav)
        load_factor = float(np.linalg.norm(accel_body) / G0)
        energy = 0.5 * float(np.dot(state.velocity_mps, state.velocity_mps)) + G0 * float(state.position_m[2])
        return DynamicsEvaluation(
            derivative=derivative,
            acceleration_inertial_mps2=accel,
            acceleration_body_mps2=accel_body,
            angular_accel_rps2=angular_accel,
            force_body_n=force_body,
            moment_body_nm=moment_body,
            atmosphere=env,
            aero=aero,
            propulsion=prop,
            wind_mps=wind_mps,
            airspeed_mps=float(np.linalg.norm(v_air_body)),
            load_factor_g=load_factor,
            energy_j_per_kg=energy,
        )
