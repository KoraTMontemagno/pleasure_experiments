import json
import tempfile
import unittest
from pathlib import Path

from pleasure_experiments import wrapper


def _config(**changes):
    config = {
        "duration": 2.5, "jitter_response": 2, "jitter_wait": 2,
        "min_ISI": 10, "ISI_jitter": 1, "habituation": 5,
        "pleasure_pipeline": {"annoyance_ntrials": 15, "pleasure_ntrials": 20},
    }
    config.update(changes)
    return config


class WrapperConfigTests(unittest.TestCase):
    def load(self, config):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "parameters.json")
            path.write_text(json.dumps(config), encoding="utf-8")
            return wrapper.load_config(path)

    def test_current_parameters_file_is_valid(self):
        config = wrapper.load_config(wrapper.CONFIG_PATH)
        self.assertNotIn("ntrials", config)   # legacy, removed
        self.assertNotIn("max_ISI", config)   # legacy, removed
        self.assertIn("min_ISI", config)

    def test_min_isi_is_required(self):
        config = _config()
        del config["min_ISI"]
        with self.assertRaisesRegex(SystemExit, "min_ISI"):
            self.load(config)

    def test_stage_trial_counts_are_required(self):
        with self.assertRaisesRegex(SystemExit, "pleasure_pipeline.pleasure_ntrials"):
            self.load(_config(pleasure_pipeline={"annoyance_ntrials": 15}))

    def test_complete_config_loads(self):
        self.assertEqual(self.load(_config())["min_ISI"], 10)


if __name__ == "__main__":
    unittest.main()
