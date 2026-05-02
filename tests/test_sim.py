import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from aerosim6dof.analysis.aero import aero_sweep, inspect_aero
from aerosim6dof.analysis.compare import compare_histories
from aerosim6dof.analysis.config_tools import config_diff, generate_scenario, inspect_vehicle
from aerosim6dof.analysis.environment import environment_report
from aerosim6dof.analysis.engagement import engagement_report
from aerosim6dof.analysis.propulsion import inspect_propulsion, thrust_curve_report
from aerosim6dof.analysis.sensors import sensor_report
from aerosim6dof.analysis.stability import linear_model_report, stability_report, trim_sweep
from aerosim6dof.core.integration import adaptive_rk45_step, rk2_step
from aerosim6dof.core.quaternions import from_euler, normalize, to_dcm, to_euler
from aerosim6dof.environment.atmosphere import AtmosphereModel, atmosphere
from aerosim6dof.environment.gravity import gravity_magnitude
from aerosim6dof.environment.terrain import TerrainModel
from aerosim6dof.environment.wind import WindModel
from aerosim6dof.gnc.lqr import controllability_rank, discrete_lqr
from aerosim6dof.gnc.trim import simple_trim
from aerosim6dof.scenario import Scenario
from aerosim6dof.sensors.sensor_suite import SensorSuite
from aerosim6dof.sim import RateLimitedActuator, run_scenario
from aerosim6dof.simulation.campaign import run_sweep_campaign
from aerosim6dof.simulation.contact import GroundContactModel
from aerosim6dof.simulation.events import EventDetector
from aerosim6dof.simulation.fault_campaign import run_fault_campaign
from aerosim6dof.simulation.runner import batch_run, linearize_scenario, monte_carlo_run, report_run
from aerosim6dof.simulation.targets import TargetObject, TargetSuite
from aerosim6dof.reports.svg import write_time_plot
from aerosim6dof.vehicle.actuators import SurfaceActuator
from aerosim6dof.vehicle.aerodynamics import AerodynamicModel
from aerosim6dof.vehicle.geometry import ReferenceGeometry
from aerosim6dof.vehicle.propulsion import PropulsionModel
from aerosim6dof.vehicle.state import VehicleState


ROOT = Path(__file__).resolve().parents[1]


