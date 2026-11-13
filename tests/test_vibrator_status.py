import json
import os
import sys
import tempfile
import threading
import types
import unittest
from datetime import datetime
from unittest.mock import patch

from pleasure_experiments.code import repeat_vibration as rv


def _fake_buttplug(log, fail_once=False):
    """Minimal stand-in for the buttplug package; records what was sent."""
    module = types.ModuleType("buttplug")

    class ButtplugError(Exception):
        pass

    class OutputType:
        VIBRATE = "vibrate"

    class DeviceOutputCommand:
        def __init__(self, kind, value):
            self.kind, self.value = kind, value

    state = {"fail": fail_once}

    class Device:
        name = "FakeToy"

        def has_output(self, kind):
            return kind == OutputType.VIBRATE

        async def run_output(self, command):
            if state["fail"]:
                state["fail"] = False
                raise ButtplugError("connection lost")
            log.append(("on", command.value))

        async def stop(self):
            log.append(("stop",))

    class ButtplugClient:
        def __init__(self, name):
            self.connected = False
            self.devices = {}

        async def connect(self, url):
            log.append(("connect", url))
            self.connected = True

        async def start_scanning(self):
            self.devices = {0: Device()}

        async def stop_scanning(self):
            pass

        async def stop_all_devices(self):
            log.append(("stop_all",))

        async def disconnect(self):
            log.append(("disconnect",))
            self.connected = False

    module.ButtplugClient = ButtplugClient
    module.ButtplugError = ButtplugError
    module.OutputType = OutputType
    module.DeviceOutputCommand = DeviceOutputCommand
    return module


class VibratorSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.temp.name)
        rv._session = rv._Session()

    def tearDown(self):
        rv.disconnect()
        os.chdir(self.cwd)
        self.temp.cleanup()

    def test_connects_once_for_many_stimuli(self):
        log = []
        with patch.dict(sys.modules, {"buttplug": _fake_buttplug(log)}), \
                patch.object(rv, "SCAN_SECONDS", 0), patch("builtins.print"):
            rv.connect()
            for intensity in (0.2, 0.4, 0.6):
                rv.vibrate(0.01, intensity)
            rv.disconnect()

        self.assertEqual([e for e in log if e[0] == "connect"],
                         [("connect", rv.INTIFACE_URL)])
        self.assertEqual([e[1] for e in log if e[0] == "on"], [0.2, 0.4, 0.6])
        self.assertEqual(log.count(("stop",)), 3)
        self.assertEqual(log[-2:], [("stop_all",), ("disconnect",)])

    def test_lost_connection_reconnects_once_and_repeats_stimulus(self):
        log = []
        with patch.dict(sys.modules, {"buttplug": _fake_buttplug(log, fail_once=True)}), \
                patch.object(rv, "SCAN_SECONDS", 0), patch("builtins.print"):
            rv.vibrate(0.01, 0.3)

        self.assertEqual(len([e for e in log if e[0] == "connect"]), 2)
        self.assertEqual([e[1] for e in log if e[0] == "on"], [0.3])

    def test_simulation_writes_on_then_off_without_connecting(self):
        seen = []
        thread = threading.Thread(target=rv.vibrate, args=(0.2, 0.35),
                                  kwargs={"simulate_device": True})
        thread.start()
        threading.Event().wait(0.05)
        seen.append(json.loads(rv.STATUS_PATH.read_text()))
        thread.join()
        seen.append(json.loads(rv.STATUS_PATH.read_text()))

        self.assertEqual((seen[0]["state"], seen[0]["intensity"]), ("on", 0.35))
        self.assertEqual(seen[1]["state"], "off")
        self.assertIsNone(rv._session.client)


class VibratorIndicatorTests(unittest.TestCase):
    def test_indicator_text(self):
        from pleasure_experiments import qc_monitor as vm
        state, text = vm.describe(
            {"state": "on", "intensity": 0.4, "duration": 2,
             "time": "2026-01-01T10:00:00.000"},
            now=datetime(2026, 1, 1, 10, 0, 1))
        self.assertEqual(state, "on")
        self.assertIn("1.0 / 2.0 s", text)
        self.assertEqual(vm.describe({"state": "ready", "device": "Toy"})[0], "ready")
        self.assertEqual(vm.describe({})[0], "idle")


if __name__ == "__main__":
    unittest.main()
