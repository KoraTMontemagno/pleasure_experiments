"""Small always-on-top window showing what the vibrator is doing (experimenter).

Reads vibrator_status.json, written by code/repeat_vibration.py, 20 times per
second:

    grey    idle          last stimulus and when it ended
    yellow  connecting    connecting to Intiface / scanning for the device
    green   connected     device found, no stimulus yet
    red     VIBRATING     intensity and elapsed / planned duration
    purple  error         e.g. no device found

Buttplug/Intiface do not report whether the motor is actually running, so this
shows the commands the experiment sent (on at intensity X, then stop).

Started by the launcher together with the QC monitor, or by hand:
    python vibrator_monitor.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

HERE = Path(__file__).resolve().parent
STATUS_PATH = HERE / "vibrator_status.json"
COLORS = {"idle": "#5a5a5a", "ready": "#2e7d32", "connecting": "#b58900",
          "on": "#c0392b", "error": "#6c3483"}


def read_status():
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "idle"}


def describe(status, now=None):
    """(state key, text) for the window."""
    now = now or datetime.now()
    state = status.get("state", "idle")
    since = status.get("time")
    try:
        elapsed = (now - datetime.fromisoformat(since)).total_seconds()
    except (TypeError, ValueError):
        elapsed = None
    sim = "  (simulation)" if status.get("device") == "SIMULATION" else ""
    if state == "on":
        duration = status.get("duration")
        timing = (f"{elapsed:.1f} / {float(duration):.1f} s"
                  if elapsed is not None and duration is not None else "")
        return "on", f"VIBRATING   intensity {float(status['intensity']):.3f}\n{timing}{sim}"
    if state == "connecting":
        return "connecting", "Connecting to the device…"
    if state == "ready":
        return "ready", f"Connected: {status.get('device', '')}\nwaiting for the first stimulus"
    if state == "error":
        return "error", f"Device error: {status.get('message', '')}"
    if state == "off" and since:
        return "idle", (f"Idle   last: {float(status['intensity']):.3f} "
                        f"ended {since[11:19]}{sim}")
    return "idle", "Idle"


def main():
    app = QtWidgets.QApplication(sys.argv)
    label = QtWidgets.QLabel()
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setMinimumSize(360, 90)
    label.setWindowTitle("Vibrator (experimenter only)")
    label.setWindowFlags(label.windowFlags()
                         | QtCore.Qt.WindowType.WindowStaysOnTopHint)

    def refresh():
        state, text = describe(read_status())
        label.setText(text)
        label.setStyleSheet(f"background:{COLORS[state]}; color:white; "
                            "font-size:18px; font-weight:bold; padding:8px;")

    timer = QtCore.QTimer()
    timer.timeout.connect(refresh)
    timer.start(50)
    refresh()
    label.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    os.chdir(HERE)
    main()
