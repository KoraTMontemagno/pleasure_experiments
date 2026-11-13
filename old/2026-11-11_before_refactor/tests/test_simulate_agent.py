import unittest
from unittest.mock import patch

from pleasure_experiments.synthetic_agent_participant_plots import simulate_agent


class SyntheticAgentTests(unittest.TestCase):
    def test_response_probability_has_half_response_at_threshold(self):
        self.assertAlmostEqual(
            simulate_agent._response_probability(0.65, 0.65, 0.2),
            0.5,
        )
        self.assertLess(
            simulate_agent._response_probability(0.4, 0.65, 0.2),
            0.5,
        )
        self.assertGreater(
            simulate_agent._response_probability(0.9, 0.65, 0.2),
            0.5,
        )

    def test_zero_spread_is_a_step_function(self):
        self.assertEqual(
            simulate_agent._response_probability(0.49, 0.5, 0),
            0.05,
        )
        self.assertEqual(
            simulate_agent._response_probability(0.5, 0.5, 0),
            0.5,
        )
        self.assertEqual(
            simulate_agent._response_probability(0.51, 0.5, 0),
            0.95,
        )

    def test_painful_pleasure_response_is_skipped_in_psi_update(self):
        class FakePsi:
            def __init__(self, *_args, **_kwargs):
                self.xCurrent = 0.5
                self.eThreshold = 0.4
                self.stdThreshold = 0.1
                self.eSlope = 0.2
                self.skipped = []
                self.added = []

            def skipData(self, intensity):
                self.skipped.append(intensity)
                self.xCurrent = intensity

            def addData(self, response):
                self.added.append(response)
                self.xCurrent = 0.4

        model = FakePsi()
        with (
            patch.object(simulate_agent.PsiMarginal, "Psi", return_value=model),
            patch.object(
                simulate_agent,
                "_sample_response",
                side_effect=[1, 0, 1],
            ),
        ):
            result = simulate_agent._fit_pleasure_threshold(
                minimum=0.1,
                maximum=0.8,
                n_trials=2,
                pain_threshold=0.65,
                pain_spread=0.2,
                pleasure_threshold=0.35,
                pleasure_spread=0.3,
                rng=object(),
            )

        self.assertEqual(model.skipped, [0.4])
        self.assertEqual(model.added, [1])
        self.assertEqual([trial["response"] for trial in result["trials"]], [1000, 1])
        self.assertFalse(result["safety_stop"])

    def test_validation_retries_once_then_accepts_pleasure_at_threshold_or_maximum(self):
        class FakeRng:
            @staticmethod
            def shuffle(_values):
                return None

        one_cycle = [0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]
        responses = iter(one_cycle + one_cycle)
        with patch.object(
            simulate_agent,
            "_sample_response",
            side_effect=lambda *_args: next(responses),
        ):
            levels, trials, passed, accepted_by_pleasure = (
                simulate_agent._validate_levels(
                    levels=(0.2, 0.3, 0.4),
                    minimum_allowed=0.1,
                    maximum_allowed=1.0,
                    adjustment_step=0.1,
                    pain_threshold=0.6,
                    pain_spread=0.1,
                    pleasure_threshold=0.3,
                    pleasure_spread=0.1,
                    rng=FakeRng(),
                )
            )

        self.assertEqual(levels, (0.2, 0.3, 0.4))
        self.assertEqual(len(trials), 12)
        self.assertFalse(passed)
        self.assertTrue(accepted_by_pleasure)
        self.assertTrue(
            any(
                trial["level"] in ("threshold", "maximum")
                and trial["pleasure_reported"]
                for trial in trials
                if trial["cycle"] == 2
            )
        )


if __name__ == "__main__":
    unittest.main()
