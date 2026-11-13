from pathlib import Path


OUTPUT_CATEGORIES = {
    "pain": "pain",
    "pleasure": "pleasure",
    "validation": "validation",
    "experiment": "experiment",
}


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
    response_labels = {0: "No", 1: "Yes", 1000: "Painful"}
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
        ylabel="VAS intensity rating (0–100)",
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