class FlightSimTests(unittest.TestCase):
    def test_quaternion_normalizes_and_reports_z_up_pitch(self):
        q = normalize(np.array([2.0, 0.0, 0.0, 0.0]))
        self.assertAlmostEqual(float(np.linalg.norm(q)), 1.0)
        nose_up = from_euler(0.0, math.radians(10.0), 0.0)
        roll, pitch, yaw = to_euler(nose_up)
        self.assertAlmostEqual(math.degrees(roll), 0.0, places=6)
        self.assertAlmostEqual(math.degrees(pitch), 10.0, places=6)
        self.assertAlmostEqual(math.degrees(yaw), 0.0, places=6)
        body_x_inertial = to_dcm(nose_up) @ np.array([1.0, 0.0, 0.0])
        self.assertGreater(body_x_inertial[2], 0.0)

    def test_atmosphere_and_gravity(self):
        self.assertGreater(atmosphere(0)["density"], atmosphere(5000)["density"])
        self.assertGreater(gravity_magnitude(0), gravity_magnitude(20000))

    def test_terrain_models_and_agl_queries(self):
        plane = TerrainModel({"base_altitude_m": 5.0, "slope_x": 0.01, "slope_y": -0.02})
        position = np.array([100.0, 10.0, 50.0])
        self.assertAlmostEqual(plane.elevation(position), 5.8)
        self.assertAlmostEqual(plane.query(position)["altitude_agl_m"], 44.2)
        moving = plane.query(position, np.array([10.0, 0.0, -5.0]))
        self.assertAlmostEqual(moving["terrain_slope_x"], 0.01)
        self.assertAlmostEqual(moving["terrain_rate_mps"], 0.1)
        self.assertAlmostEqual(moving["altitude_agl_rate_mps"], -5.1)

        grid = TerrainModel(
            {
                "type": "grid",
                "grid": {
                    "x_m": [0.0, 10.0],
                    "y_m": [0.0, 10.0],
                    "elevation_m": [[0.0, 10.0], [20.0, 30.0]],
                },
            }
        )
        self.assertAlmostEqual(grid.elevation(np.array([5.0, 5.0, 100.0])), 15.0)

        featured = TerrainModel(
            {"features": [{"type": "hill", "center_m": [0.0, 0.0], "height_m": 20.0, "radius_m": 10.0}]}
        )
        self.assertGreater(
            featured.elevation(np.array([0.0, 0.0, 0.0])),
            featured.elevation(np.array([30.0, 0.0, 0.0])),
        )

        malformed = TerrainModel(
            {"base_altitude_m": "bad", "grid": {"x_m": ["bad"], "y_m": [0.0], "elevation_m": [["bad"]]}}
        )
        self.assertEqual(malformed.elevation(np.array([0.0, 0.0, 10.0])), 0.0)
        disabled = TerrainModel({"enabled": "false", "base_altitude_m": 500.0})
        self.assertEqual(disabled.elevation(np.array([0.0, 0.0, 10.0])), 0.0)

    def test_ground_contact_classification_and_response(self):
        terrain = TerrainModel()
        contact = GroundContactModel({"enabled": True, "mode": "bounce", "stop_on_contact": False, "friction": 0.25})
        state = VehicleState(
            position_m=np.array([0.0, 0.0, -0.5]),
            velocity_mps=np.array([10.0, 0.0, -4.0]),
            quaternion=np.array([1.0, 0.0, 0.0, 0.0]),
            rates_rps=np.zeros(3),
            mass_kg=10.0,
        )
        contact_state = contact.evaluate(terrain.query(state.position_m, state.velocity_mps))
        self.assertEqual(contact_state["ground_contact_state"], "impact")
        self.assertEqual(contact_state["ground_contact_severity"], 2.0)
        self.assertFalse(contact_state["ground_contact_stop"])

        adjusted, action = contact.apply(state, terrain)
        self.assertEqual(action["ground_contact_action"], "bounce")
        self.assertGreaterEqual(adjusted.position_m[2], 0.0)
        self.assertGreater(adjusted.velocity_mps[2], 0.0)
        self.assertLess(abs(float(adjusted.velocity_mps[0])), 10.0)

    def test_ground_contact_event_carries_classification(self):
        detector = EventDetector()
        stop = detector.update(
            {"time_s": 1.0, "altitude_m": -0.2, "vz_mps": -1.2},
            {},
            -0.2,
            {
                "ground_contact_state": "touchdown",
                "impact_speed_mps": 1.2,
                "altitude_agl_rate_mps": -1.2,
                "ground_contact_stop": False,
            },
        )
        self.assertFalse(stop)
        ground = next(event for event in detector.finalize() if event["type"] == "ground_impact")
        self.assertEqual(ground["classification"], "touchdown")
        self.assertAlmostEqual(ground["impact_speed_mps"], 1.2)

    def test_target_suite_relative_telemetry(self):
        suite = TargetSuite(
            [
                TargetObject(
                    target_id="incoming",
                    initial_position_m=np.array([100.0, 0.0, 10.0]),
                    velocity_mps=np.array([-10.0, 0.0, 0.0]),
                )
            ]
        )
        summary, rows = suite.sample(0.0, np.array([0.0, 0.0, 10.0]), np.array([20.0, 0.0, 0.0]))
        self.assertEqual(summary["target_id"], "incoming")
        self.assertAlmostEqual(summary["target_range_m"], 100.0)
        self.assertAlmostEqual(summary["target_range_rate_mps"], -30.0)
        self.assertAlmostEqual(summary["closing_speed_mps"], 30.0)
        self.assertEqual(rows[0]["target_active"], 1.0)

    def test_target_events_track_closest_approach(self):
        detector = EventDetector({"target_threshold_m": 8.0})
        detector.update({"time_s": 0.0, "altitude_m": 10.0, "vz_mps": 0.0, "target_id": "a", "target_range_m": 20.0}, {}, 10.0)
        detector.update({"time_s": 1.0, "altitude_m": 10.0, "vz_mps": 0.0, "target_id": "a", "target_range_m": 6.0}, {}, 10.0)
        detector.update({"time_s": 2.0, "altitude_m": 10.0, "vz_mps": 0.0, "target_id": "a", "target_range_m": 12.0}, {}, 10.0)
        events = detector.finalize()
        closest = next(event for event in events if event["type"] == "closest_approach")
        crossing = next(event for event in events if event["type"] == "target_crossing")
        self.assertAlmostEqual(closest["miss_distance_m"], 6.0)
        self.assertEqual(closest["target_id"], "a")
        self.assertAlmostEqual(crossing["miss_distance_m"], 6.0)

    def test_integrators(self):
        def fn(_t, y):
            return -y

        y0 = np.array([1.0])
        self.assertLess(abs(float(rk2_step(fn, 0.0, y0, 0.1)[0]) - math.exp(-0.1)), 0.002)
        y_next, err, rejects = adaptive_rk45_step(fn, 0.0, y0, 0.2, tolerance=1e-8)
        self.assertLess(abs(float(y_next[0]) - math.exp(-0.2)), 1e-5)
        self.assertGreaterEqual(err, 0.0)
        self.assertGreaterEqual(rejects, 0)

    def test_wind_gust_and_turbulence(self):
        wind = WindModel(
            {
                "steady_mps": [1.0, 2.0, 0.0],
                "sinusoidal_gust": {"amplitude_mps": [0.0, 3.0, 0.0], "frequency_hz": 0.5},
                "turbulence": {"enabled": True, "intensity_mps": [0.1, 0.1, 0.1]},
            },
            seed=3,
        )
        a = wind.sample(0.0, np.array([0.0, 0.0, 100.0]), 80.0, 0.02).velocity_mps
        b = wind.sample(0.5, np.array([0.0, 0.0, 100.0]), 80.0, 0.02).velocity_mps
        self.assertEqual(a.shape, (3,))
        self.assertNotAlmostEqual(float(a[1]), float(b[1]))

    def test_layered_atmosphere_and_power_law_wind_are_runtime_configurable(self):
        standard = AtmosphereModel().sample(1000.0)
        weather = AtmosphereModel({"model": "layered", "temperature_offset_k": 8.0, "pressure_scale": 0.97}).sample(1000.0)
        self.assertNotAlmostEqual(standard.temperature, weather.temperature)
        self.assertNotAlmostEqual(standard.density, weather.density)

        wind = WindModel(
            {
                "steady_mps": [5.0, 0.0, 0.0],
                "shear": {
                    "model": "power_law",
                    "reference_wind_mps": [5.0, 0.0, 0.0],
                    "reference_altitude_m": 10.0,
                    "shear_exponent": 0.2,
                },
            }
        )
        low = wind.deterministic(0.0, np.array([0.0, 0.0, 10.0]))
        high = wind.deterministic(0.0, np.array([0.0, 0.0, 1000.0]))
        self.assertAlmostEqual(float(low[0]), 5.0)
        self.assertGreater(float(high[0]), float(low[0]))

    def test_actuator_rate_limit_and_failure(self):
        a = RateLimitedActuator(limit=1.0, rate_limit=0.5)
        self.assertAlmostEqual(a.step(1.0, 0.2), 0.1)
        stuck = SurfaceActuator({"failure": {"mode": "stuck", "start_s": 1.0, "value_rad": -0.2}})
        self.assertAlmostEqual(stuck.step(0.5, 0.1, t=1.2).value_rad, -0.2)

    def test_propulsion_cutoff_and_misalignment(self):
        motor = PropulsionModel({"max_thrust_n": 100.0, "burn_time_s": 1.0, "misalignment_deg": [1.0, 0.5, 0.0]})
        active = motor.sample(0.5, 0.8, 10.0, 5.0)
        cutoff = motor.sample(2.0, 0.8, 10.0, 5.0)
        self.assertGreater(active.thrust_n, 0.0)
        self.assertGreater(np.linalg.norm(active.thrust_body_n[1:]), 0.0)
        self.assertEqual(cutoff.thrust_n, 0.0)
        lagged = PropulsionModel({"model": "liquid", "max_thrust_n": 100.0, "engine_lag_s": 1.0, "burn_time_s": 10.0})
        slow = lagged.sample(0.1, 1.0, 10.0, 5.0, dt=0.1)
        self.assertLess(slow.throttle_actual, 1.0)

    def test_aero_coefficient_sanity(self):
        aero = AerodynamicModel({"cm_alpha": 0.8, "cm_de": 1.0})
        sample = aero.compute(
            1.2,
            340.0,
            np.array([100.0, 2.0, -5.0]),
            np.zeros(3),
            {"elevator": 0.0, "aileron": 0.0, "rudder": 0.0},
            ReferenceGeometry(),
        )
        self.assertGreater(sample.qbar_pa, 0.0)
        self.assertGreater(sample.mach, 0.0)
        self.assertTrue(np.all(np.isfinite(sample.force_body_n)))

    def test_aero_database_and_reports(self):
        vehicle = ROOT / "examples/vehicles/baseline.json"
        info = inspect_aero(vehicle)
        self.assertTrue(info["has_database"])
        with tempfile.TemporaryDirectory() as tmp:
            summary = aero_sweep(vehicle, tmp, mach_values=[0.3, 0.8], alpha_deg_values=[-5.0, 0.0, 10.0])
            self.assertEqual(summary["samples"], 6)
            self.assertTrue((Path(tmp) / "aero_sweep.csv").exists())

    def test_propulsion_environment_and_config_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            prop = thrust_curve_report(ROOT / "examples/vehicles/baseline.json", Path(tmp) / "prop")
            env = environment_report(ROOT / "examples/environments/gusted_range.json", Path(tmp) / "env")
            self.assertTrue(Path(prop["report"]).exists())
            self.assertTrue(Path(env["report"]).exists())
            vehicle_info = inspect_vehicle(ROOT / "examples/vehicles/baseline.json")
            self.assertEqual(vehicle_info["name"], "baseline_research_vehicle")
            prop_info = inspect_propulsion(ROOT / "examples/vehicles/electric_uav.json")
            self.assertEqual(prop_info["model"], "electric")
            diff = config_diff(ROOT / "examples/vehicles/baseline.json", ROOT / "examples/vehicles/electric_uav.json")
            self.assertTrue(diff["changed"] or diff["added"])
            generated = Path(tmp) / "generated.json"
            generate_scenario(generated, "generated_case")
            self.assertTrue(generated.exists())

    def test_scenario_validation(self):
        scenario = Scenario.from_file(ROOT / "examples/scenarios/nominal_ascent.json")
        self.assertEqual(scenario.name, "nominal_ascent")
        with self.assertRaises(ValueError):
            Scenario.from_dict({"name": "bad", "dt": -0.1, "duration": 1.0})
        with self.assertRaisesRegex(ValueError, "initial.position_m"):
            Scenario.from_dict({"name": "bad_vector", "initial": {"position_m": [0.0, 1.0]}})
        with self.assertRaisesRegex(ValueError, "guidance.throttle"):
            Scenario.from_dict({"name": "bad_throttle", "guidance": {"throttle": 1.4}})

    def test_sensor_sampling(self):
        suite = SensorSuite(
            {
                "seed": 2,
                "gps": {"rate_hz": 1.0, "latency_s": 0.05, "multipath_amplitude_m": 0.5},
                "radar_altimeter": {"rate_hz": 20.0},
                "optical_flow": {"rate_hz": 20.0, "max_agl_m": 200.0},
                "horizon": {"rate_hz": 20.0},
            }
        )
        truth = {
            "position_m": np.array([1.0, 2.0, 100.0]),
            "velocity_mps": np.array([10.0, 0.0, 0.0]),
            "quaternion": from_euler(0.0, 0.0, 0.0),
            "rates_rps": np.zeros(3),
            "accel_body_mps2": np.zeros(3),
            "airspeed_mps": 10.0,
            "qbar_pa": 60.0,
            "mach": 0.03,
            "altitude_agl_m": 100.0,
        }
        first = suite.sample(0.0, 0.02, truth)
        second = suite.sample(0.1, 0.02, truth)
        self.assertIn("imu_ax_mps2", first)
        self.assertIn("radar_agl_m", first)
        self.assertIn("optical_flow_x_radps", first)
        self.assertIn("horizon_pitch_deg", first)
        self.assertAlmostEqual(first["radar_agl_m"], 100.0, delta=1.0)
        self.assertEqual(first.get("gps_valid"), second.get("gps_valid"))
        uncoupled = SensorSuite({"seed": 2, "radar_altimeter": {"rate_hz": 20.0, "noise_std_m": 0.0, "terrain_coupled": False}})
        self.assertAlmostEqual(uncoupled.sample(0.0, 0.02, truth)["radar_agl_m"], 100.0)
        truth_with_terrain = dict(truth)
        truth_with_terrain["position_m"] = np.array([1.0, 2.0, 150.0])
        truth_with_terrain["altitude_agl_m"] = 120.0
        coupled = SensorSuite({"seed": 2, "radar_altimeter": {"rate_hz": 20.0, "noise_std_m": 0.0, "terrain_coupled": True}})
        uncoupled = SensorSuite({"seed": 2, "radar_altimeter": {"rate_hz": 20.0, "noise_std_m": 0.0, "terrain_coupled": False}})
        self.assertAlmostEqual(coupled.sample(0.0, 0.02, truth_with_terrain)["radar_agl_m"], 120.0)
        self.assertAlmostEqual(uncoupled.sample(0.0, 0.02, truth_with_terrain)["radar_agl_m"], 150.0)
        faulted = SensorSuite({"seed": 2, "gps": {"rate_hz": 10.0}, "faults": [{"sensor": "gps", "type": "dropout", "start_s": 0.0, "end_s": 1.0}]})
        self.assertEqual(faulted.sample(0.0, 0.02, truth)["gps_valid"], 0.0)

    def test_scenario_runs_and_writes_outputs(self):
        scenario = Scenario.from_file(ROOT / "examples/scenarios/nominal_ascent.json")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_scenario(scenario, tmp)
            out = Path(tmp)
            self.assertGreater(summary["samples"], 10)
            for name in [
                "history.csv",
                "truth.csv",
                "controls.csv",
                "sensors.csv",
                "events.json",
                "summary.json",
                "scenario_resolved.json",
                "manifest.json",
                "report.html",
            ]:
                self.assertTrue((out / name).exists(), name)
            self.assertGreaterEqual(len(list((out / "plots").glob("*.svg"))), 25)
            data = json.loads((out / "summary.json").read_text())
            self.assertIn("max_speed_mps", data)
            self.assertIn("min_altitude_agl_m", data)
            self.assertIn("max_impact_speed_mps", data)
            history_header = (out / "history.csv").read_text().splitlines()[0]
            self.assertIn("altitude_agl_m", history_header)
            self.assertIn("terrain_elevation_m", history_header)
            self.assertIn("altitude_agl_rate_mps", history_header)
            self.assertIn("ground_contact", history_header)
            self.assertIn("impact_speed_mps", history_header)
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["scenario"], "nominal_ascent")

    def test_target_intercept_writes_target_telemetry(self):
        scenario = Scenario.from_file(ROOT / "examples/scenarios/target_intercept.json")
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_scenario(scenario, tmp)
            out = Path(tmp)
            self.assertTrue((out / "targets.csv").exists())
            history_header = (out / "history.csv").read_text().splitlines()[0]
            self.assertIn("target_range_m", history_header)
            self.assertIn("closing_speed_mps", history_header)
            self.assertIn("relative_z_m", history_header)
            target_header = (out / "targets.csv").read_text().splitlines()[0]
            self.assertIn("target_id", target_header)
            self.assertIn("target_range_rate_mps", target_header)
            self.assertTrue((out / "interceptors.csv").exists())
            interceptor_header = (out / "interceptors.csv").read_text().splitlines()[0]
            self.assertIn("interceptor_id", interceptor_header)
            self.assertIn("interceptor_range_m", interceptor_header)
            self.assertIn("interceptor_closing_speed_mps", interceptor_header)
            events = json.loads((out / "events.json").read_text())
            self.assertTrue(any(event["type"] == "closest_approach" for event in events))
            self.assertTrue(any(event["type"] == "interceptor_launch" for event in events))
            self.assertTrue(any(event["type"] == "interceptor_closest_approach" for event in events))
            self.assertIsNotNone(summary["min_target_range_m"])
            self.assertIsNotNone(summary["max_closing_speed_mps"])
            self.assertIsNotNone(summary["min_interceptor_range_m"])
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertIn("targets.csv", manifest["files"])
            self.assertIn("interceptors.csv", manifest["files"])
            self.assertIn("engagement_report.html", manifest["files"])
            engagement = engagement_report(out)
            self.assertEqual(engagement["target_count"], 2)
            self.assertEqual(engagement["interceptor_count"], 1)
            self.assertTrue((out / "engagement_report.html").exists())

    def test_compare_trim_and_linearize(self):
        scenario = Scenario.from_file(ROOT / "examples/scenarios/nominal_ascent.json")
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b, tempfile.TemporaryDirectory() as c:
            run_scenario(scenario, a)
            run_scenario(Scenario.from_file(ROOT / "examples/scenarios/gusted_crossrange.json"), b)
            compare = compare_histories(Path(a) / "history.csv", Path(b) / "history.csv", c)
            self.assertGreater(compare["samples_compared"], 10)
        trim = simple_trim(json.loads((ROOT / "examples/vehicles/baseline.json").read_text()), 120.0, 1000.0)
        self.assertIn("elevator_deg", trim)
        with tempfile.TemporaryDirectory() as tmp:
            lin = linearize_scenario(scenario, 0.2, tmp)
            self.assertEqual(len(lin["A"]), 14)
            self.assertTrue((Path(tmp) / "linearization.json").exists())
            stability = stability_report(Path(tmp) / "linearization.json", Path(tmp) / "stability")
            self.assertIn("eigenvalues", stability)
            linear_report = linear_model_report(Path(tmp) / "linearization.json", Path(tmp) / "linear_report")
            self.assertEqual(linear_report["state_count"], 14)
        with tempfile.TemporaryDirectory() as tmp:
            sweep = trim_sweep(ROOT / "examples/vehicles/baseline.json", tmp, [90.0, 120.0], [0.0, 1000.0])
            self.assertEqual(sweep["count"], 4)
            self.assertTrue((Path(tmp) / "trim_sweep_report.html").exists())

    def test_lqr_and_sweep_campaign(self):
        a = np.array([[1.0, 0.1], [0.0, 1.0]])
        b = np.array([[0.0], [0.1]])
        self.assertEqual(controllability_rank(a, b), 2)
        sol = discrete_lqr(a, b, np.eye(2), np.eye(1))
        self.assertEqual(sol["K"].shape, (1, 2))
        scenario = Scenario.from_file(ROOT / "examples/scenarios/nominal_ascent.json")
        with tempfile.TemporaryDirectory() as tmp:
            campaign = run_sweep_campaign(scenario, tmp, {"guidance.throttle": [0.82, 0.86]}, max_runs=4)
            self.assertEqual(campaign["count"], 2)
            self.assertTrue((Path(tmp) / "campaign_index.csv").exists())

    def test_sensor_report_and_fault_campaign(self):
        scenario = Scenario.from_file(ROOT / "examples/scenarios/gps_dropout_navigation.json")
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_scenario(scenario, run_dir)
            metrics = sensor_report(run_dir)
            self.assertLess(metrics["gps_valid_fraction"], 1.0)
            self.assertTrue((run_dir / "sensor_report" / "sensor_report.html").exists())
            campaign = run_fault_campaign(
                Scenario.from_file(ROOT / "examples/scenarios/nominal_ascent.json"),
                Path(tmp) / "faults",
                ["gps_dropout", "thrust_loss"],
                max_runs=3,
            )
            self.assertEqual(campaign["count"], 2)
            self.assertTrue((Path(tmp) / "faults" / "fault_campaign_report.html").exists())

    def test_reports_handle_missing_values_and_batch_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_time_plot(
                out / "missing.svg",
                [{"time_s": 0.0, "a": ""}, {"time_s": 1.0, "a": "nan"}, {"time_s": 2.0, "a": 3.0}],
                ["a"],
                "Missing Values",
            )
            svg = (out / "missing.svg").read_text()
            self.assertNotIn("nan", svg.lower())
            summary = batch_run(ROOT / "examples/scenarios", out / "batch")
            self.assertGreaterEqual(summary["count"], 12)
            self.assertTrue((out / "batch" / "batch_index.csv").exists())
            report = report_run(out / "batch")
            self.assertTrue(report.exists())

    def test_monte_carlo_runner(self):
        scenario = Scenario.from_file(ROOT / "examples/scenarios/nominal_ascent.json")
        with tempfile.TemporaryDirectory() as tmp:
            result = monte_carlo_run(
                scenario,
                samples=2,
                out_dir=tmp,
                seed=10,
                dispersions={"mass_sigma_kg": 0.1, "wind_sigma_mps": 0.1},
            )
            self.assertEqual(result["samples"], 2)
            self.assertTrue((Path(tmp) / "monte_carlo_index.csv").exists())
            self.assertTrue((Path(tmp) / "monte_carlo_report.html").exists())
            self.assertEqual(report_run(tmp).name, "monte_carlo_report.html")

    def test_cli_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            validate = subprocess.run(
                [sys.executable, "-m", "aerosim6dof", "validate", "--scenario", "examples/scenarios/nominal_ascent.json"],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"valid": true', validate.stdout)
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "run",
                    "--scenario",
                    "examples/scenarios/nominal_ascent.json",
                    "--out",
                    tmp,
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"scenario": "nominal_ascent"', run.stdout)
            monte = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "monte-carlo",
                    "--scenario",
                    "examples/scenarios/nominal_ascent.json",
                    "--samples",
                    "1",
                    "--out",
                    str(Path(tmp) / "mc"),
                    "--seed",
                    "5",
                    "--mass-sigma-kg",
                    "0.1",
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"samples": 1', monte.stdout)
            aero_cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "aero-sweep",
                    "--vehicle",
                    "examples/vehicles/baseline.json",
                    "--mach",
                    "0.3,0.7",
                    "--alpha=-5,5",
                    "--out",
                    str(Path(tmp) / "aero"),
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"samples": 4', aero_cli.stdout)
            sensors_cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "sensor-report",
                    "--run",
                    tmp,
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"gps_valid_fraction"', sensors_cli.stdout)
            faults_cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "fault-campaign",
                    "--scenario",
                    "examples/scenarios/nominal_ascent.json",
                    "--fault",
                    "gps_dropout",
                    "--out",
                    str(Path(tmp) / "fault_cli"),
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"count": 1', faults_cli.stdout)
            linear_cli_dir = Path(tmp) / "linear_cli"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "linearize",
                    "--scenario",
                    "examples/scenarios/nominal_ascent.json",
                    "--time",
                    "0.2",
                    "--out",
                    str(linear_cli_dir),
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            stability_cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "stability",
                    "--linearization",
                    str(linear_cli_dir / "linearization.json"),
                    "--out",
                    str(Path(tmp) / "stability_cli"),
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"eigenvalues"', stability_cli.stdout)
            trim_sweep_cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aerosim6dof",
                    "trim-sweep",
                    "--vehicle",
                    "examples/vehicles/baseline.json",
                    "--speeds",
                    "90,120",
                    "--altitudes",
                    "0,1000",
                    "--out",
                    str(Path(tmp) / "trim_sweep_cli"),
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn('"count": 4', trim_sweep_cli.stdout)
            bad_scenario = Path(tmp) / "bad.json"
            bad_scenario.write_text(json.dumps({"name": "bad", "dt": 0.0, "duration": 1.0}))
            bad = subprocess.run(
                [sys.executable, "-m", "aerosim6dof", "validate", "--scenario", str(bad_scenario)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(bad.returncode, 2)
            self.assertIn('"error"', bad.stderr)


if __name__ == "__main__":
    unittest.main()
