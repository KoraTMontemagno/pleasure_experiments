import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pleasure_experiments.synthetic_agent_participant_plots.sweep_agents import (
    indicative_cases,
    grid_values,
    run_sweep,
)


class AgentSweepTests(unittest.TestCase):
    def test_grid_includes_zero_and_one(self):
        self.assertEqual(grid_values(0.5), [0, 0.5, 1.0])
        self.assertEqual(grid_values(0.3), [0, 0.3, 0.6, 0.9, 1.0])
        with self.assertRaises(ValueError):
            grid_values(0)

    def test_indicative_cases_cover_all_corners_and_full_parameter_ranges(self):
        cases = indicative_cases(50, seed=7)
        corners = {
            tuple(case[name] for name in (
                "pain_threshold",
                "pain_spread",
                "pleasure_threshold",
                "pleasure_spread",
            ))
            for case in cases
            if all(value in (0.0, 1.0) for value in case.values())
        }

        self.assertEqual(len(cases), 50)
        self.assertEqual(len(corners), 16)
        for name in (
            "pain_threshold",
            "pain_spread",
            "pleasure_threshold",
            "pleasure_spread",
        ):
            values = [case[name] for case in cases]
            self.assertEqual(min(values), 0.0)
            self.assertEqual(max(values), 1.0)
        with self.assertRaisesRegex(ValueError, "At least 16"):
            indicative_cases(15)

    def test_small_grid_writes_all_combinations_and_outcomes(self):
        def fake_simulate_agent(**kwargs):
            return {
                "pain": {"threshold": kwargs["pain_threshold"], "std": 0.1},
                "pleasure": {
                    "threshold": kwargs["pleasure_threshold"],
                    "std": kwargs["pleasure_spread"],
                    "trials": [{"response": 1000}],
                },
                "estimated_ceiling": 0.4,
                "safe_ceiling": 0.5,
                "initial_levels": (0.2, 0.3, 0.4),
                "validated_levels": (0.2, 0.3, 0.4),
                "validation_trials": [{"cycle": 2}],
                "validation_passed": True,
                "validation_accepted_by_pleasure": False,
                "automatic_fallback_used": True,
                "final_trials": [{"trial": 1}],
                "stopped_at": None,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "sweep.csv"
            with patch(
                "pleasure_experiments.synthetic_agent_participant_plots."
                "sweep_agents.simulate_agent",
                side_effect=fake_simulate_agent,
            ) as simulated:
                run_sweep(
                    output_path=output_path,
                    grid_step=1,
                    annoyance_trials=2,
                    pleasure_trials=2,
                    replicates=2,
                    seed=10,
                )
            with output_path.open(encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(simulated.call_count, 32)
        self.assertEqual(len(rows), 32)
        self.assertEqual(rows[0]["pain_threshold"], "0")
        self.assertEqual(rows[0]["pain_spread"], "0")
        self.assertEqual(rows[-1]["pleasure_spread"], "1")
        self.assertEqual(rows[0]["pleasure_pain_exclusions"], "1")
        self.assertEqual(rows[0]["validation_cycles"], "2")
        self.assertEqual(rows[0]["validation_accepted_by_pleasure"], "False")
        self.assertEqual(rows[0]["automatic_fallback_used"], "True")

    def test_sweep_refuses_unintended_huge_grid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "above the configured limit"):
                run_sweep(
                    output_path=Path(temp_dir) / "sweep.csv",
                    grid_step=0.1,
                    max_combinations=1000,
                )


if __name__ == "__main__":
    unittest.main()
