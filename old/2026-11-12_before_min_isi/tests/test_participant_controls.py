import csv
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class ParticipantControlsTests(unittest.TestCase):
    def test_orgasm_pause_and_quit_are_recorded(self):
        class FakeStim:
            def __init__(self, _win, text, **kwargs):
                self.text = text
                self.options = kwargs

            def draw(self):
                pass

        class FakeWindow:
            def flip(self):
                pass

        class FakeFixation:
            def draw(self):
                pass

        pause_key_calls = []
        # S (pause) -> RIGHT (resume) -> E then RIGHT (confirm quit)
        scripted_keys = iter([["s"], ["right"], ["right"]])
        psychopy = types.ModuleType("psychopy")
        psychopy.event = types.SimpleNamespace(
            waitKeys=lambda **kwargs: (
                pause_key_calls.append(kwargs) or next(scripted_keys)
            )
        )
        psychopy.visual = types.SimpleNamespace(TextStim=FakeStim)
        psychopy_fun = types.ModuleType(
            "pleasure_experiments.code.psychopy_fun"
        )
        psychopy_fun.TEXT_COLOR = (226, 216, 206)
        psychopy_fun.font_type = "Test Font"
        psychopy_fun.fontsize = 120
        psychopy_fun.participant_text = lambda key, language: {
            "control_banner": "Premi O se hai avuto un orgasmo\nPremi E se vuoi interrompere",
            "pause_message": "Orgasmo registrato.\nQuando vuoi, premi S per continuare.",
            "resume_question": "Orgasmo terminato.\nVuoi riprendere?",
            "quit_confirm": "Vuoi davvero uscire?",
        }[key]

        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                with patch.dict(
                    sys.modules,
                    {
                        "psychopy": psychopy,
                        "pleasure_experiments.code.psychopy_fun": psychopy_fun,
                    },
                ):
                    from pleasure_experiments.code.participant_controls import (
                        ParticipantControls,
                    )

                    controls = ParticipantControls(
                        FakeWindow(),
                        subject="participant-1",
                        language="it",
                    )
                    controls.set_context("final experiment", 4)
                    controls.process_keys(["o"], fixation=FakeFixation())
                    self.assertEqual(controls.consume_orgasm_reports(), 1)
                    with self.assertRaisesRegex(
                        KeyboardInterrupt, "chose to quit"
                    ):
                        controls.process_keys(["e"])
                with Path(
                    "data/sub-participant-1/experiment/"
                    "sub-participant-1_participant_events.csv"
                ).open(encoding="utf-8", newline="") as event_file:
                    events = list(csv.DictReader(event_file))
                with Path(
                    "data/sub-participant-1/experiment/"
                    "sub-participant-1_orgasm_events.csv"
                ).open(encoding="utf-8", newline="") as orgasm_file:
                    orgasms = list(csv.DictReader(orgasm_file))
            finally:
                os.chdir(original_dir)

        self.assertEqual(
            [row["event"] for row in events],
            [
                "orgasm_reported",
                "orgasm_ended",
                "participant_resumed",
                "quit_requested",
                "participant_quit",
            ],
        )
        self.assertEqual(events[0]["phase"], "final experiment")
        # Dedicated orgasm file: one row, O -> S -> resumed, full date-times.
        self.assertEqual(len(orgasms), 1)
        self.assertEqual(orgasms[0]["outcome"], "resumed")
        self.assertEqual(orgasms[0]["trial"], "4")
        self.assertRegex(orgasms[0]["orgasm_start"],
                         r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}$")
        self.assertTrue(orgasms[0]["orgasm_end"])
        self.assertGreaterEqual(float(orgasms[0]["duration_s"]), 0)
        self.assertEqual(events[0]["trial"], "4")
        self.assertIn("Premi O", controls.banner.text)
        self.assertIn("premi S", controls.pause_message.text)
        self.assertEqual(controls.banner.options["font"], "Test Font")
        self.assertAlmostEqual(controls.banner.options["height"], 0.105)
        self.assertAlmostEqual(controls.fixation.options["height"], 0.12)
        self.assertAlmostEqual(controls.pause_message.options["height"], 0.105)
        self.assertEqual(
            pause_key_calls,
            [
                {"keyList": ["s", "e", "escape"]},
                {"keyList": ["left", "right", "e", "escape"]},
                {"keyList": ["left", "right", "escape"]},
            ],
        )

    def test_practice_pause_ignores_e(self):
        from pleasure_experiments.code.participant_controls import (
            ParticipantControls,
        )

        key_calls = []
        controls = ParticipantControls.__new__(ParticipantControls)
        controls.fixation = types.SimpleNamespace(draw=lambda: None)
        controls.pause_message = types.SimpleNamespace(draw=lambda: None)
        controls.win = types.SimpleNamespace(flip=lambda: None)
        controls.event = types.SimpleNamespace(
            waitKeys=lambda **kwargs: key_calls.append(kwargs) or ["s"]
        )
        controls._record = lambda event_name: self.fail(event_name)

        controls.practice_orgasm_pause()

        self.assertEqual(key_calls, [{"keyList": ["s", "escape"]}])

    def test_e_can_be_cancelled_on_confirmation_screen(self):
        from pleasure_experiments.code.participant_controls import (
            ParticipantControls,
        )

        recorded, flips = [], []
        controls = ParticipantControls.__new__(ParticipantControls)
        controls.fixation = types.SimpleNamespace(draw=lambda: None)
        controls.quit_question = types.SimpleNamespace(draw=lambda: None)
        controls.win = types.SimpleNamespace(flip=lambda: flips.append(1))
        controls.event = types.SimpleNamespace(
            waitKeys=lambda **kwargs: ["left"]
        )
        controls._record = recorded.append

        controls.process_keys(["e"])  # must return, not raise

        self.assertEqual(recorded, ["quit_requested", "quit_cancelled"])
        # Confirmation screen, then back to the fixation screen.
        self.assertEqual(len(flips), 2)


if __name__ == "__main__":
    unittest.main()
