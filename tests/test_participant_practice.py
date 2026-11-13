import importlib
import sys
import types
import unittest
from unittest.mock import patch


class ParticipantPracticeTests(unittest.TestCase):
    def test_practice_retries_wrong_keys_and_vas_order_until_correct(self):
        drawn_texts = []

        class FakeStim:
            def __init__(self, _win, text="", **_kwargs):
                self.text = text

            def draw(self):
                drawn_texts.append(self.text)

        class FakeWindow:
            def flip(self):
                pass

        class FakeScale:
            def reset(self):
                self.rating = 0

            def setRating(self, value):
                self.rating = value

            def draw(self):
                pass

        keys = [
            # --- pain practice ---
            # pain_yes (RIGHT): wrong LEFT; E is only a wrong answer and is
            # ignored on the feedback screen, so it may not end the session.
            "left", "return", "e", "e", "return", "right", "return",
            # pain_no (LEFT)
            "right", "return", "left", "return",
            # pain_quit (E)
            "e", "return",
            # orgasm (O)
            "right", "return", "o", "return",
            "return",
            # --- pleasure practice ---
            # "question has changed" screen (E ignored)
            "e", "return",
            # pleasure_yes (RIGHT)
            "left", "return", "right", "return",
            # vibration_no (LEFT)
            "left", "return",
            # pain_down (DOWN): wrong RIGHT first
            "right", "return", "down", "return",
            "return",
            # --- VAS practice ---
            # intro screen
            "return",
            # round 1: strong/not pleasurable 3 >= faint/pleasurable 2 -> retry
            "e", "right", "right", "right", "up", "e", "return",
            "right", "right", "up", "return",
            "return",
            # round 2: strong 1 < faint 2 -> correct (the scale is pleasure)
            "right", "up", "return",
            "right", "right", "up", "return",
            "return",
        ]
        key_requests = []

        def wait_keys(**kwargs):
            key_requests.append(kwargs.get("keyList"))
            if not keys:
                raise AssertionError(
                    "Practice requested more keys than expected: "
                    f"{key_requests}"
                )
            return [keys.pop(0)]

        psychopy = types.ModuleType("psychopy")
        psychopy.core = types.SimpleNamespace()
        psychopy.event = types.SimpleNamespace(waitKeys=wait_keys)
        psychopy.monitors = types.ModuleType("psychopy.monitors")
        psychopy.visual = types.SimpleNamespace(TextStim=FakeStim)

        class FakeControls:
            def __init__(self):
                self.practice_pauses = 0
                self.draw_calls = 0

            def set_context(self, *_args):
                pass

            def draw(self):
                self.draw_calls += 1

            def process_keys(self, keys, **_kwargs):
                process_key_calls.append(list(keys))

            def consume_orgasm_reports(self):
                return 1

            def practice_orgasm_pause(self, **_kwargs):
                self.practice_pauses += 1

        process_key_calls = []
        controls = FakeControls()
        controls_module = types.ModuleType(
            "pleasure_experiments.code.participant_controls"
        )
        controls_module.get_participant_controls = (
            lambda *_args, **_kwargs: controls
        )
        window = FakeWindow()
        question = FakeStim(window)
        instructions = FakeStim(window)
        scale = FakeScale()
        display = (
            window,
            FakeStim(window),
            FakeStim(window, "Did you feel pleasure?"),
            FakeStim(window, "←\nNo"),
            FakeStim(window, "→\nYes"),
            instructions,
            FakeStim(window, "↓\nPainful / annoying"),
            question,
            scale,
            FakeStim(window),
        )

        with patch.dict(
            sys.modules,
            {
                "psychopy": psychopy,
                "psychopy.event": psychopy.event,
                "psychopy.monitors": psychopy.monitors,
                "pleasure_experiments.code.participant_controls": controls_module,
            },
        ):
            sys.modules.pop("pleasure_experiments.code.psychopy_fun", None)
            psychopy_fun = importlib.import_module(
                "pleasure_experiments.code.psychopy_fun"
            )
            psychopy_fun.run_participant_practice(
                display,
                subject="practice",
                language="en",
                mode="annoyance",
            )
            annoyance_texts = list(drawn_texts)
            psychopy_fun.run_participant_practice(
                display,
                subject="practice",
                language="en",
                mode="pleasure",
            )
            psychopy_fun.run_vas_practice(
                display,
                subject="practice",
                language="en",
            )

        self.assertEqual(controls.practice_pauses, 1)
        self.assertEqual(process_key_calls, [])
        self.assertEqual(keys, [])
        self.assertIn(
            "Did this vibration feel annoying or painful?", annoyance_texts
        )
        self.assertNotIn(
            "Did you feel a pleasurable sensation?", annoyance_texts
        )
        # DOWN (pain) option only shown in the pleasure practice.
        self.assertNotIn("↓\nPainful / annoying", annoyance_texts)
        self.assertIn("↓\nPainful / annoying", drawn_texts)
        self.assertTrue(
            any(text.startswith("The question has changed.")
                for text in drawn_texts)
        )
        # The shared question stim is restored after each practice.
        self.assertEqual(display[2].text, "Did you feel pleasure?")
        self.assertGreater(controls.draw_calls, 0)
        self.assertIn(
            "Did you feel a pleasurable sensation?",
            drawn_texts,
        )
        self.assertIn("←\nNo", drawn_texts)
        self.assertIn("→\nYes", drawn_texts)
        self.assertIn(
            "Nel caso la stimolazione causasse un orgasmo",
            psychopy_fun.participant_text(
                "annoyance_threshold_ready",
                "it",
            ),
        )
        self.assertIn(
            "The faint but very pleasurable vibration should be rated as "
            "more pleasurable than the strong but not pleasurable one: "
            "the scale is about pleasure, not about how strong the "
            "vibration was. Press ENTER to practise both ratings again.",
            drawn_texts,
        )
        self.assertGreaterEqual(
            drawn_texts.count(
                "Correct. Press ENTER to continue."
            ),
            4,
        )


if __name__ == "__main__":
    unittest.main()
