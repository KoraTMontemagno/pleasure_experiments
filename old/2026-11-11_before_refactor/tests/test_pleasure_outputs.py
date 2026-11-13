import tempfile
import unittest
from pathlib import Path

from pleasure_experiments.code.pleasure_outputs import (
    participant_output_dir,
    plot_response_summary,
    plot_vas_by_intensity,
)


class PleasureOutputTests(unittest.TestCase):
    def test_participant_output_categories_use_separate_folders(self):
        self.assertEqual(
            participant_output_dir("007", "pain"),
            Path("data/sub-007/pain"),
        )
        self.assertEqual(
            participant_output_dir("007", "pleasure"),
            Path("data/sub-007/pleasure"),
        )
        self.assertEqual(
            participant_output_dir("007", "validation"),
            Path("data/sub-007/validation"),
        )
        self.assertEqual(
            participant_output_dir("007", "experiment"),
            Path("data/sub-007/experiment"),
        )
        with self.assertRaisesRegex(ValueError, "Unknown"):
            participant_output_dir("007", "other")

    def test_response_summary_counts_yes_no_and_painful_by_intensity(self):
        records = [
            {"intensity": 0.3, "response": 1},
            {"intensity": 0.3, "response": 0},
            {"intensity": 0.3, "response": 1000},
            {"intensity": 0.5, "response": 1},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = plot_response_summary(
                records,
                Path(temp_dir) / "responses.png",
                "Test response summary",
            )
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)

    def test_vas_boxplot_is_saved_per_intensity(self):
        records = [
            {"intensity": 0.3, "intensity_rating": 25},
            {"intensity": 0.3, "intensity_rating": 45},
            {"intensity": 0.5, "intensity_rating": 80},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = plot_vas_by_intensity(
                records,
                Path(temp_dir) / "vas.png",
                "Test VAS summary",
            )
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)

    def test_summary_plot_rejects_unknown_response_codes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                plot_response_summary(
                    [{"intensity": 0.3, "response": 2}],
                    Path(temp_dir) / "responses.png",
                    "Invalid response",
                )


if __name__ == "__main__":
    unittest.main()
