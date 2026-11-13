"""Plots of the experimenter monitor, without any GUI code.

Used live by qc_monitor.py (inside the Qt window) and at the end of every run
by wrapper.py, which saves the same overview as a PNG in the participant's
experiment folder (save_overview).
"""

from collections import Counter
from datetime import datetime

from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from . import experiment_progress as progress

COLORS = {0: "dimgray", 1: "forestgreen", 1000: "indianred"}
# trial table name -> (label, phase name used in planned_order.csv)
LATER_PHASES = (("validation", "Validation", None),
                ("habituation", "Habituation", "post-validation habituation"),
                ("final", "Final", "final experiment"))

def parse_time(text):
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None



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
    """Excitement VAS over the session (clock time), coloured by phase; the
    span of each phase is shaded. Label above a point: S = start, n = after
    trial n, E = end, then the rating."""
    ax.clear()
    ax.set_title("Excitement VAS during the session "
                 "(S = start, n = after trial n, E = end)", fontsize=10)
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Excitement (0-100)")
    ax.grid(alpha=0.3)
    points = [(parse_time(r.get("timestamp")), progress.number(r.get("rating"), 0), r)
              for r in rows]
    points = [p for p in points if p[0] is not None]
    if not points:
        ax.text(0.5, 0.5, "no ratings yet", ha="center", va="center",
                transform=ax.transAxes, color="grey")
        return
    times = [t for t, _, _ in points]
    ax.plot(times, [y for _, y, _ in points], color="lightgrey", lw=1.2, zorder=1)
    for phase, color in PHASE_COLORS.items():
        in_phase = [t for t, _, r in points if r.get("phase") == phase]
        if in_phase:
            ax.axvspan(min(in_phase), max(in_phase), color=color, alpha=0.07, lw=0)
            ax.scatter([], [], color=color, s=30, label=phase)
    for t, y, row in points:
        ax.scatter(t, y, s=45, color=PHASE_COLORS.get(row.get("phase", ""), "grey"), zorder=2)
        moment = row.get("moment", "")
        short = MOMENT_SHORT.get(moment, moment.replace("after trial ", ""))
        ax.annotate(f"{short}: {y:.0f}", (t, y), textcoords="offset points",
                    xytext=(0, 6), ha="center", va="bottom", fontsize=7)
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    ax.set_xlabel("Time")
    ax.legend(loc="upper left", fontsize=7, ncol=3, frameon=False)


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



def draw_overview(subject, data=None, figure=None):
    """The monitor's plots in one figure: excitement and trial sequence on
    the left, thresholds and summary on the right."""
    data = data or progress.load(subject)
    figure = figure or Figure(figsize=(17, 9))
    grid = figure.add_gridspec(3, 2, width_ratios=[3, 2], height_ratios=[1, 1, 1.2])
    excitement_panel(figure.add_subplot(grid[0, 0]), data["arousal"])
    later_panel(figure.add_subplot(grid[1:, 0]), data)
    threshold_panel(figure.add_subplot(grid[0, 1]), data["annoyance"],
                    "Annoyance threshold (filled = annoying)", "Annoying", COLORS[1000])
    threshold_panel(figure.add_subplot(grid[1, 1]), data["pleasure"],
                    "Pleasure threshold (filled = pleasure, x = painful)", "Pleasure",
                    COLORS[1])
    text_ax = figure.add_subplot(grid[2, 1])
    text_ax.axis("off")
    text_ax.text(0, 1, "\n".join(summary_lines(data)), va="top",
                 family="monospace", fontsize=8, transform=text_ax.transAxes)
    figure.suptitle(f"sub-{subject}   |   saved {datetime.now():%Y-%m-%d %H:%M}",
                    fontsize=11, fontweight="bold")
    figure.tight_layout()
    return figure


def save_overview(subject):
    """Save the overview PNG in data/sub-<ID>/experiment/; returns the path."""
    path = (progress.subject_dir(subject) / "experiment"
            / f"sub-{subject}_monitor_overview.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    draw_overview(subject).savefig(path, dpi=120)
    return path
