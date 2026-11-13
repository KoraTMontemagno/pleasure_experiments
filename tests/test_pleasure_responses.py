import importlib
import os
import tempfile
from pathlib import Path
from datetime import datetime
import sys
import types
import unittest
from unittest.mock import patch


class PleasureResponseTests(unittest.TestCase):
    def _run_trial(self, pressed="right", response_mode="pleasure",
                   with_pain_label=False, pressed_before_screen=None,
                   **trial_kwargs):
        response_key_lists = []
        self.waits = []
        # Like PsychoPy: keys stay queued until read; getKeys(keyList) only
        # removes the listed keys; clearEvents() empties the queue.
        queue = [pressed_before_screen] if pressed_before_screen else []
        flushes = []

        def clear_events(eventType=None):
            flushes.append(eventType)
            queue.clear()

        def get_keys(keyList):
            response_key_lists.append(keyList)
            if flushes and not queue and "left" in keyList:
                # the participant answers once the answer screen is shown
                queue.append(pressed if pressed in keyList else "left")
            found = [key for key in queue if key in keyList]
            for key in found:
                queue.remove(key)
            return found

        psychopy = types.ModuleType("psychopy")
        psychopy.core = types.SimpleNamespace(wait=lambda _duration: None)
        psychopy.event = types.SimpleNamespace(getKeys=get_keys,
                                               clearEvents=clear_events)
        psychopy.monitors = types.ModuleType("psychopy.monitors")
        hardware = types.ModuleType("psychopy.hardware")
        hardware.keyboard = types.ModuleType("psychopy.hardware.keyboard")
        psychopy.hardware = hardware
        psychopy.visual = types.SimpleNamespace()

        psychopy_fun = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_fun.core = psychopy.core
        psychopy_fun.event = psychopy.event
        psychopy_fun.monitors = psychopy.monitors
        psychopy_fun.visual = psychopy.visual
        psychopy_fun.psycho_stuff = lambda **_kwargs: None
        psychopy_fun.RESPONSE_LABEL_X = 450
        psychopy_fun.participant_text = lambda key, _language="en": key
        psychopy_fun.VAS_MARKER_COLOR = "darkred"
        repeat_vibration = types.ModuleType(
            "pleasure_experiments.code.repeat_vibration"
        )

        repeat_vibration.vibrate = lambda *_args, **_kwargs: (
            datetime.now(), datetime.now())
        controls_module = types.ModuleType(
            "pleasure_experiments.code.participant_controls"
        )

        class FakeControls:
            def set_context(self, *_args):
                pass

            def process_keys(self, *_args, **_kwargs):
                pass

            def draw(self):
                pass

            def consume_orgasm_reports(self):
                return 0

        controls_module.get_participant_controls = (
            lambda *_args, **_kwargs: FakeControls()
        )

        class FakeStim:
            def __init__(self):
                self.color = "white"
                self.pos = (0, 0)

            def draw(self):
                pass

        class FakeScale(FakeStim):
            def reset(self):
                pass

        class FakeWindow:
            mouseVisible = True

            def flip(self):
                pass

        win = FakeWindow()
        with patch.dict(
            sys.modules,
            {
                "psychopy": psychopy,
                "psychopy.hardware": hardware,
                "psychopy.hardware.keyboard": hardware.keyboard,
                "pleasure_experiments.code.psychopy_fun": psychopy_fun,
                "pleasure_experiments.code.repeat_vibration": repeat_vibration,
                "pleasure_experiments.code.participant_controls": controls_module,
            },
        ):
            sys.modules.pop("pleasure_experiments.code.stimulation_utils", None)
            stimulation_utils = importlib.import_module(
                "pleasure_experiments.code.stimulation_utils"
            )
            # Skip the 15 s minimum trial duration.
            stimulation_utils._wait_with_participant_controls = (
                lambda duration, *_args, **_kwargs: self.waits.append(duration)
            )
            # Record whether the pleasure VAS is shown (fake rating 42).
            self.vas_questions = []
            stimulation_utils.collect_vas = (
                lambda _display, _controls, question:
                self.vas_questions.append(question) or 42.0
            )
            pain_label = FakeStim() if with_pain_label else None
            cwd = os.getcwd()
            temp_dir = self.temp_dir = tempfile.mkdtemp()
            os.chdir(temp_dir)  # the timing CSV is written under data/
            self.addCleanup(os.chdir, cwd)
            result = stimulation_utils.run_trial(
                vibr=0.4,
                display=(
                    win,
                    FakeStim(),            # fixation
                    FakeStim(),            # quality_question
                    FakeStim(),            # no_label
                    FakeStim(),            # yes_label
                    FakeStim(),            # ready_text
                    pain_label,
                    FakeStim(),            # intensity_question
                    FakeScale(),           # intensity_scale
                    FakeStim(),            # intensity_instruction
                ),
                stim_duration=0,
                jitter_wait=0,
                jitter_response=0,
                simulate_device=True,
                response_mode=response_mode,
                subject="response-test",
                language="en",
                **trial_kwargs,
            )
        return result, response_key_lists, pain_label

    def test_binary_response_screen_does_not_offer_down_key(self):
        result, response_key_lists, _ = self._run_trial()

        self.assertEqual(result["response"], 1)
        binary_keys = next(
            key_list
            for key_list in response_key_lists
            if "left" in key_list and "right" in key_list
        )
        self.assertEqual(
            binary_keys,
            ["left", "right", "escape", "o", "e"],
        )
        self.assertFalse(any("down" in keys for keys in response_key_lists))

    def test_no_answer_sets_pleasure_vas_to_zero_without_showing_it(self):
        result, _, _ = self._run_trial(pressed="left",
                                       collect_intensity_rating=True)
        self.assertEqual(result["response"], 0)
        self.assertEqual(result["intensity_rating"], 0.0)
        self.assertTrue(result["vas_auto_zero"])
        self.assertEqual(self.vas_questions, [])  # scale never shown

    def test_yes_answer_still_shows_the_pleasure_vas(self):
        result, _, _ = self._run_trial(pressed="right",
                                       collect_intensity_rating=True)
        self.assertEqual(result["intensity_rating"], 42.0)
        self.assertFalse(result["vas_auto_zero"])
        self.assertEqual(self.vas_questions, ["intensity_question"])

    def test_trial_lasts_at_least_min_isi_plus_minus_jitter(self):
        result, _, _ = self._run_trial(min_isi=10, isi_jitter=1)
        minimum = result["min_trial_duration"]
        self.assertTrue(9 <= minimum <= 11, minimum)
        # the trial itself took well under a second here, so the fixation is
        # kept on for the rest of the planned minimum (last wait of the trial)
        self.assertAlmostEqual(self.waits[-1] + result["trial_duration"], minimum,
                               delta=0.05)
        import csv
        timing = Path(self.temp_dir, "data", "sub-response-test", "experiment",
                      "sub-response-test_trial_timing.csv")
        with timing.open(newline="", encoding="utf-8") as handle:
            row = list(csv.DictReader(handle))[-1]
        self.assertAlmostEqual(float(row["min_trial_duration"]), minimum, places=2)
        self.assertNotEqual(row["trial_duration"], "")

    def test_key_pressed_before_the_answer_screen_is_ignored(self):
        # LEFT pressed during the vibration must not answer the question;
        # only RIGHT, pressed once the answer screen is visible, counts.
        result, _, _ = self._run_trial(pressed="right",
                                       pressed_before_screen="left")
        self.assertEqual(result["response"], 1)

    def test_pleasure_down_key_reports_pain_as_1000(self):
        result, response_key_lists, pain_label = self._run_trial(
            pressed="down", with_pain_label=True
        )

        self.assertEqual(result["response"], 1000)
        self.assertEqual(result["marker_position"], 3)
        # One timing row per stimulus, with planned and actual jitters.
        import csv
        timing = Path(self.temp_dir, "data", "sub-response-test", "experiment",
                      "sub-response-test_trial_timing.csv")
        with timing.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["response"], "1000")
        self.assertEqual(rows[0]["intensity"], "0.4")
        for field in ("jitter_pre_planned", "jitter_pre_actual",
                      "jitter_post_planned", "jitter_post_actual",
                      "stim_onset", "stim_offset", "response_time"):
            self.assertNotEqual(rows[0][field], "", field)
        self.assertEqual(pain_label.color, "lightcoral")
        self.assertTrue(any("down" in keys for keys in response_key_lists))

    def test_annoyance_screen_never_offers_down_key(self):
        result, response_key_lists, _ = self._run_trial(
            pressed="down", response_mode="annoyance", with_pain_label=True
        )

        self.assertEqual(result["response"], 0)
        self.assertFalse(any("down" in keys for keys in response_key_lists))


if __name__ == "__main__":
    unittest.main()
