import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class PleasureResponseTests(unittest.TestCase):
    def _run_trial(self, pressed="right", response_mode="pleasure",
                   with_pain_label=False):
        response_key_lists = []

        def get_keys(keyList):
            response_key_lists.append(keyList)
            if pressed in keyList:
                return [pressed]
            if "left" in keyList:  # fallback answer if key not offered
                return ["left"]
            return []

        psychopy = types.ModuleType("psychopy")
        psychopy.core = types.SimpleNamespace(wait=lambda _duration: None)
        psychopy.event = types.SimpleNamespace(getKeys=get_keys)
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
        psychopy_fun.VAS_MARKER_COLOR = "darkred"
        repeat_vibration = types.ModuleType(
            "pleasure_experiments.code.repeat_vibration"
        )

        async def fake_vibrate(**_kwargs):
            pass

        repeat_vibration.go_vibrate = fake_vibrate
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
                lambda *_args, **_kwargs: None
            )
            pain_label = FakeStim() if with_pain_label else None
            result = stimulation_utils.run_trial(
                vibr=0.4,
                win=win,
                fixation=FakeStim(),
                quality_pleasure=FakeScale(),
                quality_question_pleasure=FakeStim(),
                no_label=FakeStim(),
                yes_label=FakeStim(),
                stim_duration=0,
                jitter_wait=0,
                jitter_response=0,
                simulate_device=True,
                response_mode=response_mode,
                pain_label=pain_label,
                subject="response-test",
                language="en",
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

    def test_pleasure_down_key_reports_pain_as_1000(self):
        result, response_key_lists, pain_label = self._run_trial(
            pressed="down", with_pain_label=True
        )

        self.assertEqual(result["response"], 1000)
        self.assertEqual(result["marker_position"], 3)
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
