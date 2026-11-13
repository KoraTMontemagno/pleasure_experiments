"""Experimenter monitor: one window with everything (participant never sees it).

    top bar       vibrator state (20x/s): connecting / connected / VIBRATING
                  at intensity X (elapsed / planned s) / idle / error
    vibrator      intensity over time, on/off steps of the last 3 minutes
                  (like the pain experiment's temperature trace), live
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
from collections import Counter
from datetime import datetime
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from PyQt6 import QtCore, QtGui, QtWidgets

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from pleasure_experiments.code import experiment_progress as progress  # noqa: E402

STATUS_PATH = HERE / "vibrator_status.json"
COLORS = {0: "dimgray", 1: "forestgreen", 1000: "indianred"}
STATE_COLORS = {"idle": "#5a5a5a", "ready": "#2e7d32", "connecting": "#b58900",
                "on": "#c0392b", "error": "#6c3483"}
# trial table name -> (label, phase name used in planned_order.csv)
LATER_PHASES = (("validation", "Validation", None),
                ("habituation", "Habituation", "post-validation habituation"),
                ("final", "Final", "final experiment"))
TRACE_SECONDS = 180
JITTER_WARNING = 0.25  # s between planned and actual timing -> yellow row


# ---------------------------------------------------------------- vibrator --
def read_status():
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "idle"}


def parse_time(text):
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


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


def vibration_segments(timing_rows, status, now):
    """(start s, end s, intensity, label) relative to now, from the timing file
    plus the stimulus running right now (from the status file)."""
    segments = []
    for row in timing_rows:
        onset, offset = parse_time(row.get("stim_onset")), parse_time(row.get("stim_offset"))
        intensity = progress.number(row.get("intensity"))
        if onset and offset and intensity is not None:
            segments.append(((onset - now).total_seconds(),
                             (offset - now).total_seconds(), intensity,
                             f"{row.get('phase', '')[:4]} {row.get('trial', '')}"))
    if status.get("state") == "on":
        onset = parse_time(status.get("time"))
        if onset:
            segments.append(((onset - now).total_seconds(), 0.0,
                             float(status["intensity"]), "now"))
    return [s for s in segments if s[1] >= -TRACE_SECONDS]


def vibration_panel(ax, segments):
    ax.clear()
    ax.set_title(f"Vibrator: commanded intensity, last {TRACE_SECONDS // 60} min", fontsize=10)
    ax.set_xlim(-TRACE_SECONDS, 2)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Seconds before now")
    ax.set_ylabel("Intensity")
    ax.grid(alpha=0.3)
    xs, ys = [-TRACE_SECONDS], [0]
    for start, end, intensity, label in sorted(segments):
        xs += [start, start, end, end]
        ys += [0, intensity, intensity, 0]
        ax.annotate(label, ((start + end) / 2, intensity), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=6, color="dimgrey")
    xs.append(2)
    ys.append(0)
    ax.plot(xs, ys, color="#c0392b", lw=1.5, drawstyle="default")
    ax.fill_between(xs, ys, color="#c0392b", alpha=0.15, lw=0)


# --------------------------------------------------------------- QC panels --
def threshold_panel(ax, rows, title, yes_label, yes_color):
    ax.clear()
    ax.set_title(title, fontsize=10)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel("Intensity")
    ax.grid(alpha=0.3)
    ax.set_ylim(0, 1.05)
    if not rows:
        ax.text(0.5, 0.5, "no trials yet", ha="center", va="center",
                transform=ax.transAxes, color="grey")
        return
    trials = [int(progress.number(r["trial"], n)) for n, r in enumerate(rows, 1)]
    intensity = [progress.number(r.get("vibration")) for r in rows]
    estimate = [progress.number(r.get("estimated_threshold")) for r in rows]
    low = [progress.number(r.get("threshold_low_2sd")) for r in rows]
    high = [progress.number(r.get("threshold_high_2sd")) for r in rows]
    if all(v is not None for v in estimate + low + high):
        ax.fill_between(trials, low, high, color="tab:blue", alpha=0.12, lw=0)
        ax.plot(trials, estimate, color="tab:blue", lw=1.5, label="estimate ± 2 SD")
    for trial, value, row in zip(trials, intensity, rows):
        code = progress.response_code(row.get("response"))
        if code == 1000:
            ax.scatter(trial, value, marker="x", s=60, color=COLORS[1000])
        else:
            color = yes_color if code == 1 else COLORS[0]
            ax.scatter(trial, value, s=50, edgecolors=color, lw=1.5,
                       facecolors=color if code == 1 else "none")
    ax.scatter([], [], s=50, color=yes_color, label=yes_label)
    ax.scatter([], [], s=50, facecolors="none", edgecolors=COLORS[0], label="No")
    ax.legend(loc="best", fontsize=7)


def later_panel(ax, data):
    ax.clear()
    ax.set_title("Validation / habituation / final trials (colour = response, "
                 "number = VAS, hollow grey = planned)", fontsize=10)
    ax.set_xlabel("Trial (in order of presentation)")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel("Intensity")
    ax.grid(alpha=0.3)
    ax.set_ylim(0, 1.05)
    planned = {}
    for row in data["planned"]:
        planned.setdefault(row.get("phase"), []).append(progress.number(row.get("intensity")))
    total = sum(max(len(data[name]), len(planned.get(phase, [])))
                for name, _, phase in LATER_PHASES)
    if not total:
        ax.text(0.5, 0.5, "no trials yet", ha="center", va="center",
                transform=ax.transAxes, color="grey")
        return
    x = 0
    for n_phase, (name, label, phase) in enumerate(LATER_PHASES):
        rows, plan = data[name], planned.get(phase, [])
        length = max(len(rows), len(plan))
        if not length:
            continue
        start = x + 1
        for offset, value in enumerate(plan[len(rows):], start=len(rows)):
            ax.scatter(start + offset, value, s=40, facecolors="none",
                       edgecolors="silver", lw=1.2)
        for offset, row in enumerate(rows):
            value = progress.number(row.get("intensity"))
            code = progress.response_code(row.get("response"))
            ax.scatter(start + offset, value, s=45, marker="x" if code == 1000 else "o",
                       color=COLORS.get(code, "grey"))
            vas = progress.number(row.get("intensity_rating"))
            if vas is not None:
                ax.annotate(f"{vas:.0f}", (start + offset, value), textcoords="offset points",
                            rotation=90 if total > 60 else 0, xytext=(0, 6),
                            ha="center", va="bottom", fontsize=6)
        x += length
        ax.axvline(start - 0.5, color="grey", ls="--", lw=0.8)
        ax.annotate(label, (start - 0.5, 1.0), xycoords=("data", "axes fraction"),
                    xytext=(3, -12 - 11 * n_phase), textcoords="offset points",
                    fontsize=8, color="dimgrey")
    for code, text in progress.RESPONSE_LABELS.items():
        ax.scatter([], [], color=COLORS[code], marker="x" if code == 1000 else "o", label=text)
    ax.legend(loc="lower right", fontsize=7, ncol=3)


PHASE_COLORS = {"annoyance threshold": "indianred", "pleasure threshold": "forestgreen",
                "final experiment": "tab:purple"}
MOMENT_SHORT = {"start": "S", "end": "E"}


def excitement_panel(ax, rows):
    """Excitement VAS of every check, in order, coloured by phase."""
    ax.clear()
    ax.set_title("Excitement VAS (S = start, n = after trial n, E = end)", fontsize=10)
    ax.set_ylim(0, 135)  # headroom for labels and the legend row
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Rating")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(alpha=0.3)
    if not rows:
        ax.text(0.5, 0.5, "no ratings yet", ha="center", va="center",
                transform=ax.transAxes, color="grey")
        return
    xs = list(range(1, len(rows) + 1))
    ys = [progress.number(r.get("rating"), 0) for r in rows]
    ax.plot(xs, ys, color="lightgrey", lw=1, zorder=1)
    for x, y, row in zip(xs, ys, rows):
        phase = row.get("phase", "")
        ax.scatter(x, y, s=40, color=PHASE_COLORS.get(phase, "grey"), zorder=2)
        moment = row.get("moment", "")
        short = MOMENT_SHORT.get(moment, moment.replace("after trial ", ""))
        ax.annotate(f"{short}\n{y:.0f}", (x, y), textcoords="offset points",
                    xytext=(0, 5), ha="center", va="bottom", fontsize=6)
    for phase, color in PHASE_COLORS.items():
        if any(r.get("phase") == phase for r in rows):
            ax.scatter([], [], color=color, s=30, label=phase)
    ax.legend(loc="upper left", fontsize=6, ncol=3, frameon=False)


def summary_lines(data):
    summary = data["summary"]

    def value(key):
        found = progress.number(summary.get(key))
        return "-" if found is None else f"{found:.3f}"

    lines = [
        f"Annoyance threshold:  {value('annoyance_threshold')}",
        f"Safe ceiling:         {value('safe_ceiling')}"
        + ("  (manual)" if summary.get("safe_ceiling_manually_overridden") else ""),
        f"Pleasure threshold:   {value('pleasure_threshold')}"
        + ("  (manual)" if summary.get("pleasure_threshold_manually_overridden") else ""),
    ]
    levels = summary.get("final_intensities")
    if levels:
        lines.append("Final intensities:    " + ", ".join(f"{float(v):.3f}" for v in levels))
    if "validation_passed" in summary:
        lines.append(f"Validation passed:    {summary['validation_passed']}")
    final = data["final"]
    if final:
        expected = summary.get("final_n_trials")
        lines += ["", f"Final trials: {len(final)}" + (f"/{expected}" if expected else "")]
        by_type = {}
        for row in final:
            kind = row.get("stimulus_type") or f"{progress.number(row.get('intensity'), 0):.3f}"
            label = progress.RESPONSE_LABELS.get(progress.response_code(row.get("response")), "?")
            by_type.setdefault(kind, Counter())[label] += 1
        order = [k for k in ("low", "medium", "high") if k in by_type]
        for kind in order + [k for k in by_type if k not in order]:
            counts = by_type[kind]
            lines.append(f"  {kind:<7} " + "  ".join(
                f"{label} {counts[label]}" for label in ("Yes", "No", "Painful")))
    if data["arousal"]:
        last = data["arousal"][-1]
        lines += ["", f"Last excitement: {progress.number(last.get('rating'), 0):.0f}"
                  f"  ({last.get('phase', '')}, {last.get('moment', '')}, "
                  f"{last.get('timestamp', '')[11:19]})"]
    painful = sum(progress.response_code(r.get("response")) == 1000
                  for name in ("pleasure", "validation", "habituation", "final")
                  for r in data[name])
    events = Counter(row.get("event") for row in data["events"])
    lines += ["", f"Painful reports (DOWN): {painful}",
              f"Orgasm reports:  {events['orgasm_reported']}",
              f"Quit requests:   {events['quit_requested']}  (cancelled {events['quit_cancelled']})"]
    if events["participant_quit"]:
        lines.append("PARTICIPANT ENDED THE EXPERIMENT")
    if data["events"]:
        last = data["events"][-1]
        lines.append(f"Last event: {last.get('event')} ({last.get('phase')}, "
                     f"{last.get('timestamp', '')[11:19]})")
    return lines


def current_phase(subject):
    """Name of the most recently written stage file."""
    latest, name = 0, "waiting for the first trial..."
    for table in progress.STAGE_TABLES:
        path = progress.table_path(subject, table)
        if path.is_file() and path.stat().st_mtime > latest:
            latest, name = path.stat().st_mtime, table
    return name


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
        self._timing = []

        self.status = QtWidgets.QLabel()
        self.status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status.setMinimumHeight(48)
        self.phase = QtWidgets.QLabel()
        self.phase.setStyleSheet("font-size:14px; font-weight:bold; padding:4px;")
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.status, 3)
        top.addWidget(self.phase, 1)

        # left: vibrator trace (fast) above the trial sequence
        self.trace_fig = Figure(figsize=(9, 2.6), tight_layout=True)
        self.trace_ax = self.trace_fig.add_subplot()
        self.trace_canvas = FigureCanvasQTAgg(self.trace_fig)
        self.later_fig = Figure(figsize=(9, 3.6), tight_layout=True)
        self.later_ax = self.later_fig.add_subplot()
        self.later_canvas = FigureCanvasQTAgg(self.later_fig)
        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.trace_canvas, 2)
        left.addWidget(self.later_canvas, 3)

        # right: thresholds and summary
        self.side_fig = Figure(figsize=(6, 7.5), tight_layout=True)
        grid = self.side_fig.add_gridspec(4, 1, height_ratios=[1, 1, 1, 1.2])
        self.annoy_ax = self.side_fig.add_subplot(grid[0])
        self.pleasure_ax = self.side_fig.add_subplot(grid[1])
        self.excitement_ax = self.side_fig.add_subplot(grid[2])
        self.text_ax = self.side_fig.add_subplot(grid[3])
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

        for interval, slot in ((50, self.refresh_status), (250, self.refresh_trace),
                               (1000, self.refresh_data)):
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

    def refresh_trace(self):
        vibration_panel(self.trace_ax, vibration_segments(self._timing, read_status(),
                                                          datetime.now()))
        self.trace_canvas.draw_idle()

    def refresh_data(self, force=False):
        paths = [progress.table_path(self.subject, t) for t in progress.TABLES]
        mtimes = tuple(p.stat().st_mtime if p.is_file() else 0 for p in paths)
        if mtimes == self._mtimes and not force:
            return  # nothing new written
        self._mtimes = mtimes
        data = progress.load(self.subject)
        self._timing = data["timing"]
        self.phase.setText(f"sub-{self.subject}   |   last written: "
                           f"{current_phase(self.subject)}")
        threshold_panel(self.annoy_ax, data["annoyance"],
                        "Annoyance threshold (filled = annoying)", "Annoying", COLORS[1000])
        threshold_panel(self.pleasure_ax, data["pleasure"],
                        "Pleasure threshold (filled = pleasure, x = painful)", "Pleasure",
                        COLORS[1])
        excitement_panel(self.excitement_ax, data["arousal"])
        self.text_ax.clear()
        self.text_ax.axis("off")
        self.text_ax.text(0, 1, "\n".join(summary_lines(data)), va="top",
                          family="monospace", fontsize=8, transform=self.text_ax.transAxes)
        self.side_canvas.draw_idle()
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
