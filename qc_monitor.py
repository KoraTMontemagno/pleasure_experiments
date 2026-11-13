"""Experimenter monitor: one window with everything (participant never sees it).

    top bar       vibrator state (20x/s): connecting / connected / VIBRATING
                  at intensity X (elapsed / planned s) / idle / error
    excitement    excitement VAS over the session (clock time), by phase
    trials        validation / habituation / final trials in order, coloured
                  by response, VAS above; hollow grey = planned, not yet done
    thresholds    annoyance and pleasure runs with the running estimate ± 2 SD
    summary       thresholds, final intensities, responses per intensity,
                  pain / orgasm / quit events
    table         every stimulus, newest first: intensity, response, VAS,
                  planned vs actual jitters and stimulus duration (yellow =
                  actual differs from planned by more than 0.25 s)

Data: the files the experiment writes after every trial (data/sub-<ID>/...)
and vibrator_status.json (code/repeat_vibration.py). Buttplug/Intiface do not
report whether the motor runs, so the vibrator views show what was commanded.

Started by the launcher ("Live experimenter monitor"), or by hand:
    python qc_monitor.py <participant>      e.g.  python qc_monitor.py 6
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6 import QtCore, QtGui, QtWidgets

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from pleasure_experiments.code import experiment_progress as progress  # noqa: E402
from pleasure_experiments.code.qc_plots import (  # noqa: E402
    COLORS,
    current_phase,
    excitement_panel,
    later_panel,
    parse_time,
    summary_lines,
    threshold_panel,
)

STATUS_PATH = HERE / "vibrator_status.json"
STATE_COLORS = {"idle": "#5a5a5a", "ready": "#2e7d32", "connecting": "#b58900",
                "on": "#c0392b", "error": "#6c3483"}
# trial table name -> (label, phase name used in planned_order.csv)
JITTER_WARNING = 0.25  # s between planned and actual timing -> yellow row


# ---------------------------------------------------------------- vibrator --
def read_status():
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "idle"}


def describe(status, now=None):
    """(state key, text) for the vibrator status bar."""
    now = now or datetime.now()
    state = status.get("state", "idle")
    since = parse_time(status.get("time"))
    elapsed = (now - since).total_seconds() if since else None
    sim = "  (simulation)" if status.get("device") == "SIMULATION" else ""
    if state == "on":
        duration = status.get("duration")
        timing = (f"   {elapsed:.1f} / {float(duration):.1f} s"
                  if elapsed is not None and duration is not None else "")
        return "on", f"VIBRATING   intensity {float(status['intensity']):.3f}{timing}{sim}"
    if state == "connecting":
        return "connecting", "Connecting to the device…"
    if state == "ready":
        return "ready", f"Connected: {status.get('device', '')} - waiting for the first stimulus"
    if state == "error":
        return "error", f"Device error: {status.get('message', '')}"
    if state == "off" and since:
        return "idle", (f"Idle   last: {float(status['intensity']):.3f}, "
                        f"ended {status['time'][11:19]}{sim}")
    return "idle", "Vibrator idle"


# ----------------------------------------------------------------- table --
TABLE_COLUMNS = [
    ("Phase", "phase"), ("Trial", "trial"), ("Intensity", "intensity"),
    ("Response", None), ("VAS", "intensity_rating"),
    ("Pre-jitter plan", "jitter_pre_planned"), ("Pre-jitter actual", "jitter_pre_actual"),
    ("Post-jitter plan", "jitter_post_planned"), ("Post-jitter actual", "jitter_post_actual"),
    ("Stim plan", "stim_duration_planned"), ("Stim actual", "stim_duration_actual"),
    ("Trial (s)", "trial_duration"), ("Orgasm", "orgasm_reports"), ("Onset", "stim_onset"),
]
TIMING_PAIRS = (("jitter_pre_planned", "jitter_pre_actual"),
                ("jitter_post_planned", "jitter_post_actual"),
                ("stim_duration_planned", "stim_duration_actual"))


def table_cells(row):
    """Display texts for one timing row, and whether its timing is off."""
    cells = []
    for _, key in TABLE_COLUMNS:
        if key is None:
            cells.append(progress.RESPONSE_LABELS.get(progress.response_code(row.get("response")), ""))
        elif key == "stim_onset":
            cells.append((row.get(key) or "")[11:23])
        else:
            value = row.get(key, "")
            number = progress.number(value)
            cells.append(f"{number:.3f}".rstrip("0").rstrip(".") if number is not None
                         and key not in ("trial", "orgasm_reports") else str(value or ""))
    off = any(
        progress.number(row.get(plan)) is not None and progress.number(row.get(actual)) is not None
        and abs(progress.number(row.get(plan)) - progress.number(row.get(actual))) > JITTER_WARNING
        for plan, actual in TIMING_PAIRS)
    return cells, off


# ------------------------------------------------------------------ window --
class Monitor(QtWidgets.QMainWindow):
    def __init__(self, subject):
        super().__init__()
        self.subject = subject
        self.setWindowTitle(f"Experimenter monitor - sub-{subject} (participant never sees this)")
        self.resize(1700, 1000)
        self._mtimes = None

        self.status = QtWidgets.QLabel()
        self.status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status.setMinimumHeight(48)
        self.phase = QtWidgets.QLabel()
        self.phase.setStyleSheet("font-size:14px; font-weight:bold; padding:4px;")
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.status, 3)
        top.addWidget(self.phase, 1)

        # left: excitement VAS over the session above the trial sequence
        self.excitement_fig = Figure(figsize=(9, 2.8), tight_layout=True)
        self.excitement_ax = self.excitement_fig.add_subplot()
        self.excitement_canvas = FigureCanvasQTAgg(self.excitement_fig)
        self.later_fig = Figure(figsize=(9, 3.6), tight_layout=True)
        self.later_ax = self.later_fig.add_subplot()
        self.later_canvas = FigureCanvasQTAgg(self.later_fig)
        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.excitement_canvas, 2)
        left.addWidget(self.later_canvas, 3)

        # right: thresholds and summary
        self.side_fig = Figure(figsize=(6, 6.2), tight_layout=True)
        grid = self.side_fig.add_gridspec(3, 1, height_ratios=[1, 1, 1.2])
        self.annoy_ax = self.side_fig.add_subplot(grid[0])
        self.pleasure_ax = self.side_fig.add_subplot(grid[1])
        self.text_ax = self.side_fig.add_subplot(grid[2])
        self.side_canvas = FigureCanvasQTAgg(self.side_fig)

        plots = QtWidgets.QHBoxLayout()
        plots.addLayout(left, 3)
        plots.addWidget(self.side_canvas, 2)

        self.table = QtWidgets.QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([name for name, _ in TABLE_COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setToolTip(f"Yellow: actual timing differs from planned by > {JITTER_WARNING} s")

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        holder = QtWidgets.QWidget()
        holder.setLayout(plots)
        splitter.addWidget(holder)
        splitter.addWidget(self.table)
        splitter.setSizes([680, 280])

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        for interval, slot in ((50, self.refresh_status), (1000, self.refresh_data)):
            timer = QtCore.QTimer(self)
            timer.timeout.connect(slot)
            timer.start(interval)
        self.refresh_data(force=True)
        self.refresh_status()

    def refresh_status(self):
        state, text = describe(read_status())
        self.status.setText(text)
        self.status.setStyleSheet(f"background:{STATE_COLORS[state]}; color:white; "
                                  "font-size:20px; font-weight:bold; padding:6px;")

    def refresh_data(self, force=False):
        paths = [progress.table_path(self.subject, t) for t in progress.TABLES]
        mtimes = tuple(p.stat().st_mtime if p.is_file() else 0 for p in paths)
        if mtimes == self._mtimes and not force:
            return  # nothing new written
        self._mtimes = mtimes
        data = progress.load(self.subject)
        self.phase.setText(f"sub-{self.subject}   |   last written: "
                           f"{current_phase(self.subject)}")
        threshold_panel(self.annoy_ax, data["annoyance"],
                        "Annoyance threshold (filled = annoying)", "Annoying", COLORS[1000])
        threshold_panel(self.pleasure_ax, data["pleasure"],
                        "Pleasure threshold (filled = pleasure, x = painful)", "Pleasure",
                        COLORS[1])
        self.text_ax.clear()
        self.text_ax.axis("off")
        self.text_ax.text(0, 1, "\n".join(summary_lines(data)), va="top",
                          family="monospace", fontsize=8, transform=self.text_ax.transAxes)
        self.side_canvas.draw_idle()
        excitement_panel(self.excitement_ax, data["arousal"])
        self.excitement_canvas.draw_idle()
        later_panel(self.later_ax, data)
        self.later_canvas.draw_idle()
        self.fill_table(data["timing"])

    def fill_table(self, rows):
        self.table.setRowCount(len(rows))
        warn = QtGui.QBrush(QtGui.QColor("#fff3b0"))
        for r, row in enumerate(reversed(rows)):  # newest first
            cells, off = table_cells(row)
            for c, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if off:
                    item.setBackground(warn)
                self.table.setItem(r, c, item)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python qc_monitor.py <participant>")
    os.chdir(HERE)
    app = QtWidgets.QApplication(sys.argv)
    window = Monitor(sys.argv[1])
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
