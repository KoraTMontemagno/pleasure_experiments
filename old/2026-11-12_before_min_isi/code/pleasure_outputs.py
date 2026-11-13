import csv
import os
from datetime import datetime
from pathlib import Path


OUTPUT_CATEGORIES = {
    "pain": "pain",
    "pleasure": "pleasure",
    "validation": "validation",
    "experiment": "experiment",
}


RESPONSE_LABELS = {0: "No", 1: "Yes", 1000: "Painful"}

# One row per stimulus, all stages (experiment folder): for troubleshooting
# and the live vibrator plot of the experimenter monitor.
TIMING_FIELDS = [
    "subject", "phase", "trial", "intensity", "simulated",
    "stim_duration_planned", "stim_duration_actual",
    "jitter_pre_planned", "jitter_pre_actual",
    "jitter_post_planned", "jitter_post_actual",
    "response", "intensity_rating", "orgasm_reports",
    "fixation_onset", "stim_onset", "stim_offset", "response_onset",
    "response_time", "trial_end", "trial_duration",
]
PLANNED_FIELDS = ["phase", "trial", "intensity", "stimulus_type"]
AROUSAL_FIELDS = ["timestamp", "subject", "phase", "moment", "trials_done",
                  "before_trial", "rating"]


def now_iso():
    return datetime.now().isoformat(timespec="milliseconds")


