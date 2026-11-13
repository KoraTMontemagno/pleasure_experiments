"""Vibrator control through Intiface (Buttplug), one connection per session.

    connect()      once at the start: connect to Intiface and scan for the
                   device (~5 s). Called by wrapper.run_experiment before the
                   first stage; vibrate() also connects if needed.
    vibrate(...)   one stimulus: on at `intensity` for `duration` s, then stop.
    disconnect()   at the end of the session (stops all devices first).

The Buttplug client keeps the connection alive with a background ping task,
so it lives on its own asyncio event loop in a background thread for the whole
session; the experiment (PsychoPy, main thread) sends commands to it.

If the connection drops mid-session, vibrate() reconnects once and repeats the
stimulus (with a warning in the log); if that fails too, it raises.
"""

import asyncio
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

INTIFACE_URL = "ws://127.0.0.1:12345"
SCAN_SECONDS = 5

# Commanded vibrator state, read live by qc_monitor.py (experimenter
# screen). Buttplug/Intiface do not report whether a motor is running, so this
# is what the experiment sent: connecting -> ready -> on (intensity) -> off.
STATUS_PATH = Path("vibrator_status.json")


def write_status(state, **details):
    """Atomically replace the status file (never half-written for the reader)."""
    status = {"state": state,
              "time": datetime.now().isoformat(timespec="milliseconds"),
              **details}
    tmp = STATUS_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(status), encoding="utf-8")
        os.replace(tmp, STATUS_PATH)
    except OSError:
        pass  # the indicator is only a display aid; never stop the experiment


class _Session:
    """The one Buttplug connection of this process."""

    def __init__(self):
        self.loop = None
        self.thread = None
        self.client = None
        self.devices = []

    # -- background event loop ---------------------------------------------
    def _run(self, coro, timeout=None):
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self.loop.run_forever,
                                           name="buttplug", daemon=True)
            self.thread.start()
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    @property
    def connected(self):
        return bool(self.client is not None and self.client.connected
                    and self.devices)

    # -- coroutines (run on the background loop) -----------------------------
    async def _connect(self):
        from buttplug import ButtplugClient, OutputType

        client = ButtplugClient("Pleasure experiment")
        await client.connect(INTIFACE_URL)
        await client.start_scanning()
        await asyncio.sleep(SCAN_SECONDS)
        await client.stop_scanning()
        devices = [device for device in client.devices.values()
                   if device.has_output(OutputType.VIBRATE)]
        if not devices:
            await client.disconnect()
            raise RuntimeError(
                "No vibrating device found. Check that Intiface Central is "
                "running and the device is connected, or use Simulation.")
        self.client, self.devices = client, devices

    async def _vibrate(self, duration, intensity):
        from buttplug import DeviceOutputCommand, OutputType

        names = ", ".join(device.name for device in self.devices)
        await asyncio.gather(*(
            device.run_output(DeviceOutputCommand(OutputType.VIBRATE, intensity))
            for device in self.devices))
        onset = datetime.now()
        write_status("on", intensity=intensity, duration=duration, device=names)
        try:
            await asyncio.sleep(duration)
        finally:
            await asyncio.gather(*(device.stop() for device in self.devices),
                                 return_exceptions=True)
            write_status("off", intensity=intensity, device=names)
        return onset, datetime.now()

    async def _disconnect(self):
        try:
            await self.client.stop_all_devices()
        finally:
            await self.client.disconnect()

    # -- public, called from the experiment's thread ---------------------------
    def connect(self):
        if self.connected:
            return
        write_status("connecting")
        try:
            self._run(self._connect(), timeout=SCAN_SECONDS + 30)
        except Exception as exc:
            write_status("error", message=str(exc)[:80])
            raise
        names = ", ".join(device.name for device in self.devices)
        write_status("ready", device=names)
        print(f"Vibrator connected: {names}")

    def vibrate(self, duration, intensity):
        from buttplug import ButtplugError

        self.connect()
        try:
            return self._run(self._vibrate(duration, intensity),
                             timeout=duration + 10)
        except (ButtplugError, ConnectionError, OSError, TimeoutError) as exc:
            print(f"WARNING: vibrator connection lost ({exc!r}); "
                  "reconnecting and repeating the stimulus.")
            self.client, self.devices = None, []
            self.connect()
            return self._run(self._vibrate(duration, intensity),
                             timeout=duration + 10)

    def disconnect(self):
        if self.client is not None:
            try:
                self._run(self._disconnect(), timeout=10)
            except Exception as exc:  # noqa: BLE001 - closing anyway
                print(f"Vibrator disconnect: {exc!r}")
            print("Vibrator disconnected.")
        self.client, self.devices = None, []
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=5)
            self.loop.close()
            self.loop = self.thread = None
        write_status("idle")


_session = _Session()


def connect():
    """Connect to Intiface and find the device (once per session)."""
    _session.connect()


def vibrate(duration, intensity, simulate_device=False):
    """One stimulus; blocks for `duration` s. Returns (onset, offset) datetimes."""
    if simulate_device:
        onset = datetime.now()
        write_status("on", intensity=intensity, duration=duration,
                     device="SIMULATION")
        time.sleep(duration)
        write_status("off", intensity=intensity, device="SIMULATION")
        return onset, datetime.now()
    return _session.vibrate(duration, intensity)


def disconnect():
    """Stop and close the connection (end of session; safe to call twice)."""
    _session.disconnect()
