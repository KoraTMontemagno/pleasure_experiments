import asyncio
from buttplug import ButtplugClient, DeviceOutputCommand, OutputType

async def vibrate_device(device, duration=2, intensity=0.5):
    if device.has_output(OutputType.VIBRATE):
        await device.run_output(DeviceOutputCommand(OutputType.VIBRATE, intensity))
        await asyncio.sleep(duration)
        await device.stop()  # stops immediately

async def go_vibrate(duration, intensity):
    client = ButtplugClient("My Client")
    await client.connect("ws://127.0.0.1:12345")

    # Scan once
    await client.start_scanning()
    await asyncio.sleep(5)
    await client.stop_scanning()

    repeats = 1
    delay_between_pulses = 0 

    for i in range(repeats):
        for device in client.devices.values():
            print(f"Pulsing {device.name} ({i+1}/{repeats})")
            await vibrate_device(device, duration, intensity)
        await asyncio.sleep(delay_between_pulses)  # small pause before next pulse

    await client.disconnect()

#asyncio.run(go_vibrate())

async def scan_for_devices():
    client = ButtplugClient("My Client")
    await client.connect("ws://127.0.0.1:12345")
    #Print("Scanning for devices")

    # Scan once
    await client.start_scanning()
    await asyncio.sleep(5)
    await client.stop_scanning()
    print("Devices found:", client.devices)

    return client




