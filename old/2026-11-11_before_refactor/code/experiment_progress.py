"""What is saved for a participant, shared by the launcher and the QC monitor.

Pure file reading (no PsychoPy), so it can run in the monitor process and be
tested. Paths are relative to the experiment folder (pleasure_experiments/),
where the launcher and wrapper.py run.
"""

import csv
import json
import re
from pathlib import Path

DATA_ROOT = Path("data")

# label shown to the experimenter -> answer to wrapper.py's "Select what to run"
FULL, ANNOYANCE, PLEASURE, FINAL = (
    "1. Full pipeline (all stages)",
    "2. Annoyance threshold only",
    "3. Pleasure threshold only",
    "4. Final experiment only",
)
STEPS = {FULL: "1", ANNOYANCE: "2", PLEASURE: "3", FINAL: "4"}

# name -> (folder, file name after "sub-<ID>_")
TABLES = {
    "annoyance": ("pain", "annoyance_trial_data_detailed.csv"),
    "pleasure": ("pleasure", "pleasure_trial_data_detailed.csv"),
    "validation": ("validation", "pleasure_validation_trials.csv"),
    "habituation": ("experiment", "pleasure_habituation_trials.csv"),
    "final": ("experiment", "pleasure_final_trials.csv"),
    "events": ("experiment", "participant_events.csv"),
}
RESPONSE_LABELS = {0: "No", 1: "Yes", 1000: "Painful"}


def subject_dir(subject, root=DATA_ROOT):
    return Path(root) / f"sub-{subject}"


def table_path(subject, name, root=DATA_ROOT):
    folder, suffix = TABLES[name]
    return subject_dir(subject, root) / folder / f"sub-{subject}_{suffix}"


def read_rows(path):
    """CSV rows as dicts; [] if missing. Tolerates a file being written."""
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def read_summary(subject, root=DATA_ROOT):
    path = (subject_dir(subject, root) / "pleasure"
            / f"sub-{subject}_pleasure_pipeline_summary.json")
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def load(subject, root=DATA_ROOT):
    """Everything saved for one participant: summary + one row list per table."""
    data = {name: read_rows(table_path(subject, name, root)) for name in TABLES}
    data["summary"] = read_summary(subject, root)
    return data


def number(value, default=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default  # NaN -> default


def response_code(value):
    code = number(value)
    return None if code is None else int(code)


def progress(subject, final_trials_per_intensity, root=DATA_ROOT):
    """Which stages are done (from the summary and the trial files)."""
    data = load(subject, root)
    summary = data["summary"]
    n_final = final_trials_per_intensity * 3
    return {
        "annoyance_done": "safe_ceiling" in summary,
        "pleasure_done": "pleasure_threshold" in summary,
        "final_trials": len(data["final"]),
        "final_expected": n_final,
        "final_done": len(data["final"]) >= n_final,
        "any_data": subject_dir(subject, root).is_dir(),
        "summary": summary,
    }


def available_steps(state):
    """Steps that can run now: each stage needs the previous one's results."""
    steps = [FULL, ANNOYANCE]
    if state["annoyance_done"]:
        steps.append(PLEASURE)
    if state["pleasure_done"]:
        steps.append(FINAL)
    return steps


def next_step(state):
    if not state["annoyance_done"]:
        return FULL
    if not state["pleasure_done"]:
        return PLEASURE
    return FINAL


def progress_text(state):
    """Short status lines for the step dialog."""
    summary = state["summary"]

    def value(key):
        found = number(summary.get(key))
        return "-" if found is None else f"{found:.3f}"

    lines = []
    if not state["any_data"]:
        return "No data saved yet for this participant."
    if state["annoyance_done"]:
        lines.append(f"Annoyance threshold: {value('annoyance_threshold')}   "
                     f"safe ceiling: {value('safe_ceiling')}")
    else:
        lines.append("Annoyance threshold: not done")
    if state["pleasure_done"]:
        lines.append(f"Pleasure threshold: {value('pleasure_threshold')}")
    else:
        lines.append("Pleasure threshold: not done")
    levels = summary.get("final_intensities")
    if levels:
        lines.append("Final intensities: "
                     + ", ".join(f"{float(level):.3f}" for level in levels))
    lines.append(f"Final trials saved: {state['final_trials']}"
                 f"/{state['final_expected']}")
    return "\n".join(lines)


_REVIEW = re.compile(
    r"Experimenter review\s*[—-]\s*(?P<title>[^\n]*)\n(?P<message>.*)\n"
    r"(?P<options>ENTER: continue[^\n]*)",
    re.S,
)
_MANUAL = re.compile(r"M: enter a manual (?P<label>.+?)\s*:?\s*$")


def parse_review(prompt):
    """psychopy_fun.show_break_review's terminal prompt -> its parts.

    Returns dict(title, message, manual_label) or None if not a review prompt.
    manual_label is None when no manual value can be entered.
    """
    match = _REVIEW.search(prompt)
    if not match:
        return None
    manual = _MANUAL.search(match["options"].strip())
    return {
        "title": match["title"].strip(),
        "message": match["message"].strip(),
        "manual_label": manual["label"] if manual else None,
    }
