import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pleasure_experiments.code import experiment_progress as progress


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class ExperimentProgressTests(unittest.TestCase):
    def test_steps_follow_saved_results(self):
        with tempfile.TemporaryDirectory() as root:
            state = progress.progress("7", 10, root=root)
            self.assertFalse(state["any_data"])
            self.assertEqual(progress.available_steps(state),
                             [progress.FULL, progress.ANNOYANCE])
            self.assertEqual(progress.next_step(state), progress.FULL)

            summary_path = (Path(root) / "sub-7" / "pleasure"
                            / "sub-7_pleasure_pipeline_summary.json")
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(json.dumps(
                {"annoyance_threshold": 0.6, "safe_ceiling": 0.5}))
            state = progress.progress("7", 10, root=root)
            self.assertEqual(progress.next_step(state), progress.PLEASURE)
            self.assertNotIn(progress.FINAL, progress.available_steps(state))

            # both thresholds, no validation yet: validation is next, the
            # final experiment is not offered
            summary_path.write_text(json.dumps({
                "annoyance_threshold": 0.6, "safe_ceiling": 0.5,
                "pleasure_threshold": 0.3}))
            state = progress.progress("7", 10, root=root)
            self.assertEqual(progress.next_step(state), progress.VALIDATION)
            self.assertNotIn(progress.FINAL, progress.available_steps(state))
            self.assertIn("Validation: not done", progress.progress_text(state))

            summary_path.write_text(json.dumps({
                "annoyance_threshold": 0.6, "safe_ceiling": 0.5,
                "pleasure_threshold": 0.3,
                "final_intensities": [0.2, 0.3, 0.4],
            }))
            _write_csv(progress.table_path("7", "final", root),
                       [{"trial": 1, "intensity": 0.2, "response": 1000}])
            state = progress.progress("7", 10, root=root)
            self.assertEqual(progress.next_step(state), progress.FINAL)
            self.assertIn(progress.VALIDATION, progress.available_steps(state))
            self.assertEqual(state["final_trials"], 1)
            text = progress.progress_text(state)
            self.assertIn("Pleasure threshold: 0.300", text)
            self.assertIn("Final trials saved: 1/30", text)

    def test_parse_review_matches_show_break_review_prompt(self):
        # Built exactly as psychopy_fun.show_break_review builds it.
        title, message = "Annoyance threshold", "Estimated threshold: 0.600\nSafe ceiling: 0.500"
        options = "ENTER: continue, Q: stop" + ", M: enter a manual safe ceiling"
        prompt = f"\nExperimenter review — {title}\n{message}\n{options}: "

        review = progress.parse_review(prompt)

        self.assertEqual(review["title"], title)
        self.assertEqual(review["message"], message)
        self.assertEqual(review["manual_label"], "safe ceiling")

        no_manual = progress.parse_review(
            "\nExperimenter review — Break\nNext block.\nENTER: continue, Q: stop: ")
        self.assertIsNone(no_manual["manual_label"])
        self.assertIsNone(progress.parse_review("Enter subject number: "))


class LauncherInputTests(unittest.TestCase):
    def test_prompts_are_routed_to_the_right_dialog(self):
        import os
        cwd = os.getcwd()
        try:
            from pleasure_experiments import launcher
        finally:
            os.chdir(cwd)

        gui_input = launcher.make_input("12", "3")
        with patch("builtins.print"):
            self.assertEqual(gui_input("Welcome! Select what to run:\n"), "3")
            self.assertEqual(gui_input("Now input subject number : "), "12")
            with patch.object(launcher, "ask_review", return_value="m") as review:
                answer = gui_input(
                    "\nExperimenter review — Pleasure threshold\n"
                    "Estimated threshold: 0.300\n"
                    "ENTER: continue, Q: stop, M: enter a manual threshold: ")
            self.assertEqual(answer, "m")
            self.assertEqual(review.call_args.args[0]["manual_label"], "threshold")
            with patch.object(launcher, "ask_manual_value", return_value="0.25"):
                self.assertEqual(gui_input(
                    "Enter threshold (0.100–0.500), or press ENTER to keep "
                    "the estimate: "), "0.25")
            with patch.object(launcher, "ask_yes_no", return_value="y") as yes_no:
                self.assertEqual(gui_input(
                    "\nData already exists for this participant.\n"
                    "Do you want to proceed? [y/n]: "), "y")
            yes_no.assert_called_once()


if __name__ == "__main__":
    unittest.main()
