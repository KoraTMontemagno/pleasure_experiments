"""Generate participant-wise plots from the saved pleasure experiment data."""

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PHASE_COLORS = {
    "annoyance threshold": "indianred",
    "pleasure threshold": "forestgreen",
    "final experiment": "tab:purple",
    "post-validation habituation": "tab:blue",
}


def read_csv(path, required_fields):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no CSV header")
        missing = set(required_fields) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def parse_time(value, path, field):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field} timestamp in {path}: {value!r}") from exc


def parse_number(value, path, field):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field} value in {path}: {value!r}") from exc
    return number if math.isfinite(number) else None


def elapsed_minutes(timestamp, start):
    return (timestamp - start).total_seconds() / 60


def participant_axes(figure, subjects, title, ylabel, ylim):
    columns = min(3, len(subjects))
    rows = math.ceil(len(subjects) / columns)
    axes = figure.subplots(rows, columns, squeeze=False, sharey=True)
    figure.suptitle(title, fontsize=15)
    for axis, subject in zip(axes.flat, subjects):
        axis.set_title(subject)
        axis.set_xlabel("Elapsed time (minutes)")
        axis.set_ylabel(ylabel)
        axis.set_ylim(*ylim)
        axis.grid(alpha=0.25)
    for axis in list(axes.flat)[len(subjects):]:
        axis.set_visible(False)
    return axes.flat


def save_arousal_plot(data_dir, output_dir):
    participants = {}
    for path in sorted(data_dir.glob("sub-*/experiment/sub-*_arousal_ratings.csv")):
        rows = read_csv(path, {"timestamp", "phase", "rating"})
        points = []
        for row in rows:
            timestamp = parse_time(row.get("timestamp"), path, "timestamp")
            rating = parse_number(row.get("rating"), path, "rating")
            if timestamp is not None and rating is not None:
                points.append((timestamp, row["phase"], rating))
        if points:
            participants[path.parent.parent.name] = sorted(points)
    if not participants:
        raise FileNotFoundError(f"No timestamped arousal ratings found under {data_dir}")

    figure = plt.figure(figsize=(6 * min(3, len(participants)),
                                 4 * math.ceil(len(participants) / 3)))
    axes = participant_axes(
        figure,
        list(participants),
        "Arousal ratings over the experiment",
        "Arousal rating (0-100)",
        (0, 100),
    )
    phases = set()
    for axis, (_subject, points) in zip(axes, participants.items()):
        start = min(point[0] for point in points)
        grouped = {}
        for timestamp, phase, rating in points:
            grouped.setdefault(phase, []).append(
                (elapsed_minutes(timestamp, start), rating)
            )
        for phase, values in grouped.items():
            values.sort()
            color = PHASE_COLORS.get(phase, "grey")
            axis.plot([x for x, _ in values], [y for _, y in values],
                      color=color, alpha=0.45, linewidth=1)
            axis.scatter([x for x, _ in values], [y for _, y in values],
                         color=color, s=24, label=phase)
            phases.add(phase)
        axis.set_xlim(left=0)
    handles = [
        plt.Line2D([], [], color=PHASE_COLORS.get(phase, "grey"), marker="o",
                   linewidth=1, label=phase)
        for phase in sorted(phases)
    ]
    figure.legend(handles=handles, loc="upper center", ncol=min(4, len(handles)),
                  bbox_to_anchor=(0.5, 0.94), frameon=False)
    figure.tight_layout(rect=(0, 0, 1, 0.88))
    output = output_dir / "arousal_over_time.png"
    figure.savefig(output, dpi=180)
    plt.close(figure)
    return output


