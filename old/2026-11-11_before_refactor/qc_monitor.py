"""Live QC monitor for the experimenter (adapted from pain_experiment).

A separate window on the experimenter screen; the participant never sees it.
It reads the participant's saved trial files every second (they are written
after every trial) and shows:

    top left:     annoyance threshold - intensity per trial (filled = annoying)
                  and the running threshold estimate ± 2 SD
    top right:    pleasure threshold - intensity per trial (filled = pleasure,
                  x = painful) and the running estimate ± 2 SD
    bottom left:  validation, habituation and final trials in order of
                  presentation, coloured by response, with the VAS rating
    bottom right: summary - thresholds, safe ceiling, final intensities,
                  responses per final intensity, orgasm/quit events

Started by the launcher ("Live QC monitor"), or by hand:
    python qc_monitor.py <participant>      e.g.  python qc_monitor.py 6
"""

import os
import sys
from collections import Counter
from pathlib import Path

import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE.parent))
from pleasure_experiments.code import experiment_progress as progress  # noqa: E402

COLORS = {0: "dimgray", 1: "forestgreen", 1000: "indianred"}
LATER_PHASES = (("validation", "Validation"), ("habituation", "Habituation"),
                ("final", "Final"))


def threshold_panel(ax, rows, title, yes_label, yes_color):
    ax.clear()
    ax.set_title(title, fontsize=10)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Trial")
    ax.set_ylabel("Intensity")
    ax.grid(alpha=0.3)
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
    ax.set_ylim(0, 1.05)


def x_total(data):
    return sum(len(data[name]) for name, _ in LATER_PHASES)


def later_panel(ax, data):
    ax.clear()
    ax.set_title("Validation / habituation / final trials "
                 "(colour = response, number = VAS)", fontsize=10)
    ax.set_xlabel("Trial (in order of presentation)")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel("Intensity")
    ax.grid(alpha=0.3)
    x = 0
    any_rows = False
    for name, label in LATER_PHASES:
        rows = data[name]
        if not rows:
            continue
        any_rows = True
        start = x + 1
        for row in rows:
            x += 1
            value = progress.number(row.get("intensity"))
            code = progress.response_code(row.get("response"))
            ax.scatter(x, value, s=45, marker="x" if code == 1000 else "o",
                       color=COLORS.get(code, "grey"))
            vas = progress.number(row.get("intensity_rating"))
            if vas is not None:
                ax.annotate(f"{vas:.0f}", (x, value), textcoords="offset points",
                            rotation=90 if x_total(data) > 60 else 0,
                            xytext=(0, 6), ha="center", fontsize=6)
        ax.axvspan(start - 0.5, x + 0.5, color="grey",
                   alpha=0.06 if name == "habituation" else 0, lw=0)
        # Dashed line at the start of each phase; labels staggered so short
        # phases (3 habituation trials) do not overlap the next label.
        n_phase = [n for n, _ in LATER_PHASES].index(name)
        ax.axvline(start - 0.5, color="grey", ls="--", lw=0.8)
        ax.annotate(label, (start - 0.5, 1.0), xycoords=("data", "axes fraction"),
                    xytext=(3, -12 - 11 * n_phase), textcoords="offset points",
                    fontsize=8, color="dimgrey")
    if not any_rows:
        ax.text(0.5, 0.5, "no trials yet", ha="center", va="center",
                transform=ax.transAxes, color="grey")
        return
    for code, text in progress.RESPONSE_LABELS.items():
        ax.scatter([], [], color=COLORS[code], marker="x" if code == 1000 else "o",
                   label=text)
    ax.legend(loc="lower right", fontsize=7, ncol=3)
    ax.set_ylim(0, 1.05)


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
        lines.append("Final intensities:    "
                     + ", ".join(f"{float(v):.3f}" for v in levels))
    if "validation_passed" in summary:
        lines.append(f"Validation passed:    {summary['validation_passed']}")

    final = data["final"]
    if final:
        expected = summary.get("final_n_trials")
        lines.append("")
        lines.append(f"Final trials: {len(final)}" + (f"/{expected}" if expected else ""))
        by_type = {}
        for row in final:
            kind = row.get("stimulus_type") or f"{progress.number(row.get('intensity'), 0):.3f}"
            label = progress.RESPONSE_LABELS.get(progress.response_code(row.get("response")), "?")
            by_type.setdefault(kind, Counter())[label] += 1
        for kind in ("low", "medium", "high"):
            if kind in by_type:
                counts = by_type.pop(kind)
                lines.append(f"  {kind:<7} " + "  ".join(
                    f"{label} {counts[label]}" for label in ("Yes", "No", "Painful")))
        for kind, counts in by_type.items():
            lines.append(f"  {kind:<7} " + "  ".join(
                f"{label} {counts[label]}" for label in ("Yes", "No", "Painful")))

    painful = sum(progress.response_code(r.get("response")) == 1000
                  for name in ("pleasure", "validation", "habituation", "final")
                  for r in data[name])
    events = Counter(row.get("event") for row in data["events"])
    lines.append("")
    lines.append(f"Painful reports (DOWN): {painful}")
    lines.append(f"Orgasm reports:  {events['orgasm_reported']}")
    lines.append(f"Quit requests:   {events['quit_requested']}"
                 f"  (cancelled {events['quit_cancelled']})")
    if events["participant_quit"]:
        lines.append("PARTICIPANT ENDED THE EXPERIMENT")
    if data["events"]:
        last = data["events"][-1]
        lines.append(f"Last event: {last.get('event')} ({last.get('phase')}, "
                     f"{last.get('timestamp', '')[11:19]})")
    return lines


