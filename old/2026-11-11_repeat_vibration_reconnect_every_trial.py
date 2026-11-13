import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

# Commanded vibrator state, read live by vibrator_monitor.py (experimenter
# screen). Buttplug/Intiface do not report whether a motor is running, so this
# is what the experiment sent: connecting -> on (intensity) -> off.
STATUS_PATH = Path("vibrator_status.json")


def write_status(state, **details):
    """Atomically replace the status file (never half-written for the reader)."""
    status = {"state": state, "time": datetime.now().isoformat(timespec="milliseconds"),
              **details}
    tmp = STATUS_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(status), encoding="utf-8")
        os.replace(tmp, STATUS_PATH)
    except OSError:
        pass  # the indicator is only a display aid; never stop the experiment

async def vibrate_device(device, duration=2, intensity=0.5):
    from buttplug import DeviceOutputCommand, OutputType

    if device.has_output(OutputType.VIBRATE):
        await device.run_output(DeviceOutputCommand(OutputType.VIBRATE, intensity))
        write_status("on", intensity=intensity, duration=duration,
                     device=device.name)
        try:
            await asyncio.sleep(duration)
        finally:
            await device.stop()  # stops immediately
            write_status("off", intensity=intensity, device=device.name)

async def go_vibrate(duration, intensity, simulate_device=False):
    if simulate_device:
        write_status("on", intensity=intensity, duration=duration,
                     device="SIMULATION")
        await asyncio.sleep(duration)
        write_status("off", intensity=intensity, device="SIMULATION")
        return

    from buttplug import ButtplugClient

    write_status("connecting")
    client = ButtplugClient("My Client")
    await client.connect("ws://127.0.0.1:12345")

    # Scan once
    await client.start_scanning()
    await asyncio.sleep(5)
    await client.stop_scanning()

    if not client.devices:
        write_status("error", message="no device found")
        await client.disconnect()
        raise RuntimeError(
            "No compatible device found. Connect a device or rerun with "
            "--simulate-device to test without hardware."
        )

    repeats = 1
    delay_between_pulses = 0 

    for i in range(repeats):
        for device in client.devices.values():
            await vibrate_device(device, duration, intensity)
        await asyncio.sleep(delay_between_pulses)  # small pause before next pulse

    await client.disconnect()