def save_intensity_plot(data_dir, output_dir):
    participants = {}
    for path in sorted(data_dir.glob("sub-*/experiment/sub-*_trial_timing.csv")):
        rows = read_csv(path, {"phase", "intensity_rating", "stim_onset"})
        trials = []
        for row in rows:
            phase = row.get("phase", "")
            if phase not in ("post-validation habituation", "final experiment"):
                continue
            timestamp = parse_time(row.get("stim_onset"), path, "stim_onset")
            rating = parse_number(row.get("intensity_rating"), path, "intensity_rating")
            if timestamp is not None and rating is not None:
                trials.append((timestamp, phase, rating))
        if trials:
            all_times = [
                parse_time(row.get("stim_onset"), path, "stim_onset")
                for row in rows
            ]
            start = min(timestamp for timestamp in all_times if timestamp is not None)
            participants[path.parent.parent.name] = (start, sorted(trials))
    if not participants:
        raise FileNotFoundError(f"No timestamped VAS intensity ratings found under {data_dir}")

    figure = plt.figure(figsize=(6 * min(3, len(participants)),
                                 4 * math.ceil(len(participants) / 3)))
    axes = participant_axes(
        figure,
        list(participants),
        "Reported vibration intensity over the experiment",
        "Intensity rating (VAS, 0-100)",
        (0, 100),
    )
    phases = set()
    for axis, (_subject, (start, trials)) in zip(axes, participants.items()):
        grouped = {}
        for timestamp, phase, rating in trials:
            grouped.setdefault(phase, []).append(
                (elapsed_minutes(timestamp, start), rating)
            )
        for phase, values in grouped.items():
            values.sort()
            color = PHASE_COLORS[phase]
            axis.plot([x for x, _ in values], [y for _, y in values],
                      color=color, alpha=0.35, linewidth=0.8)
            axis.scatter([x for x, _ in values], [y for _, y in values],
                         color=color, s=22, label=phase)
            phases.add(phase)
        axis.set_xlim(left=0)
    handles = [
        plt.Line2D([], [], color=PHASE_COLORS[phase], marker="o",
                   linewidth=1, label=phase)
        for phase in sorted(phases)
    ]
    figure.legend(handles=handles, loc="upper center", ncol=len(handles),
                  bbox_to_anchor=(0.5, 0.94), frameon=False)
    figure.tight_layout(rect=(0, 0, 1, 0.88))
    output = output_dir / "reported_intensity_over_time.png"
    figure.savefig(output, dpi=180)
    plt.close(figure)
    return output


def save_pain_plot(data_dir, output_dir):
    participants = {}
    for path in sorted(data_dir.glob("sub-*/pain/sub-*_annoyance_trial_data_detailed.csv")):
        rows = read_csv(path, {"trial", "response", "trial_start_time"})
        trials = []
        for row in rows:
            timestamp = parse_time(row.get("trial_start_time"), path, "trial_start_time")
            response = parse_number(row.get("response"), path, "response")
            trial = parse_number(row.get("trial"), path, "trial")
            if timestamp is None or response is None or trial is None:
                continue
            if response not in (0, 1):
                raise ValueError(f"Expected a binary pain response in {path}: {response}")
            trials.append((timestamp, trial, int(response)))
        if trials:
            participants[path.parent.parent.name] = sorted(trials)
    if not participants:
        raise FileNotFoundError(f"No timestamped annoyance trials found under {data_dir}")

    figure = plt.figure(figsize=(6 * min(3, len(participants)),
                                 4 * math.ceil(len(participants) / 3)))
    axes = participant_axes(
        figure,
        list(participants),
        "Binary pain/annoyance choices over time",
        "Response (0 = No, 1 = Yes)",
        (-0.15, 1.15),
    )
    for axis, (_subject, trials) in zip(axes, participants.items()):
        start = min(trial[0] for trial in trials)
        x_values = [elapsed_minutes(timestamp, start) for timestamp, _, _ in trials]
        responses = [response for _, _, response in trials]
        axis.step(x_values, responses, where="mid", color="indianred", alpha=0.55)
        axis.scatter(x_values, responses, color="indianred", s=28)
        axis.set_yticks([0, 1], labels=["No", "Yes"])
        axis.set_xlim(left=0)
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    output = output_dir / "pain_choices_over_time.png"
    figure.savefig(output, dpi=180)
    plt.close(figure)
    return output


def main():
    default_data_dir = Path(__file__).resolve().parent / "data"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=default_data_dir)
    parser.add_argument("--output-dir", type=Path, default=default_data_dir / "visualizations")
    args = parser.parse_args()
    if not args.data_dir.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {args.data_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for output in (
        save_arousal_plot(args.data_dir, args.output_dir),
        save_intensity_plot(args.data_dir, args.output_dir),
        save_pain_plot(args.data_dir, args.output_dir),
    ):
        print(f"Saved {output}")


if __name__ == "__main__":
    main()
