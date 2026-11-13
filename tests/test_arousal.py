import csv
import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

class FakeStim:
    def __init__(self, text=""):
        self.text = text
        self.drawn = []

    def draw(self):
        self.drawn.append(self.text)


class FakeScale(FakeStim):
    def reset(self):
        pass

    def setRating(self, value):
        self.rating = value


def fake_display():
    win = types.SimpleNamespace(flip=lambda: None)
    return (win, FakeStim("+"), FakeStim(), FakeStim(), FakeStim(),
            FakeStim("ready text"), FakeStim(), FakeStim("old practice prompt"),
            FakeScale(), FakeStim())


class FakeControls:
    def set_context(self, *_args):
        pass

    def draw(self):
        pass

    def process_keys(self, *_args, **_kwargs):
        pass


class ArousalTests(unittest.TestCase):
    def setUp(self):
        # Import the real modules, and remove them again afterwards so other
        # test files can still install their fake psychopy modules.
        modules = patch.dict(sys.modules)
        modules.start()
        self.addCleanup(modules.stop)
        global su
        su = importlib.import_module("pleasure_experiments.code.stimulation_utils")

    def test_moments_start_every_n_and_end(self):
        moments = [su.arousal_moment(done, 25, 10) for done in range(26)]
        self.assertEqual([m for m in moments if m],
                         ["start", "after trial 10", "after trial 20", "end"])
        self.assertIsNone(su.arousal_moment(0, 25, 0))  # 0 = off

    def test_rating_saved_then_reposition_screen_until_enter(self):
        display = fake_display()
        vas_keys = iter([["right"]] * 30 + [["up"]])
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                with patch.object(su.event, "getKeys", lambda **_k: next(vas_keys)), \
                        patch.object(su.event, "waitKeys", lambda **_k: ["return"]), \
                        patch.object(su, "_wait_with_participant_controls", lambda *_a: None), \
                        patch("pleasure_experiments.code.participant_controls."
                              "get_participant_controls", lambda *_a: FakeControls()), \
                        patch("builtins.print"):
                    rating = su.check_arousal(display, "a1", "it", "final experiment",
                                              10, 90, 10)
                path = Path("data/sub-a1/experiment/sub-a1_arousal_ratings.csv")
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
            finally:
                os.chdir(cwd)

        self.assertEqual(rating, 30.0)
        self.assertEqual(rows[0]["moment"], "after trial 10")
        self.assertEqual(rows[0]["before_trial"], "11")
        self.assertEqual(rows[0]["rating"], "30.0")
        self.assertRegex(rows[0]["timestamp"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        # the question is the arousal one, not the leftover practice prompt
        self.assertIn("eccitat", display[7].drawn[0])
        self.assertNotIn("old practice prompt", display[7].drawn)
        # reposition screen shown (Italian: la clitoride), then text restored
        self.assertTrue(any("clitoride" in text for text in display[5].drawn))
        self.assertEqual(display[5].text, "ready text")

    def test_last_rating_can_skip_the_reposition_screen(self):
        display = fake_display()
        keys = iter([["up"]])
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                with patch.object(su.event, "getKeys", lambda **_k: next(keys)), \
                        patch.object(su.event, "waitKeys",
                                     lambda **_k: self.fail("reposition shown")), \
                        patch.object(su, "_wait_with_participant_controls", lambda *_a: None), \
                        patch("pleasure_experiments.code.participant_controls."
                              "get_participant_controls", lambda *_a: FakeControls()), \
                        patch("builtins.print"):
                    su.check_arousal(display, "a1", "en", "final experiment",
                                     90, 90, 10, reposition=False)
            finally:
                os.chdir(cwd)
        self.assertEqual(display[5].drawn, [])  # ready text never drawn

    def test_no_check_when_not_due(self):
        self.assertIsNone(su.check_arousal(fake_display(), "a1", "en",
                                           "final experiment", 7, 90, 10))


if __name__ == "__main__":
    unittest.main()
