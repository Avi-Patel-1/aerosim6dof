import json
import tempfile
import unittest
from pathlib import Path

from aerosim6dof.analysis import trade_space


class TradeSpaceAnalysisTests(unittest.TestCase):
    def test_run_adapts_summary_and_design_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "summary.json").write_text(
                json.dumps(
                    {
                        "scenario": "nominal_ascent",
                        "duration_s": 18.0,
                        "samples": 601,
                        "final": {"altitude_m": 379.7, "speed_mps": 201.3},
                        "max_qbar_pa": 41665.0,
                        "parameters": {"guidance.pitch_command_deg": 12.0},
                    }
                )
            )
            (out / "scenario_resolved.json").write_text(
                json.dumps({"guidance": {"throttle": 0.86, "pitch_command_deg": 12.0}})
            )

            row = trade_space.run(out, design_paths=["guidance.throttle"])

            self.assertEqual(row["scenario"], "nominal_ascent")
            self.assertEqual(row["final_altitude_m"], 379.7)
            self.assertEqual(row["param_guidance.pitch_command_deg"], 12.0)
            self.assertEqual(row["param_guidance.throttle"], 0.86)
            self.assertEqual(row["run_dir"], str(out))

    def test_sweep_and_trade_analysis_functions(self):
        payload = {
            "base_scenario": "nominal_ascent",
            "parameters": {"guidance.throttle": [0.8, 0.85, 0.9]},
            "runs": [
                _summary("low", 0.8, altitude=300.0, qbar=45000.0, load=2.5),
                _summary("mid", 0.85, altitude=360.0, qbar=42000.0, load=2.0),
                _summary("high", 0.9, altitude=370.0, qbar=48000.0, load=3.3),
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            campaign_path = Path(tmp) / "campaign_summary.json"
            campaign_path.write_text(json.dumps(payload))

            rows = trade_space.sweep(campaign_path)
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["source_kind"], "sweep")
            self.assertEqual(rows[1]["param_guidance.throttle"], 0.85)

            front = trade_space.pareto(rows)
            self.assertEqual([row["scenario"] for row in front], ["high", "mid"])

            rel = trade_space.reliability(rows, {"final_altitude_m": ">=350", "max_qbar_pa": "<=45000"})
            self.assertEqual(rel["pass_count"], 1)
            self.assertAlmostEqual(rel["reliability"], 1.0 / 3.0)
            self.assertIn("final_altitude_m >= 350", rel["rows"][0]["failed_requirements"])

            uncertainty = trade_space.uq(rows, ["final_altitude_m"])
            self.assertAlmostEqual(uncertainty["metrics"]["final_altitude_m"]["mean"], 1030.0 / 3.0)
            self.assertEqual(uncertainty["metrics"]["final_altitude_m"]["p50"], 360.0)
            self.assertEqual(trade_space.UQ(rows, ["final_altitude_m"])["count"], 3)

            sens = trade_space.sensitivity(
                rows,
                parameters=["param_guidance.throttle"],
                metrics=["final_altitude_m"],
            )
            self.assertEqual(sens["count"], 1)
            self.assertGreater(sens["sensitivities"][0]["correlation"], 0.0)

            model = trade_space.surrogate(rows, "final_altitude_m", features=["param_guidance.throttle"])
            self.assertEqual(model["target"], "final_altitude_m")
            prediction = trade_space.predict_surrogate(model, {"param_guidance.throttle": 0.875})
            self.assertGreater(prediction, 350.0)

            optimum = trade_space.optimize(
                rows,
                "final_altitude_m",
                requirements={"max_qbar_pa": "<=45000"},
            )
            self.assertEqual(optimum["best"]["scenario"], "mid")

            bundle = trade_space.campaign(
                campaign_path,
                requirements={"final_altitude_m": ">=350", "max_qbar_pa": "<=45000"},
                objective="final_altitude_m",
            )
            self.assertEqual(bundle["row_count"], 3)
            self.assertEqual(bundle["optimization"]["best"]["scenario"], "mid")
            self.assertEqual(bundle["reliability"]["pass_count"], 1)

    def test_csv_index_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "campaign_index.csv"
            index.write_text(
                "scenario,final_altitude_m,max_qbar_pa,run_dir,param_guidance.throttle\n"
                "a,100.0,40000.0,runs/a,0.7\n"
                "b,120.0,42000.0,runs/b,0.8\n"
            )

            rows = trade_space.sweep(index)

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["final_altitude_m"], 100.0)
            self.assertEqual(rows[1]["param_guidance.throttle"], 0.8)


def _summary(name: str, throttle: float, *, altitude: float, qbar: float, load: float) -> dict:
    return {
        "scenario": name,
        "duration_s": 18.0,
        "samples": 601,
        "final": {"altitude_m": altitude, "speed_mps": 200.0 + throttle},
        "max_altitude_m": altitude,
        "max_qbar_pa": qbar,
        "max_load_factor_g": load,
        "event_count": 0,
        "parameters": {"guidance.throttle": throttle},
        "run_dir": f"runs/{name}",
    }


if __name__ == "__main__":
    unittest.main()
