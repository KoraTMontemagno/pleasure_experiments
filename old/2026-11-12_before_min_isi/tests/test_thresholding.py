import os
import csv
import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import numpy as np



_psychopy = types.ModuleType("psychopy")
_psychopy.core = types.SimpleNamespace(wait=lambda _duration: None)
_psychopy.event = types.SimpleNamespace(waitKeys=lambda **_kwargs: ["space"])
_psychopy.monitors = types.ModuleType("psychopy.monitors")
_psychopy.visual = types.SimpleNamespace()
_hardware = types.ModuleType("psychopy.hardware")
_hardware.keyboard = types.ModuleType("psychopy.hardware.keyboard")
_psychopy.hardware = _hardware
_psychopy_fun = types.ModuleType("pleasure_experiments.code.psychopy_fun")
_psychopy_fun.core = _psychopy.core
_psychopy_fun.event = _psychopy.event
_psychopy_fun.monitors = _psychopy.monitors
_psychopy_fun.visual = _psychopy.visual
_psychopy_fun.psycho_stuff = lambda **_kwargs: None
_psychopy_fun.show_break_review = lambda *args, **kwargs: (True, None)
_psychopy_fun.participant_text = lambda key, language="en": {
    "annoyance_question": "Did this vibration feel annoying or painful?",
    "pleasure_question": "Did you feel a pleasurable sensation?",
    "no": "No",
    "yes": "Yes",
    "annoyance_threshold_ready": "Nel caso la stimolazione causasse un orgasmo. Premi INVIO quando sei pront*.",
    "pleasure_threshold_ready": "Press ENTER when ready.",
}[key]
_psychopy_fun.run_participant_practice = lambda *_args, **_kwargs: None
_psychopy_fun.run_vas_practice = lambda *_args, **_kwargs: None
_psychopy_fun.RESPONSE_LABEL_X = 450
_psychopy_fun.VAS_MARKER_COLOR = "darkred"
_psi_module = types.ModuleType("pleasure_experiments.code.PsiMarginal")
_psi_module.Psi = lambda *_args, **_kwargs: None
with patch.dict(
    sys.modules,
    {
        "psychopy": _psychopy,
        "psychopy.hardware": _hardware,
        "psychopy.hardware.keyboard": _hardware.keyboard,
        "pleasure_experiments.code.psychopy_fun": _psychopy_fun,
        "pleasure_experiments.code.PsiMarginal": _psi_module,
    },
):
    thresholding = importlib.import_module(
        "pleasure_experiments.code.thresholding"
    )


class ThresholdingTests(unittest.TestCase):
    def test_annoyance_threshold_stops_after_four_max_trials_without_pain(self):
        self._run_max_pain_free(practice=True)

    def test_practice_false_skips_the_key_practice(self):
        self._run_max_pain_free(practice=False)

    def _run_max_pain_free(self, practice):
        class FakeWindow:
            def flip(self):
                pass

        class FakeText:
            text = ""

            def draw(self):
                pass

        class FakePsi:
            def __init__(self):
                self.xCurrent = 1.0
                self.response = []
                self.eThreshold = 0.7
                self.stdThreshold = 0.1
                self.eSlope = 0.2
                self.eLapse = 0.01
                self.guessRate = 0.05

            def addData(self, response):
                self.response.append(response)

            def skipData(self, _intensity):
                pass

        class FakeLoc:
            def __init__(self, dataframe):
                self.dataframe = dataframe

            def __setitem__(self, _index, row):
                self.dataframe.rows.append(row)

        class FakeDataFrame:
            def __init__(self, data=None, columns=None):
                self.columns = columns or list(data or {})
                self.rows = []
                if data:
                    self.rows = [
                        dict(zip(self.columns, values))
                        for values in zip(*data.values())
                    ]
                self.loc = FakeLoc(self)

            def __len__(self):
                return len(self.rows)

            def to_csv(self, path, index=False):
                with open(path, "w", newline="", encoding="utf-8") as output:
                    writer = csv.DictWriter(
                        output,
                        fieldnames=self.columns,
                        extrasaction="ignore",
                    )
                    writer.writeheader()
                    writer.writerows(self.rows)

        responses = iter([0, 0, 1, 0, 0, 0, 0])
        trial_calls = []
        participant_flow = []

        def fake_run_trial(**kwargs):
            trial_calls.append(kwargs)
            participant_flow.append("vibration")
            return {
                "response": next(responses),
                "marker_position": 1,
                "intensity_rating": None,
                "wait_time": 0.0,
                "response_jitter": 0.0,
                "trial_start_time": "start",
                "trial_end_time": "end",
                "trial_duration": 15.0,
                "orgasm_reports": 0,
            }

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
        display = (
            FakeWindow(),
            object(),
            object(),
            types.SimpleNamespace(text=""),
            types.SimpleNamespace(text=""),
            types.SimpleNamespace(text=""),
            FakeText(),
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
                        "pleasure_experiments.code.participant_controls": (
                            controls_module
                        ),
                    },
                ), patch.object(
                    thresholding.PsiMarginal,
                    "Psi",
                    return_value=FakePsi(),
                ), patch.object(
                    thresholding,
                    "run_trial",
                    side_effect=fake_run_trial,
                ), patch.object(
                    thresholding,
                    "run_participant_practice",
                    side_effect=lambda *_args, **_kwargs: participant_flow.append(
                        "practice"
                    ),
                ), patch.object(
                    thresholding,
                    "pd",
                    types.SimpleNamespace(DataFrame=FakeDataFrame),
                ), patch.object(
                    thresholding.event,
                    "waitKeys",
                    return_value=["space"],
                ), patch.object(
                    thresholding,
                    "plt",
                    MagicMock(),
                ) as plotter, patch.object(
                    thresholding,
                    "norm",
                    types.SimpleNamespace(
                        cdf=lambda values, **_kwargs: np.full_like(values, 0.5)
                    ),
                ):
                    plotter.subplots.return_value = (MagicMock(), MagicMock())
                    result = thresholding.run_threshold(
                        subject="max-pain-free",
                        pattern="annoyance",
                        ntrials=10,
                        habituation=0,
                        stim_duration=1,
                        jitter_wait=0,
                        jitter_response=0,
                        simulate_device=True,
                        min_vibr=0.1,
                        max_vibr=1.0,
                        display=display,
                        language="it",
                        practice=practice,
                    )
            finally:
                os.chdir(original_dir)
            detailed_log_exists = Path(
                temp_dir
                + "/data/sub-max-pain-free/pain/"
                + "sub-max-pain-free_annoyance_trial_data_detailed.csv"
            ).is_file()

        self.assertTrue(result["pain_free_maximum_stop"])
        self.assertEqual(result["pain_free_maximum_trials"], 4)
        self.assertEqual(len(trial_calls), 7)
        if practice:
            self.assertEqual(participant_flow[0], "practice")
        else:
            self.assertNotIn("practice", participant_flow)
        self.assertIn("Premi INVIO quando sei pront*", display[6].text)
        self.assertTrue(
            all(call["vibr"] == 1.0 for call in trial_calls)
        )
        self.assertTrue(detailed_log_exists)


if __name__ == "__main__":
    unittest.main()
