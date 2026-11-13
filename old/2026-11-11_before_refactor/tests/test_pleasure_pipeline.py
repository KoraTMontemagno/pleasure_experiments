import contextlib
import csv
import importlib
import io
import unittest
import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot

from pleasure_experiments.code.pleasure_pipeline import (
    _load_summary,
    _save_summary,
    _threshold_summary_fields,
    adjust_validation_levels,
    automatic_ceiling,
    automatic_fallback_intensities,
    calculate_safe_ceiling,
    pseudorandom_balanced_order,
    run_final_intensity_validation,
    run_final_pleasure_trials,
    run_final_pleasure_stage,
    run_post_validation_habituation,
    run_pleasure_threshold_stage,
    run_pleasure_pipeline,
    select_initial_validation_levels,
    select_three_intensities,
    select_symmetric_intensity_range,
)


class PleasurePipelineHelperTests(unittest.TestCase):
    def test_validation_levels_depend_on_estimated_pain_threshold_band(self):
        self.assertEqual(
            select_initial_validation_levels(
                0.3, 0.7, 0.1, 1.0, 0.8, 0.1
            ),
            (0.1, 0.2, 0.3),
        )
        self.assertEqual(
            select_initial_validation_levels(
                0.45, 0.35, 0.1, 1.0, 0.8, 0.1
            ),
            (0.2, 0.35, 0.5),
        )
        self.assertEqual(
            select_initial_validation_levels(
                0.5, 0.35, 0.1, 1.0, 0.8, 0.1
            ),
            (0.2, 0.35, 0.5),
        )
        self.assertEqual(
            select_initial_validation_levels(
                0.65, 0.35, 0.1, 1.0, 0.8, 0.1
            ),
            (0.1, 0.45, 0.8),
        )
        self.assertEqual(
            select_initial_validation_levels(
                0.6669039135267083,
                0.4811772382705832,
                0.1,
                1.0,
                0.5,
                0.1,
            ),
            (0.3, 0.4, 0.5),
        )
        with self.assertRaisesRegex(ValueError, "below 0.2"):
            select_initial_validation_levels(
                0.19, 0.35, 0.1, 1.0, 0.8, 0.1
            )

    def test_validation_pain_adjustment_requires_two_pain_responses_at_max(self):
        levels = (0.2, 0.3, 0.4)
        self.assertIsNone(
            adjust_validation_levels(
                levels,
                {"minimum": 0, "threshold": 0, "maximum": 1},
                0.1,
                0.1,
            )
        )
        self.assertEqual(
            adjust_validation_levels(
                levels,
                {"minimum": 0, "threshold": 0, "maximum": 2},
                0.1,
                0.1,
            ),
            (0.1, 0.2, 0.3),
        )

    def test_validation_pain_at_minimum_or_threshold_shifts_all_levels(self):
        self.assertEqual(
            adjust_validation_levels(
                (0.3, 0.4, 0.5),
                {"minimum": 1, "threshold": 0, "maximum": 0},
                0.1,
                0.1,
            ),
            (0.2, 0.3, 0.4),
        )
        self.assertEqual(
            adjust_validation_levels(
                (0.3, 0.4, 0.5),
                {"minimum": 0, "threshold": 1, "maximum": 0},
                0.1,
                0.1,
            ),
            (0.2, 0.3, 0.4),
        )

    def test_automatic_ceiling_uses_half_floor_within_device_bounds(self):
        self.assertEqual(automatic_ceiling(0.3, 0.1, 1.0), 0.5)
        self.assertEqual(automatic_ceiling(0.7, 0.1, 1.0), 0.7)
        self.assertEqual(automatic_ceiling(0.3, 0.1, 0.4), 0.4)

    def test_four_pain_free_maximum_trials_force_configured_ceiling(self):
        class FakeWindow:
            def close(self):
                pass

        summary = {
            "minimum_intensity": 0.1,
            "maximum_intensity": 1.0,
            "annoyance_threshold": 0.2,
            "annoyance_threshold_std": 0.05,
            "annoyance_pain_free_maximum_stop": True,
            "annoyance_pain_free_maximum_trials": 4,
        }
        review_calls = []
        threshold_calls = []
        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )

        def fake_review(*_args, **kwargs):
            review_calls.append(kwargs)
            return True, kwargs.get("threshold")

        psychopy_module.show_break_review = fake_review
        threshold_module = types.ModuleType(
            "pleasure_experiments.code.thresholding"
        )

        def fake_threshold(**kwargs):
            threshold_calls.append(kwargs)
            return {
                "threshold": 0.6,
                "estimated_threshold": 0.6,
                "manually_overridden": False,
                "std": 0.1,
            }

        threshold_module.run_threshold = fake_threshold

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                _save_summary("ceiling", summary)
                with patch.dict(
                    sys.modules,
                    {
                        "pleasure_experiments.code.psychopy_fun": psychopy_module,
                        "pleasure_experiments.code.thresholding": threshold_module,
                    },
                ):
                    result = run_pleasure_threshold_stage(
                        subject="ceiling",
                        ntrials=10,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        display=(FakeWindow(),),
                    )
                saved_summary = _load_summary("ceiling")
            finally:
                os.chdir(original_dir)

        self.assertEqual(result["threshold"], 0.6)
        self.assertEqual(threshold_calls[0]["max_vibr"], 1.0)
        self.assertIsNone(review_calls[0]["threshold"])
        self.assertEqual(saved_summary["safe_ceiling"], 1.0)
        self.assertEqual(
            saved_summary["safe_ceiling_override_reason"],
            "four_pain_free_trials_at_maximum",
        )

    def test_automatic_fallback_uses_fixed_levels_within_device_range(self):
        self.assertEqual(
            automatic_fallback_intensities(0.1, 1.0),
            (0.2, 0.3, 0.4),
        )
        with self.assertRaisesRegex(ValueError, "outside the configured"):
            automatic_fallback_intensities(0.25, 1.0)

    def test_automatic_final_stage_selects_levels_from_pain_threshold_band(self):
        display = (object(),) * 11
        summary = {
            "minimum_intensity": 0.1,
            "maximum_intensity": 1.0,
            "safe_ceiling": 0.3,
            "annoyance_threshold": 0.65,
            "pleasure_threshold": 0.15,
            "pleasure_threshold_std": 0.1,
        }
        validation_calls = []
        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_module.participant_text = lambda key, language: {
            "pleasure_question": "Was this vibration pleasurable?",
            "final_ready": "Press SPACE or ENTER when ready.",
        }[key]
        psychopy_module.show_break_review = (
            lambda *args, **kwargs: (True, kwargs.get("threshold"))
        )
        vas_practice_calls = []
        psychopy_module.run_vas_practice = (
            lambda *args, **kwargs: vas_practice_calls.append(kwargs)
        )
        stimulation_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )
        stimulation_module.run_trial = lambda **kwargs: {}

        def fake_validation(**kwargs):
            validation_calls.append(kwargs)
            levels = (
                kwargs["initial_minimum"],
                kwargs["initial_threshold"],
                kwargs["initial_maximum"],
            )
            return {
                "validated_minimum": levels[0],
                "validated_threshold": levels[1],
                "validated_maximum": levels[2],
                "levels": levels,
                "trials": [],
                "log_path": "validation.csv",
                "validation_passed": False,
                "accepted_by_pleasure": True,
                "validation_cycles": 2,
            }

        with patch.dict(
            sys.modules,
            {
                "pleasure_experiments.code.psychopy_fun": psychopy_module,
                "pleasure_experiments.code.stimulation_utils": stimulation_module,
            },
        ), patch(
            "pleasure_experiments.code.pleasure_pipeline._load_summary",
            return_value=summary,
        ), patch(
            "pleasure_experiments.code.pleasure_pipeline._save_summary"
        ), patch(
            "pleasure_experiments.code.pleasure_pipeline.run_final_intensity_validation",
            side_effect=fake_validation,
        ), patch(
            "pleasure_experiments.code.pleasure_pipeline.run_post_validation_habituation",
            return_value={
                "trials": [],
                "log_path": "habituation.csv",
                "safety_stop": False,
            },
        ), patch(
            "pleasure_experiments.code.pleasure_pipeline.run_final_pleasure_trials",
            return_value=[],
        ) as final_trials_mock:
            result = run_final_pleasure_stage(
                subject="test",
                intensity_step=0.05,
                final_trials_per_intensity=1,
                stim_duration=0.5,
                jitter_wait=0.5,
                jitter_response=0.5,
                display=display,
                automatic_mode=True,
                return_details=True,
            )

        self.assertEqual(len(vas_practice_calls), 1)
        self.assertEqual(
            tuple(
                validation_calls[0][key]
                for key in (
                    "initial_minimum",
                    "initial_threshold",
                    "initial_maximum",
                )
            ),
            (0.1, 0.3, 0.5),
        )
        self.assertEqual(
            final_trials_mock.call_args.kwargs["n_trials"],
            3,
        )
        self.assertEqual(
            final_trials_mock.call_args.kwargs["break_interval"],
            10,
        )
        self.assertTrue(validation_calls[0]["automatic_mode"])
        self.assertIsNotNone(result)
        self.assertFalse(result["validation_passed"])
        self.assertTrue(result["validation_accepted_by_pleasure"])

    def test_automatic_break_review_skips_terminal_input(self):
        created_texts = []
        participant_keys = []

        class FakeTextStim:
            def __init__(self, _win, text, **_kwargs):
                self.text = text
                created_texts.append(self)

            def draw(self):
                pass

        class FakeWindow:
            def flip(self):
                pass

        psychopy = types.ModuleType("psychopy")
        for component in ("core", "event", "monitors"):
            setattr(psychopy, component, types.ModuleType(f"psychopy.{component}"))
        psychopy.event.waitKeys = lambda **kwargs: (
            participant_keys.append(kwargs) or ["return"]
        )
        psychopy.visual = types.SimpleNamespace(TextStim=FakeTextStim)

        with patch.dict(sys.modules, {"psychopy": psychopy}):
            psycho_module = importlib.import_module(
                "pleasure_experiments.code.psychopy_fun"
            )
            with patch("builtins.input", side_effect=AssertionError("unexpected input")):
                accepted, selected = psycho_module.show_break_review(
                    FakeWindow(),
                    title="Automatic review",
                    message="Accepted automatically",
                    threshold=0.5,
                    minimum=0.1,
                    maximum=1.0,
                    automatic_mode=True,
                )

        self.assertTrue(accepted)
        self.assertEqual(selected, 0.5)
        self.assertEqual(len(created_texts), 6)
        self.assertEqual(
            participant_keys,
            [{"keyList": ["return", "escape", "o", "e"]}],
        )

    def test_break_review_keeps_details_off_participant_display(self):
        created_texts = []
        participant_keys = []

        class FakeTextStim:
            def __init__(self, _win, text, **_kwargs):
                self.text = text
                created_texts.append(self)

            def draw(self):
                pass

        class FakeWindow:
            def flip(self):
                pass

        psychopy = types.ModuleType("psychopy")
        for component in ("core", "event", "monitors"):
            setattr(psychopy, component, types.ModuleType(f"psychopy.{component}"))
        psychopy.event.waitKeys = lambda **kwargs: (
            participant_keys.append(kwargs) or ["return"]
        )
        psychopy.visual = types.SimpleNamespace(TextStim=FakeTextStim)

        with patch.dict(sys.modules, {"psychopy": psychopy}):
            psycho_module = importlib.import_module(
                "pleasure_experiments.code.psychopy_fun"
            )
            with patch(
                "builtins.input",
                side_effect=["m", "0.5"],
            ) as experimenter_input:
                accepted, threshold = psycho_module.show_break_review(
                    FakeWindow(),
                    title="Annoyance threshold review",
                    message="Estimated threshold: 0.600",
                    threshold=0.6,
                    minimum=0.1,
                    maximum=0.8,
                )

        self.assertTrue(accepted)
        self.assertEqual(threshold, 0.5)
        self.assertEqual(
            created_texts[0].text,
            "You can take a break if you want.\n"
            "Press ENTER when you are ready to continue.",
        )
        self.assertIn("Estimated threshold: 0.600", experimenter_input.call_args_list[0].args[0])
        self.assertEqual(len(participant_keys), 1)
        self.assertEqual(len(created_texts), 6)

    def test_symmetric_range_lowers_threshold_if_max_is_too_close(self):
        minimum, adjusted_threshold, maximum = select_symmetric_intensity_range(
            threshold=0.5,
            maximum_intensity=0.55,
            minimum_allowed=0.1,
            adjustment_step=0.1,
        )

        self.assertAlmostEqual(adjusted_threshold, 0.45)
        self.assertAlmostEqual(minimum, 0.35)
        self.assertAlmostEqual(maximum, 0.55)
        self.assertAlmostEqual(
            (adjusted_threshold - minimum),
            (maximum - adjusted_threshold),
        )

    def test_symmetric_range_uses_one_adjustment_step_around_threshold(self):
        minimum, threshold, maximum = select_symmetric_intensity_range(
            threshold=0.36,
            maximum_intensity=0.65,
            minimum_allowed=0.1,
            adjustment_step=0.1,
        )

        self.assertAlmostEqual(minimum, 0.26)
        self.assertAlmostEqual(threshold, 0.36)
        self.assertAlmostEqual(maximum, 0.46)

    def test_symmetric_range_rejects_minimum_below_configured_limit(self):
        with self.assertRaisesRegex(ValueError, "leave room"):
            select_symmetric_intensity_range(
                threshold=0.15,
                maximum_intensity=0.65,
                minimum_allowed=0.1,
                adjustment_step=0.1,
            )

    def test_validation_interleaves_values_and_restarts_six_trial_cycle(self):
        class FakeText:
            text = ""

        responses = iter([1, 1, 1000, 1, 1, 1000] + [1] * 6)
        presented = []
        vas_enabled = []
        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_module.show_break_review = lambda *args, **kwargs: (True, None)
        stimulation_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )

        def fake_run_trial(**kwargs):
            presented.append(kwargs["vibr"])
            vas_enabled.append(kwargs["collect_intensity_rating"])
            return {"response": next(responses)}

        stimulation_module.run_trial = fake_run_trial
        display = (
            object(),
            object(),
            object(),
            FakeText(),
            object(),
            object(),
            FakeText(),
            object(),
            FakeText(),
            FakeText(),
            FakeText(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {
                        "pleasure_experiments.code.psychopy_fun": psychopy_module,
                        "pleasure_experiments.code.stimulation_utils": stimulation_module,
                    },
                ), patch(
                    "pleasure_experiments.code.pleasure_pipeline.random.shuffle",
                    side_effect=lambda values: None,
                ), contextlib.redirect_stdout(io.StringIO()) as experimenter_log:
                    result = run_final_intensity_validation(
                        subject="test",
                        display=display,
                        minimum_allowed=0.1,
                        initial_minimum=0.3,
                        initial_threshold=0.5,
                        initial_maximum=0.7,
                        adjustment_step=0.1,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                    )
                experimenter_output = experimenter_log.getvalue()
                log_exists = os.path.isfile(
                    os.path.join(temp_dir, result["log_path"])
                )
                response_plot_exists = os.path.isfile(
                    os.path.join(
                        temp_dir,
                        "data",
                        "sub-test",
                        "validation",
                        "sub-test_pleasure_validation_cycle-02_responses.png",
                    )
                )
            finally:
                os.chdir(original_dir)

        self.assertCountEqual(presented[:3], [0.3, 0.5, 0.7])
        self.assertCountEqual(presented[3:6], [0.3, 0.5, 0.7])
        self.assertCountEqual(presented[6:9], [0.4, 0.5, 0.6])
        self.assertCountEqual(presented[9:12], [0.4, 0.5, 0.6])
        self.assertEqual(len(presented), 12)
        self.assertEqual(vas_enabled, [False] * 12)
        self.assertEqual(result["levels"], (0.4, 0.5, 0.6))
        self.assertEqual(result["validated_maximum"], 0.6)
        self.assertTrue(log_exists)
        self.assertTrue(response_plot_exists)
        self.assertIn("Validation run 1/2 | Trial 1/6", experimenter_output)
        self.assertIn("VAS=not collected", experimenter_output)

    def test_validation_stops_at_device_floor_without_key_level_pleasure(self):
        class FakeText:
            text = ""

        responses = iter([0, 1000, 0, 0, 0, 0])
        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_module.show_break_review = lambda *args, **kwargs: (True, None)
        stimulation_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )
        stimulation_module.run_trial = lambda **kwargs: {
            "response": next(responses)
        }
        display = (
            object(),
            object(),
            object(),
            FakeText(),
            object(),
            object(),
            FakeText(),
            object(),
            FakeText(),
            FakeText(),
            FakeText(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {
                        "pleasure_experiments.code.psychopy_fun": psychopy_module,
                        "pleasure_experiments.code.stimulation_utils": (
                            stimulation_module
                        ),
                    },
                ), patch(
                    "pleasure_experiments.code.pleasure_pipeline.random.shuffle",
                    side_effect=lambda values: None,
                ):
                    result = run_final_intensity_validation(
                        subject="floor",
                        display=display,
                        minimum_allowed=0.1,
                        initial_minimum=0.15,
                        initial_threshold=0.25,
                        initial_maximum=0.35,
                        adjustment_step=0.1,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                    )
                log_path = os.path.join(
                    temp_dir,
                    "data",
                    "sub-floor",
                    "validation",
                    "sub-floor_pleasure_validation_trials.csv",
                )
                with open(log_path, encoding="utf-8") as log_file:
                    logged_trials = log_file.readlines()
                response_plot_exists = os.path.isfile(
                    os.path.join(
                        temp_dir,
                        "data",
                        "sub-floor",
                        "validation",
                        "sub-floor_pleasure_validation_cycle-01_responses.png",
                    )
                )
            finally:
                os.chdir(original_dir)

        self.assertIsNone(result)
        self.assertEqual(len(logged_trials), 7)
        self.assertTrue(response_plot_exists)

    def test_final_experiment_saves_response_and_vas_plots_in_experiment_folder(self):
        class FakeWindow:
            def flip(self):
                pass

        class FakeText:
            text = ""

            def draw(self):
                pass

        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_module.participant_text = lambda key, language: {
            "pleasure_question": "Was this vibration pleasurable?",
            "final_ready": "Press SPACE or ENTER when ready.",
        }[key]
        psychopy_module.show_break_review = lambda *args, **kwargs: (True, None)
        psychopy_module.event = types.SimpleNamespace(
            waitKeys=lambda **_kwargs: ["return"]
        )
        controls_module = types.ModuleType(
            "pleasure_experiments.code.participant_controls"
        )
        controls_module.get_participant_controls = (
            lambda *_args, **_kwargs: types.SimpleNamespace(
                set_context=lambda *_args: None,
                draw=lambda: None,
                process_keys=lambda *_args, **_kwargs: None,
            )
        )
        stimulation_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )
        trial_responses = iter([
            {
                "response": 1000,
                "intensity_rating": 20.0,
                "orgasm_reports": 1,
            },
            {"response": 1, "intensity_rating": 70.0},
            {"response": 0, "intensity_rating": 90.0},
        ])
        stimulation_module.run_trial = lambda **_kwargs: next(trial_responses)
        display = (
            FakeWindow(),
            object(),
            object(),
            FakeText(),
            object(),
            object(),
            FakeText(),
            object(),
            FakeText(),
            FakeText(),
            FakeText(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {
                        "pleasure_experiments.code.psychopy_fun": psychopy_module,
                        "pleasure_experiments.code.stimulation_utils": (
                            stimulation_module
                        ),
                        "pleasure_experiments.code.participant_controls": (
                            controls_module
                        ),
                    },
                ), contextlib.redirect_stdout(io.StringIO()) as experimenter_log:
                    records = run_final_pleasure_trials(
                        subject="final",
                        levels=(0.2, 0.3, 0.4),
                        n_trials=3,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                        seed=5,
                        display=display,
                    )
                experimenter_output = experimenter_log.getvalue()
                output_dir = Path(temp_dir) / "data/sub-final/experiment"
                output_exists = {
                    name: (output_dir / name).is_file()
                    for name in (
                        "sub-final_pleasure_final_trials.csv",
                        "sub-final_pleasure_experiment_responses.png",
                        "sub-final_pleasure_experiment_vas.png",
                    )
                }
                with (
                    output_dir
                    .joinpath("sub-final_pleasure_final_trials.csv")
                    .open(encoding="utf-8", newline="") as log_file
                ):
                    logged_trials = list(csv.DictReader(log_file))
            finally:
                os.chdir(original_dir)

        self.assertEqual(len(records), 3)
        self.assertIn("Final experiment | Trial 1/3", experimenter_output)
        self.assertIn("VAS=70/100", experimenter_output)
        self.assertIn("VAS=90/100", experimenter_output)
        self.assertEqual(logged_trials[0]["orgasm_reports"], "1")
        self.assertTrue(output_exists["sub-final_pleasure_final_trials.csv"])
        self.assertTrue(
            output_exists["sub-final_pleasure_experiment_responses.png"]
        )
        self.assertTrue(output_exists["sub-final_pleasure_experiment_vas.png"])
        self.assertIn("stimulus_type", logged_trials[0])
        self.assertTrue(
            all(
                row["stimulus_type"]
                == {
                    0.2: "low",
                    0.3: "medium",
                    0.4: "high",
                }[float(row["intensity"])]
                for row in logged_trials
            )
        )

    def test_final_experiment_break_interval_is_configurable(self):
        class FakeWindow:
            def flip(self):
                pass

        class FakeStim:
            def __init__(self):
                self.text = ""

            def draw(self):
                pass

        break_calls = []
        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_module.participant_text = lambda key, language: {
            "pleasure_question": "Was this vibration pleasurable?",
            "final_ready": "Press SPACE or ENTER when ready.",
        }[key]
        psychopy_module.show_break_review = (
            lambda *args, **kwargs: (
                break_calls.append(kwargs.get("trial_number")) or True,
                None,
            )
        )
        psychopy_module.event = types.SimpleNamespace(
            waitKeys=lambda **_kwargs: ["return"]
        )
        controls_module = types.ModuleType(
            "pleasure_experiments.code.participant_controls"
        )
        controls_module.get_participant_controls = (
            lambda *_args, **_kwargs: types.SimpleNamespace(
                set_context=lambda *_args: None,
                draw=lambda: None,
                process_keys=lambda *_args, **_kwargs: None,
            )
        )
        stimulation_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )
        stimulation_module.run_trial = lambda **_kwargs: {
            "response": 0,
            "intensity_rating": 50,
        }
        display = (
            FakeWindow(),
            object(),
            object(),
            FakeStim(),
            object(),
            object(),
            FakeStim(),
            object(),
            object(),
            object(),
            object(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {
                        "pleasure_experiments.code.psychopy_fun": psychopy_module,
                        "pleasure_experiments.code.stimulation_utils": (
                            stimulation_module
                        ),
                        "pleasure_experiments.code.participant_controls": (
                            controls_module
                        ),
                    },
                ), contextlib.redirect_stdout(io.StringIO()):
                    records = run_final_pleasure_trials(
                        subject="breaks",
                        levels=(0.2, 0.3, 0.4),
                        n_trials=6,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                        seed=5,
                        display=display,
                        break_interval=2,
                    )
            finally:
                os.chdir(original_dir)

        self.assertEqual(len(records), 6)
        self.assertEqual(break_calls, [2, 4])

    def test_failed_validation_uses_at_most_two_cycles_for_pleasure_acceptance(self):
        class FakeText:
            text = ""

        one_cycle = [1, 1, 1000, 1, 1, 1]
        responses = iter(one_cycle + one_cycle)
        presented = []
        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_module.show_break_review = lambda *args, **kwargs: (True, None)
        stimulation_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )

        def fake_run_trial(**kwargs):
            presented.append(kwargs["vibr"])
            return {"response": next(responses)}

        stimulation_module.run_trial = fake_run_trial
        display = (
            object(),
            object(),
            object(),
            FakeText(),
            object(),
            object(),
            FakeText(),
            object(),
            FakeText(),
            FakeText(),
            FakeText(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {
                        "pleasure_experiments.code.psychopy_fun": psychopy_module,
                        "pleasure_experiments.code.stimulation_utils": (
                            stimulation_module
                        ),
                    },
                ), patch(
                    "pleasure_experiments.code.pleasure_pipeline.random.shuffle",
                    side_effect=lambda values: None,
                ):
                    result = run_final_intensity_validation(
                        subject="two-runs",
                        display=display,
                        minimum_allowed=0.1,
                        initial_minimum=0.2,
                        initial_threshold=0.3,
                        initial_maximum=0.4,
                        adjustment_step=0.1,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                    )
            finally:
                os.chdir(original_dir)

        self.assertEqual(len(presented), 12)
        self.assertEqual(result["levels"], (0.2, 0.3, 0.4))
        self.assertFalse(result["validation_passed"])
        self.assertTrue(result["accepted_by_pleasure"])
        self.assertEqual(result["validation_cycles"], 2)

    def test_post_validation_habituation_collects_three_vas_ratings(self):
        trial_calls = []
        psychopy_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )

        def fake_run_trial(**kwargs):
            trial_calls.append(kwargs)
            return {"response": 1, "intensity_rating": 52.0}

        psychopy_module.run_trial = fake_run_trial
        display = (
            object(),
            object(),
            object(),
            types.SimpleNamespace(text=""),
            object(),
            object(),
            object(),
            object(),
            object(),
            object(),
            object(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {"pleasure_experiments.code.stimulation_utils": psychopy_module},
                ), contextlib.redirect_stdout(io.StringIO()) as experimenter_log:
                    result = run_post_validation_habituation(
                        subject="test",
                        display=display,
                        intensities=(0.2, 0.5, 0.8),
                        seed=3,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                    )
                experimenter_output = experimenter_log.getvalue()
                log_exists = os.path.isfile(
                    os.path.join(temp_dir, result["log_path"])
                )
                self.assertEqual(
                    Path(result["log_path"]).parent,
                    Path("data/sub-test/experiment"),
                )
            finally:
                os.chdir(original_dir)

        self.assertEqual(len(result["trials"]), 3)
        # One trial per final intensity, in shuffled order.
        self.assertEqual(sorted(call["vibr"] for call in trial_calls),
                         [0.2, 0.5, 0.8])
        self.assertEqual(
            [call["collect_intensity_rating"] for call in trial_calls],
            [True] * 3,
        )
        self.assertFalse(result["safety_stop"])
        self.assertTrue(log_exists)
        self.assertIn(
            "Post-validation habituation | Trial 1/3", experimenter_output
        )
        self.assertIn("VAS=52/100", experimenter_output)

    def test_post_validation_habituation_continues_after_pain_response(self):
        trial_calls = []
        stimulation_module = types.ModuleType(
            "pleasure_experiments.code.stimulation_utils"
        )

        def fake_run_trial(**kwargs):
            trial_calls.append(kwargs)
            return {"response": 1000, "intensity_rating": 35.0}

        stimulation_module.run_trial = fake_run_trial
        display = (
            object(),
            object(),
            object(),
            types.SimpleNamespace(text=""),
            object(),
            object(),
            object(),
            object(),
            object(),
            object(),
            object(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {"pleasure_experiments.code.stimulation_utils": stimulation_module},
                ):
                    result = run_post_validation_habituation(
                        subject="test",
                        display=display,
                        intensities=(0.2, 0.5, 0.8),
                        seed=3,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                    )
            finally:
                os.chdir(original_dir)

        self.assertEqual(len(result["trials"]), 3)
        self.assertFalse(result["safety_stop"])
        self.assertEqual(len(trial_calls), 3)

    def test_pipeline_returns_levels_without_reloading_final_summary_field(self):
        class FakeWindow:
            def close(self):
                pass

        summary = {
            "minimum_intensity": 0.1,
            "safe_ceiling": 0.8,
            "pleasure_threshold": 0.55,
            "pleasure_threshold_std": 0.1,
        }
        expected_levels = select_three_intensities(
            threshold=summary["pleasure_threshold"],
            uncertainty=summary["pleasure_threshold_std"],
            minimum_intensity=summary["minimum_intensity"],
            safe_ceiling=summary["safe_ceiling"],
            intensity_step=0.05,
        )

        with (
            patch(
                "pleasure_experiments.code.pleasure_pipeline._create_display",
                return_value=(FakeWindow(),),
            ),
            patch(
                "pleasure_experiments.code.pleasure_pipeline.run_annoyance_stage",
                return_value={"threshold": 0.7},
            ),
            patch(
                "pleasure_experiments.code.pleasure_pipeline.run_pleasure_threshold_stage",
                return_value={"threshold": 0.55},
            ),
            patch(
                "pleasure_experiments.code.pleasure_pipeline._load_summary",
                return_value=summary,
            ),
            patch(
                "pleasure_experiments.code.pleasure_pipeline.run_final_pleasure_stage",
                return_value={
                    "trials": [{"trial": 1}],
                    "final_intensities": expected_levels,
                },
            ),
        ):
            result = run_pleasure_pipeline(
                subject="test",
                annoyance_ntrials=1,
                pleasure_ntrials=1,
                habituation=0,
                stim_duration=1,
                jitter_wait=0,
                jitter_response=0,
                intensity_step=0.05,
                final_trials_per_intensity=1,
            )

        self.assertEqual(result["final_intensities"], expected_levels)
        self.assertEqual(result["final_trials"], [{"trial": 1}])

    def test_threshold_summary_preserves_estimate_and_manual_choice(self):
        fields = _threshold_summary_fields(
            "pleasure",
            {
                "threshold": 0.46,
                "estimated_threshold": 0.52,
                "manually_overridden": True,
                "std": 0.08,
            },
        )

        self.assertEqual(fields["pleasure_threshold"], 0.46)
        self.assertEqual(fields["pleasure_threshold_estimated"], 0.52)
        self.assertTrue(fields["pleasure_threshold_manually_overridden"])
        self.assertEqual(fields["pleasure_threshold_std"], 0.08)

    def test_stage_summary_can_be_saved_and_loaded_between_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                expected = {
                    "subject": "test",
                    "annoyance_threshold": 0.7,
                    "annoyance_threshold_std": 0.1,
                    "minimum_intensity": 0.1,
                    "maximum_intensity": 1.0,
                }
                _save_summary("test", expected)

                with open(
                    "data/sub-test/pleasure/sub-test_pleasure_pipeline_summary.json",
                    encoding="utf-8",
                ) as summary_file:
                    self.assertEqual(json.load(summary_file), expected)
                self.assertEqual(_load_summary("test"), expected)
            finally:
                os.chdir(original_dir)

    def test_loading_missing_summary_explains_required_previous_stage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with self.assertRaisesRegex(FileNotFoundError, "Run the earlier stage"):
                    _load_summary("missing")
            finally:
                os.chdir(original_dir)

    def test_safe_ceiling_uses_configured_standard_deviation_margin(self):
        ceiling = calculate_safe_ceiling(
            threshold=0.8,
            uncertainty=0.1,
            safety_margin_sd=1,
            minimum_intensity=0.1,
            maximum_intensity=1.0,
        )

        self.assertAlmostEqual(ceiling, 0.7)

    def test_safe_ceiling_is_limited_to_device_maximum(self):
        ceiling = calculate_safe_ceiling(
            threshold=1.2,
            uncertainty=0.1,
            safety_margin_sd=1,
            minimum_intensity=0.1,
            maximum_intensity=1.0,
        )

        self.assertAlmostEqual(ceiling, 1.0)

    def test_safe_ceiling_rejects_range_that_is_too_low(self):
        with self.assertRaisesRegex(ValueError, "insufficient range"):
            calculate_safe_ceiling(
                threshold=0.15,
                uncertainty=0.1,
                safety_margin_sd=1,
                minimum_intensity=0.1,
                maximum_intensity=1.0,
            )

    def test_three_levels_are_distinct_and_below_safe_ceiling(self):
        levels = select_three_intensities(
            threshold=0.72,
            uncertainty=0.12,
            minimum_intensity=0.1,
            safe_ceiling=0.8,
            intensity_step=0.05,
        )

        self.assertEqual(len(set(levels)), 3)
        self.assertEqual(tuple(sorted(levels)), levels)
        self.assertLessEqual(max(levels), 0.8)
        self.assertTrue(all(0.1 <= level for level in levels))

    def test_intensity_selection_keeps_three_levels_when_plus_two_sd_is_capped(self):
        levels = select_three_intensities(
            threshold=0.75,
            uncertainty=0.2,
            minimum_intensity=0.1,
            safe_ceiling=0.8,
            intensity_step=0.05,
        )

        self.assertEqual(len(set(levels)), 3)
        self.assertLessEqual(max(levels), 0.8)

    def test_final_order_is_balanced_and_has_no_adjacent_repeats(self):
        levels = (0.3, 0.5, 0.7)
        order = pseudorandom_balanced_order(levels, 30, seed=12)

        self.assertEqual(len(order), 30)
        self.assertEqual([order.count(level) for level in levels], [10, 10, 10])
        self.assertTrue(all(left != right for left, right in zip(order, order[1:])))

    def test_final_order_requires_balanced_trial_count(self):
        with self.assertRaisesRegex(ValueError, "multiple of three"):
            pseudorandom_balanced_order((0.2, 0.4, 0.6), 29, seed=1)


if __name__ == "__main__":
    unittest.main()