def append_csv(path, fieldnames, row):
    """Append one row (header written for a new file).

    A file written with an older set of columns is first rewritten with the
    current header (old rows keep their values, new columns stay empty), so
    columns never shift when a field is added.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            old_fields, old_rows = reader.fieldnames, list(reader)
        if old_fields != list(fieldnames):
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames,
                                        extrasaction="ignore")
                writer.writeheader()
                writer.writerows(old_rows)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames,
                                extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def timing_path(subject):
    return participant_output_dir(subject, "experiment") / f"sub-{subject}_trial_timing.csv"


def arousal_path(subject):
    return participant_output_dir(subject, "experiment") / f"sub-{subject}_arousal_ratings.csv"


def planned_path(subject):
    return participant_output_dir(subject, "experiment") / f"sub-{subject}_planned_order.csv"


def write_planned_order(subject, phase, intensities, stimulus_types=None):
    """Save the planned intensity order of a phase (replaces that phase's rows)."""
    path = planned_path(subject)
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            rows = [r for r in csv.DictReader(handle) if r["phase"] != phase]
    for trial, intensity in enumerate(intensities, start=1):
        rows.append({"phase": phase, "trial": trial,
                     "intensity": f"{float(intensity):.4f}",
                     "stimulus_type": (stimulus_types or {}).get(intensity, "")})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLANNED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def log_trial(phase, trial, total, intensity, response, vas=None, note=""):
    """One line per trial in the experimenter log, e.g.
    'Final experiment       12/90   intensity 0.386  Yes      VAS 45'"""
    label = RESPONSE_LABELS.get(response, str(response))
    parts = [f"{phase:<22} {trial:>3}/{total:<3}",
             f"intensity {float(intensity):.3f}", f"{label:<7}"]
    if vas is not None:
        parts.append(f"VAS {float(vas):.0f}")
    if note:
        parts.append(note)
    print("  ".join(parts))


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def participant_output_dir(subject, category):
    try:
        folder = OUTPUT_CATEGORIES[category]
    except KeyError as exc:
        raise ValueError(f"Unknown participant output category: {category}") from exc
    return Path("data") / f"sub-{subject}" / folder


def plot_response_summary(records, output_path, title):
    plt = _pyplot()

    responses_by_intensity = {}
    response_labels = RESPONSE_LABELS
    for record in records:
        response = record["response"]
        if response not in response_labels:
            raise ValueError(f"Unexpected pleasure response code: {response}")
        intensity = round(float(record["intensity"]), 6)
        counts = responses_by_intensity.setdefault(
            intensity,
            {label: 0 for label in response_labels.values()},
        )
        counts[response_labels[response]] += 1

    intensities = sorted(responses_by_intensity)
    figure, axis = plt.subplots(figsize=(8, 5))
    if intensities:
        bottoms = [0] * len(intensities)
        colors = {"No": "dimgray", "Yes": "forestgreen", "Painful": "indianred"}
        for label in ("Yes", "No", "Painful"):
            heights = [
                responses_by_intensity[intensity][label]
                for intensity in intensities
            ]
            axis.bar(
                [f"{intensity:g}" for intensity in intensities],
                heights,
                bottom=bottoms,
                label=label,
                color=colors[label],
            )
            bottoms = [
                bottom + height
                for bottom, height in zip(bottoms, heights)
            ]
        axis.legend(title="Response")
    else:
        axis.text(
            0.5,
            0.5,
            "No trials recorded",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
    axis.set(
        xlabel="Vibration intensity",
        ylabel="Number of trials",
        title=title,
    )
    axis.grid(axis="y", alpha=0.2)
    figure.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=300)
    plt.close(figure)
    return output_path


def plot_vas_by_intensity(records, output_path, title):
    plt = _pyplot()

    ratings_by_intensity = {}
    for record in records:
        rating = record.get("intensity_rating")
        if rating is None:
            continue
        intensity = round(float(record["intensity"]), 6)
        ratings_by_intensity.setdefault(intensity, []).append(float(rating))

    intensities = sorted(ratings_by_intensity)
    figure, axis = plt.subplots(figsize=(8, 5))
    if intensities:
        axis.boxplot(
            [ratings_by_intensity[intensity] for intensity in intensities]
        )
        axis.set_xticks(range(1, len(intensities) + 1))
        axis.set_xticklabels([f"{intensity:g}" for intensity in intensities])
    else:
        axis.text(
            0.5,
            0.5,
            "No VAS ratings recorded",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
    axis.set(
        xlabel="Vibration intensity",
        ylabel="Pleasure intensity VAS (0–100)",
        ylim=(0, 100),
        title=title,
    )
    axis.grid(axis="y", alpha=0.2)
    figure.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=300)
    plt.close(figure)
    return output_path


def check_thresholds_files(subject, directories):
    """
    Check whether a subject-specific folder already exists and
    list all files inside it.

    Parameters
    ----------
    subject : str
        Subject number, e.g. "01"

    directories : list
        Parent directories to search, e.g.
        ["data", "subject_temperatures"]

    Returns
    -------
    bool
        True if the experiment should proceed.
        False if the user chooses to cancel.
    """

    subject_folder = f"sub-{subject}"

    existing_files = {}

    for directory in directories:

        subject_path = os.path.join(directory, subject_folder)

        if not os.path.exists(subject_path):
            continue

        files_in_folder = []

        for root, dirs, files in os.walk(subject_path):

            for filename in files:
                filepath = os.path.join(root, filename)
                files_in_folder.append(filepath)

        if files_in_folder:
            existing_files[directory] = sorted(files_in_folder)

    # --------------------------------------------------
    # No files found
    # --------------------------------------------------

    if not existing_files:

        print(
            f"\nNo existing files found for participant "
            f"{subject_folder}."
        )

        return True

    # --------------------------------------------------
    # Print existing files
    # --------------------------------------------------

    # Short summary: number of files per stage folder (not every file).
    print(f"\nExisting data for {subject_folder}:")
    for directory, files in existing_files.items():
        per_folder = {}
        for filepath in files:
            folder = os.path.relpath(filepath, os.path.join(directory, subject_folder))
            folder = folder.split(os.sep)[0] if os.sep in folder else "."
            per_folder[folder] = per_folder.get(folder, 0) + 1
        print(f"  {directory}/{subject_folder}/  "
              + ", ".join(f"{name}: {n} files" for name, n in sorted(per_folder.items())))

    # --------------------------------------------------
    # Ask whether to proceed
    # --------------------------------------------------

    while True:

        answer = input(
            "\nData already exists for this participant.\n"
            "Do you want to proceed? [y/n]: "
        ).strip().lower()

        if answer in ("y", "yes"):

            print("\nProceeding...\n")
            return True

        elif answer in ("n", "no"):

            print("\nExperiment cancelled.")
            return False

        else:

            print("Please enter 'y' or 'n'.")