def current_phase(subject):
    """Name of the most recently written trial file."""
    latest, name = 0, "waiting for the first trial..."
    for table in progress.TABLES:
        if table == "events":
            continue
        path = progress.table_path(subject, table)
        if path.is_file() and path.stat().st_mtime > latest:
            latest, name = path.stat().st_mtime, table
    return name


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python qc_monitor.py <participant>")
    subject = sys.argv[1]

    # Top row: the two threshold runs and the summary. Bottom row: the
    # validation / habituation / final trials over the full width (~90+ trials).
    fig = plt.figure(figsize=(17, 10))
    grid = fig.add_gridspec(2, 3, height_ratios=[1, 1.4], width_ratios=[1, 1, 0.8])
    ax_annoy = fig.add_subplot(grid[0, 0])
    ax_pleasure = fig.add_subplot(grid[0, 1])
    ax_text = fig.add_subplot(grid[0, 2])
    ax_later = fig.add_subplot(grid[1, :])
    fig.canvas.manager.set_window_title(f"QC monitor - sub-{subject} (experimenter only)")
    fig.subplots_adjust(hspace=0.3, wspace=0.22, top=0.92, bottom=0.06,
                        left=0.05, right=0.99)

    def update(_):
        data = progress.load(subject)
        threshold_panel(ax_annoy, data["annoyance"],
                        "Annoyance threshold (filled = annoying)", "Annoying",
                        COLORS[1000])
        threshold_panel(ax_pleasure, data["pleasure"],
                        "Pleasure threshold (filled = pleasure, x = painful)",
                        "Pleasure", COLORS[1])
        later_panel(ax_later, data)
        ax_text.clear()
        ax_text.axis("off")
        ax_text.text(0, 1, "\n".join(summary_lines(data)), va="top",
                     family="monospace", fontsize=9, transform=ax_text.transAxes)
        fig.suptitle(f"sub-{subject}   |   last written: {current_phase(subject)}",
                     fontsize=11, fontweight="bold")
        return []

    update(0)
    _ani = animation.FuncAnimation(fig, update, interval=1000,  # noqa: F841
                                   cache_frame_data=False)
    plt.show()


if __name__ == "__main__":
    main()
