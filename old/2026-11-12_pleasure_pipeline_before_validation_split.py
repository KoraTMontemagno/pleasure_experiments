import numpy as np
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import random

from .display import as_display
from .pleasure_outputs import (
    log_trial,
    write_planned_order,
    participant_output_dir,
    plot_response_summary,
    plot_vas_by_intensity,
)


MAX_VALIDATION_RUNS = 2


def calculate_safe_ceiling(
    threshold,
    uncertainty,
    safety_margin_sd,
    minimum_intensity,
    maximum_intensity,
):
    values = (threshold, uncertainty, safety_margin_sd, minimum_intensity, maximum_intensity)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Threshold and intensity settings must be finite numbers.")
    if uncertainty < 0 or safety_margin_sd < 0:
        raise ValueError("Uncertainty and safety margin must be nonnegative.")
    if minimum_intensity >= maximum_intensity:
        raise ValueError("minimum_intensity must be below maximum_intensity.")

    safe_ceiling = min(
        maximum_intensity,
        threshold - 0.1, #I am conservative to begin with
    ) 
    if safe_ceiling <= minimum_intensity:
        raise ValueError(
            "The annoyance threshold leaves insufficient range below the "
            "configured minimum intensity."
        )
        
    return safe_ceiling


def select_initial_validation_levels(
    pain_threshold,
    pleasure_threshold,
    minimum_allowed,
    maximum_allowed,
    safe_ceiling,
    adjustment_step,
):
    values = (
        pain_threshold,
        pleasure_threshold,
        minimum_allowed,
        maximum_allowed,
        safe_ceiling,
        adjustment_step,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Validation thresholds and bounds must be finite.")
    if adjustment_step <= 0:
        raise ValueError("validation_adjustment_step must be positive.")
    if pain_threshold < 0.2:
        raise ValueError(
            "Estimated pain threshold is below 0.2; the participant is "
            "excluded from the pleasure stages."
        )
    if pain_threshold < 0.4:
        levels = (0.1, 0.2, 0.3)
        if minimum_allowed > levels[0] or maximum_allowed < levels[-1]:
            raise ValueError(
                "The 0.1/0.2/0.3 validation levels are outside the configured "
                "device intensity range."
            )
        return levels

    target_maximum = 0.5 if pain_threshold <= 0.5 else safe_ceiling
    target_maximum = min(target_maximum, maximum_allowed)
    if target_maximum <= minimum_allowed + 2 * adjustment_step:
        raise ValueError(
            "The selected maximum does not leave room for three distinct "
            "validation levels with the configured minimum step."
        )

    lowest_middle = (target_maximum + minimum_allowed) / 2
    highest_middle = target_maximum - adjustment_step
    middle = min(max(pleasure_threshold, lowest_middle), highest_middle)
    step = target_maximum - middle
    minimum = middle - step
    minimum, middle, target_maximum = (
        round(value, 10) for value in (minimum, middle, target_maximum)
    )
    if (
        step + 1e-12 < adjustment_step
        or minimum < minimum_allowed - 1e-12
    ):
        raise ValueError(
            "Could not select three symmetric validation levels within the "
            "device range."
        )
    return tuple(round(value, 10) for value in (minimum, middle, target_maximum))


def adjust_validation_levels(
    levels,
    painful_counts,
    adjustment_step,
    minimum_allowed,
):
    """Apply the specified pain-response adjustments to a validation range."""
    minimum, threshold, maximum = levels
    threshold_or_minimum_pain = (
        painful_counts.get("minimum", 0) > 0
        or painful_counts.get("threshold", 0) > 0
    )
    maximum_pain_twice = painful_counts.get("maximum", 0) >= 2
    if not threshold_or_minimum_pain and not maximum_pain_twice:
        return None

    if threshold_or_minimum_pain:
        minimum -= adjustment_step
        threshold -= adjustment_step
        maximum -= adjustment_step

    if maximum_pain_twice:
        maximum -= adjustment_step
        if maximum - threshold < adjustment_step:
            threshold = maximum - adjustment_step
        minimum = 2 * threshold - maximum

    levels = tuple(round(value, 10) for value in (minimum, threshold, maximum))
    if levels[0] < minimum_allowed:
        raise ValueError(
            "Pain/annoyance during validation required lowering the intensity "
            "range below the configured device minimum."
        )
    if not levels[0] < levels[1] < levels[2]:
        raise ValueError(
            "Could not keep three ordered validation intensities after "
            "adjusting for painful responses."
        )
    return levels


def automatic_ceiling(computed_ceiling, minimum_allowed, maximum_allowed):
    """Raise the automatic ceiling to 0.5 where device bounds allow."""
    if not all(
        math.isfinite(value)
        for value in (computed_ceiling, minimum_allowed, maximum_allowed)
    ):
        raise ValueError("Automatic ceiling settings must be finite numbers.")
    if minimum_allowed >= maximum_allowed:
        raise ValueError("minimum_allowed must be below maximum_allowed.")
    return min(maximum_allowed, max(computed_ceiling, 0.5))


def automatic_fallback_intensities(minimum_allowed, maximum_allowed):
    levels = (0.2, 0.3, 0.4)
    if minimum_allowed > levels[0] or maximum_allowed < levels[-1]:
        raise ValueError(
            "Automatic fallback intensities 0.2/0.3/0.4 are outside the "
            "configured device intensity range."
        )
    return levels


def pseudorandom_balanced_order(levels, n_trials, seed=None):
    if len(levels) != 3 or len(set(levels)) != 3:
        raise ValueError("Exactly three distinct intensity levels are required.")
    if n_trials < 1 or n_trials % len(levels) != 0:
        raise ValueError("n_trials must be a positive multiple of three.")

    rng = random.Random(seed)
    order = []
    for _ in range(n_trials // len(levels)):
        group = list(levels)
        rng.shuffle(group)
        if order and group[0] == order[-1]:
            group = group[1:] + group[:1]
        order.extend(group)
    return order


def _write_trial_log(path, rows):
    fieldnames = [
        "timestamp",
        "subject",
        "trial",
        "intensity",
        "stimulus_type",
        "response",
        "marker_position",
        "intensity_rating",
        "orgasm_reports",
        "wait_time",
        "response_jitter",
        "trial_start_time",
        "trial_end_time",
        "min_trial_duration",
        "trial_duration",
        "validation_cycle",
        "validation_intensity",
    ]
    with path.open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _summary_path(subject):
    return (
        participant_output_dir(subject, "pleasure")
        / f"sub-{subject}_pleasure_pipeline_summary.json"
    )


def _load_summary(subject):
    path = _summary_path(subject)
    if not path.is_file():
        raise FileNotFoundError(
            f"Pipeline summary not found for participant {subject}: {path}. "
            "Run the earlier stage first."
        )
    with path.open(encoding="utf-8") as summary_file:
        return json.load(summary_file)


def _save_summary(subject, summary):
    path = _summary_path(subject)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2)
    print(f"Pipeline progress saved: {path}")


def _create_display(language="en"):
    from .psychopy_fun import psycho_stuff

    return psycho_stuff(
        language=language,
        instruction_text=(
            "The experiment will begin shortly.\n\n"
            "Please wait for the experimenter."
        )
    )


def _threshold_summary_fields(stage, result):
    return {
        f"{stage}_threshold": result["threshold"],
        f"{stage}_threshold_estimated": result["estimated_threshold"],
        f"{stage}_threshold_manually_overridden": result[
            "manually_overridden"
        ],
        f"{stage}_threshold_std": result["std"],
    }


def run_final_intensity_validation(
    subject,
    display,
    minimum_allowed,
    initial_minimum,
    initial_threshold,
    initial_maximum,
    adjustment_step,
    stim_duration,
    jitter_wait,
    jitter_response,
    min_isi=10.0,
    isi_jitter=0.0,
    simulate_device=False,
    language="en",
    automatic_mode=False,
):
    from .psychopy_fun import show_break_review
    from .stimulation_utils import run_trial

    if not all(
        math.isfinite(value)
        for value in (
            initial_minimum,
            initial_threshold,
            initial_maximum,
            minimum_allowed,
            adjustment_step,
        )
    ):
        raise ValueError("Validation intensity settings must be finite numbers.")
    if adjustment_step <= 0:
        raise ValueError("validation_adjustment_step must be positive.")
    if not initial_minimum < initial_threshold < initial_maximum:
        raise ValueError(
            "Validation values must satisfy minimum < threshold < maximum."
        )

    display = as_display(display)
    win = display.win
    accepted, _ = show_break_review(
        win,
        title="Validation intensities",
        message=(
            "The pleasure threshold, minimum, and maximum will each be "
            "presented twice in an interleaved order. Pain at the minimum "
            "or threshold lowers the full range. The maximum is lowered only "
            "if both maximum presentations are painful. Every adjusted range "
            "is retested from the beginning, up to two runs. If the last run "
            "does not pass, pleasure reported at the threshold or maximum "
            "allows those levels to be retained."
        ),
        language=language,
        automatic_mode=automatic_mode,
        subject=subject,
        phase="validation",
    )
    if not accepted:
        return None

    output_dir = participant_output_dir(subject, "validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"sub-{subject}_pleasure_validation_trials.csv"
    minimum = initial_minimum
    threshold = initial_threshold
    maximum = initial_maximum
    trial_number = 0
    cycle_number = 0
    records = []
    accepted_by_pleasure = False
    validation_passed = False

    while cycle_number < MAX_VALIDATION_RUNS:
        cycle_number += 1
        first_pass = ["minimum", "threshold", "maximum"]
        random.shuffle(first_pass)
        second_pass = first_pass.copy()
        random.shuffle(second_pass)
        while second_pass[0] == first_pass[-1]:
            random.shuffle(second_pass)
        schedule = first_pass + second_pass
        painful_counts = {"minimum": 0, "threshold": 0, "maximum": 0}

        for cycle_trial_number, level_name in enumerate(schedule, start=1):
            trial_number += 1
            level = {
                "minimum": minimum,
                "threshold": threshold,
                "maximum": maximum,
            }[level_name]
            trial = run_trial(
                vibr=level,
                display=display,
                stim_duration=stim_duration,
                jitter_wait=jitter_wait,
                jitter_response=jitter_response,
                min_isi=min_isi,
                isi_jitter=isi_jitter,
                simulate_device=simulate_device,
                response_mode="pleasure",
                collect_intensity_rating=False,
                subject=subject,
                participant_phase="validation",
                trial_number=trial_number,
                language=language,
            )
            records.append({
                "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                "subject": subject,
                "trial": trial_number,
                "intensity": level,
                "validation_cycle": cycle_number,
                "validation_intensity": level_name,
                "orgasm_reports": trial.get("orgasm_reports", 0),
                **trial,
            })
            log_trial(
                f"Validation {cycle_number}/{MAX_VALIDATION_RUNS}",
                cycle_trial_number,
                6,
                level,
                trial["response"],
                note=level_name,
                duration=trial.get("trial_duration"),
            )
            _write_trial_log(log_path, records)
            if trial["response"] == 1000:
                painful_counts[level_name] += 1

        plot_response_summary(
            records[-len(schedule):],
            output_dir
            / f"sub-{subject}_pleasure_validation_cycle-{cycle_number:02d}_responses.png",
            f"Validation cycle {cycle_number}: responses by intensity",
        )

        if not any(painful_counts.values()):
            validation_passed = True
            break

        adjustment_failed = False
        try:
            adjusted_levels = adjust_validation_levels(
                (minimum, threshold, maximum),
                painful_counts,
                adjustment_step,
                minimum_allowed,
            )
        except ValueError as exc:
            print(
                f"Validation stopped safely: {exc} "
                "No further validation stimuli will be delivered."
            )
            adjusted_levels = None
            adjustment_failed = True

        pleasure_reported_at_key_level = any(
            record["validation_cycle"] == cycle_number
            and record["validation_intensity"] in ("threshold", "maximum")
            and record["response"] == 1
            for record in records
        )
        final_run = cycle_number >= MAX_VALIDATION_RUNS or adjustment_failed
        if final_run:
            if pleasure_reported_at_key_level:
                accepted_by_pleasure = True
                print(
                    "Validation did not pass, but pleasure was reported at "
                    "the threshold or maximum in the last run. Keeping these "
                    "levels and proceeding."
                )
                break
            print(
                "Validation did not pass and no pleasure was reported at the "
                "threshold or maximum in the last run. Stopping."
            )
            return None

        if adjusted_levels is None:
            print(
                "Only one painful response occurred at the maximum; "
                "repeating validation at the same levels."
            )
            continue
        minimum, threshold, maximum = adjusted_levels

    return {
        "validated_minimum": minimum,
        "validated_threshold": threshold,
        "validated_maximum": maximum,
        "levels": (minimum, threshold, maximum),
        "trials": records,
        "log_path": str(log_path),
        "validation_passed": validation_passed,
        "accepted_by_pleasure": accepted_by_pleasure,
        "validation_cycles": cycle_number,
    }


def run_post_validation_habituation(
    subject,
    display,
    intensities,
    stim_duration,
    jitter_wait,
    jitter_response,
    min_isi=10.0,
    isi_jitter=0.0,
    simulate_device=False,
    language="en",
    seed=None,
):
    from .stimulation_utils import run_trial
    display = as_display(display)
    output_dir = participant_output_dir(subject, "experiment")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"sub-{subject}_pleasure_habituation_trials.csv"
    records = []
    safety_stop = False

    # One trial per intensity (e.g. the three final levels), shuffled, so the
    # participant meets the whole range before the final trials.
    intensities = [float(value) for value in intensities]
    order = list(np.random.default_rng(seed).permutation(intensities))
    n_trials = len(order)
    write_planned_order(subject, "post-validation habituation", order)
    print(f"\nHabituation: {n_trials} trials")
    for trial_number, intensity in enumerate(order, start=1):
        trial = run_trial(
            vibr=intensity,
            display=display,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            simulate_device=simulate_device,
            response_mode="pleasure",
            collect_intensity_rating=True,
            subject=subject,
            participant_phase="post-validation habituation",
            trial_number=trial_number,
            language=language,
        )
        records.append({
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "subject": subject,
            "trial": trial_number,
            "intensity": intensity,
            "orgasm_reports": trial.get("orgasm_reports", 0),
            **trial,
        })
        log_trial(
            "Habituation",
            trial_number,
            n_trials,
            intensity,
            trial["response"],
            trial.get("intensity_rating"),
            duration=trial.get("trial_duration"),
        )
        _write_trial_log(log_path, records)

    return {
        "trials": records,
        "log_path": str(log_path),
        "safety_stop": safety_stop,
    }


def run_final_pleasure_trials(
    subject,
    levels,
    n_trials,
    stim_duration,
    jitter_wait,
    jitter_response,
    min_isi=10.0,
    isi_jitter=0.0,
    simulate_device=False,
    seed=None,
    display=None,
    language="en",
    automatic_mode=False,
    break_interval=10,
    arousal_every=0,
):
    from .psychopy_fun import event, participant_text, show_break_review
    from .stimulation_utils import check_arousal, run_trial, show_finished

    if not isinstance(break_interval, int) or isinstance(break_interval, bool):
        raise ValueError("break_interval must be a non-negative integer.")
    if break_interval < 0:
        raise ValueError("break_interval must be a non-negative integer.")

    order = pseudorandom_balanced_order(levels, n_trials, seed=seed)
    stimulus_type_by_intensity = dict(
        zip(sorted(levels), ("low", "medium", "high"))
    )
    write_planned_order(subject, "final experiment", order,
                        stimulus_type_by_intensity)
    output_dir = participant_output_dir(subject, "experiment")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"sub-{subject}_pleasure_final_trials.csv"
    records = []
    owns_display = display is None
    win = None

    try:
        if display is None:
            display = _create_display(language)
        display = as_display(display)
        win = display.win
        quality_question = display.quality_question
        quality_question.text = participant_text("pleasure_question", language)
        # No ready screen: the final trials follow the habituation directly.

        for trial_number, intensity in enumerate(order, start=1):
            check_arousal(display, subject, language, "final experiment",
                          trial_number - 1, n_trials, arousal_every)
            trial = run_trial(
                vibr=intensity,
                display=display,
                stim_duration=stim_duration,
                jitter_wait=jitter_wait,
                jitter_response=jitter_response,
                min_isi=min_isi,
                isi_jitter=isi_jitter,
                simulate_device=simulate_device,
                response_mode="pleasure",
                collect_intensity_rating=True,
                subject=subject,
                participant_phase="final experiment",
                trial_number=trial_number,
                language=language,
            )
            records.append({
                "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                "subject": subject,
                "trial": trial_number,
                "intensity": intensity,
                "stimulus_type": stimulus_type_by_intensity[intensity],
                "orgasm_reports": trial.get("orgasm_reports", 0),
                **trial,
            })
            log_trial(
                "Final experiment",
                trial_number,
                n_trials,
                intensity,
                trial["response"],
                trial.get("intensity_rating"),
                duration=trial.get("trial_duration"),
            )
            _write_trial_log(log_path, records)

            if (
                break_interval > 0
                and trial_number % break_interval == 0
                and trial_number < n_trials
            ):
                accepted, _ = show_break_review(
                    win,
                    title="Break",
                    message="The next block will begin when the experimenter continues.",
                    language=language,
                    automatic_mode=automatic_mode,
                    subject=subject,
                    phase="final experiment",
                    trial_number=trial_number,
                )
                if not accepted:
                    raise KeyboardInterrupt(
                        "Aborted during final pleasure trials."
                    )
        # last excitement rating (no reposition screen: nothing follows),
        # then the end-of-experiment screen
        check_arousal(display, subject, language, "final experiment",
                      n_trials, n_trials, arousal_every, reposition=False)
        show_finished(display, language)
    except KeyboardInterrupt as exc:
        print(f"\n{exc}")
    finally:
        if owns_display and win is not None:
            win.close()

    print(f"Final pleasure-trial log: {log_path}")
    plot_response_summary(
        records,
        output_dir / f"sub-{subject}_pleasure_experiment_responses.png",
        "Final experiment: responses by intensity",
    )
    plot_vas_by_intensity(
        records,
        output_dir / f"sub-{subject}_pleasure_experiment_vas.png",
        "Final experiment: pleasure VAS by vibration intensity",
    )
    return records


def run_annoyance_stage(
    subject,
    ntrials,
    habituation,
    stim_duration,
    jitter_wait,
    jitter_response,
    min_isi=10.0,
    isi_jitter=0.0,
    minimum_intensity=0.1,
    maximum_intensity=1.0,
    simulate_device=False,
    display=None,
    language="en",
    automatic_mode=False,
    practice=True,
    arousal_every=0,
):
    from .thresholding import run_threshold

    owns_display = display is None
    if display is None:
        display = _create_display(language)
    try:
        result = run_threshold(
            subject=subject,
            pattern="annoyance",
            ntrials=ntrials,
            habituation=habituation,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            simulate_device=simulate_device,
            min_vibr=minimum_intensity,
            max_vibr=maximum_intensity,
            display=display,
            review_threshold=False,
            language=language,
            automatic_mode=automatic_mode,
            practice=practice,
            arousal_every=arousal_every,
        )
        if result is None:
            return None

        summary = {
            "subject": subject,
            "minimum_intensity": minimum_intensity,
            "maximum_intensity": maximum_intensity,
            "annoyance_ntrials": ntrials,
            "annoyance_pain_free_maximum_stop": result.get(
                "pain_free_maximum_stop", False
            ),
            "annoyance_pain_free_maximum_trials": result.get(
                "pain_free_maximum_trials", 0
            ),
            **_threshold_summary_fields("annoyance", result),
        }
        _save_summary(subject, summary)
        return result
    finally:
        if owns_display:
            display[0].close()


def run_pleasure_threshold_stage(
    subject,
    ntrials,
    stim_duration,
    jitter_wait,
    jitter_response,
    min_isi=10.0,
    isi_jitter=0.0,
    safety_margin_sd=1.0,
    simulate_device=False,
    display=None,
    language="en",
    automatic_mode=False,
    practice=True,
    arousal_every=0,
):
    from .thresholding import run_threshold
    from .psychopy_fun import show_break_review

    summary = _load_summary(subject)
    minimum_intensity = float(summary["minimum_intensity"])
    maximum_intensity = float(summary["maximum_intensity"])
    pain_threshold = float(summary["annoyance_threshold"])
    if pain_threshold < 0.2:
        summary["participant_excluded_for_low_pain_threshold"] = True
        _save_summary(subject, summary)
        print(
            f"Estimated pain threshold {pain_threshold:.3f} is below 0.2; "
            "excluding participant before the pleasure stage."
        )
        return None
    pain_free_maximum_stop = summary.get(
        "annoyance_pain_free_maximum_stop", False
    )
    if pain_free_maximum_stop:
        safe_ceiling = maximum_intensity
    else:
        safe_ceiling = calculate_safe_ceiling(
            pain_threshold,
            float(summary["annoyance_threshold_std"]),
            safety_margin_sd,
            minimum_intensity,
            maximum_intensity,
        )
    if automatic_mode:
        selected_auto_ceiling = automatic_ceiling(
            safe_ceiling,
            minimum_intensity,
            maximum_intensity,
        )
    else:
        selected_auto_ceiling = safe_ceiling
    owns_display = display is None
    if display is None:
        display = _create_display(language)
    try:
        accepted, selected_ceiling = show_break_review(
            display[0],
            title="Review the pleasure-stage ceiling",
            message=(
                (
                    "Four pain-free trials were delivered at maximum "
                    f"intensity. The pleasure-stage ceiling is fixed at "
                    f"{maximum_intensity:.3f}."
                    if pain_free_maximum_stop
                    else
                    f"Proposed pleasure-stage ceiling: "
                    f"{selected_auto_ceiling:.3f}\n"
                    "Enter M in the terminal if you want to set the ceiling manually."
                )
            ),
            threshold=(
                None if pain_free_maximum_stop else selected_auto_ceiling
            ),
            minimum=minimum_intensity,
            maximum=maximum_intensity,
            language=language,
            value_label="ceiling",
            automatic_mode=automatic_mode,
            subject=subject,
            phase="pleasure threshold ceiling review",
        )
        if not accepted:
            return None
        if pain_free_maximum_stop:
            selected_ceiling = maximum_intensity
        elif selected_ceiling is None:
            return None

        result = run_threshold(
            subject=subject,
            pattern="pleasure",
            ntrials=ntrials,
            habituation=0,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            simulate_device=simulate_device,
            min_vibr=minimum_intensity,
            max_vibr=selected_ceiling,
            display=display,
            review_threshold=True,
            language=language,
            automatic_mode=automatic_mode,
            practice=practice,
            arousal_every=arousal_every,
        )
        if result is None:
            return None

        summary.update({
            "safety_margin_sd": safety_margin_sd,
            "safe_ceiling_estimated": safe_ceiling,
            "safe_ceiling": selected_ceiling,
            "safe_ceiling_manually_overridden": not math.isclose(
                selected_ceiling, safe_ceiling
            ) and not automatic_mode and not pain_free_maximum_stop,
            "safe_ceiling_override_reason": (
                "four_pain_free_trials_at_maximum"
                if pain_free_maximum_stop
                else None
            ),
            "safe_ceiling_automatic_floor_applied": (
                automatic_mode
                and selected_ceiling > safe_ceiling
            ),
            "pleasure_ntrials": ntrials,
            **_threshold_summary_fields("pleasure", result),
        })
        _save_summary(subject, summary)
        return result
    finally:
        if owns_display:
            display[0].close()


def run_final_pleasure_stage(
    subject,
    intensity_step,
    final_trials_per_intensity,
    stim_duration,
    jitter_wait,
    jitter_response,
    min_isi=10.0,
    isi_jitter=0.0,
    simulate_device=False,
    seed=None,
    display=None,
    validation_adjustment_step=0.1,
    return_details=False,
    language="en",
    automatic_mode=False,
    practice=True,
    arousal_every=0,
    final_break_interval=10,
):
    from .psychopy_fun import show_break_review

    if (
        not isinstance(final_trials_per_intensity, int)
        or isinstance(final_trials_per_intensity, bool)
        or final_trials_per_intensity < 1
    ):
        raise ValueError("final_trials_per_intensity must be a positive integer.")
    if (
        not isinstance(final_break_interval, int)
        or isinstance(final_break_interval, bool)
        or final_break_interval < 0
    ):
        raise ValueError("final_break_interval must be a non-negative integer.")
    final_n_trials = final_trials_per_intensity * 3

    summary = _load_summary(subject)
    required = (
        "minimum_intensity",
        "maximum_intensity",
        "annoyance_threshold",
        "safe_ceiling",
        "pleasure_threshold",
        "pleasure_threshold_std",
    )
    missing = [key for key in required if key not in summary]
    if missing:
        raise ValueError(
            "Earlier pipeline stages are incomplete; missing: "
            + ", ".join(missing)
        )

    owns_display = display is None
    if display is None:
        display = _create_display(language)
    try:
        original_threshold = float(summary["pleasure_threshold"])
        pain_threshold = float(summary["annoyance_threshold"])
        minimum_allowed = float(summary["minimum_intensity"])
        maximum_allowed = float(summary["maximum_intensity"])
        selected_ceiling = float(summary["safe_ceiling"])
        if automatic_mode:
            selected_ceiling = automatic_ceiling(
                selected_ceiling,
                minimum_allowed,
                maximum_allowed,
            )
        fallback_used = False
        try:
            (
                initial_minimum,
                initial_threshold,
                initial_maximum,
            ) = select_initial_validation_levels(
                pain_threshold=pain_threshold,
                pleasure_threshold=original_threshold,
                minimum_allowed=minimum_allowed,
                maximum_allowed=maximum_allowed,
                safe_ceiling=selected_ceiling,
                adjustment_step=validation_adjustment_step,
            )
        except ValueError as exc:
            if (
                not automatic_mode
                or "below 0.2" in str(exc)
                or "device intensity range" in str(exc)
            ):
                raise
            (
                initial_minimum,
                initial_threshold,
                initial_maximum,
            ) = automatic_fallback_intensities(
                minimum_allowed,
                maximum_allowed,
            )
            fallback_used = True
            print(
                "Automatic mode: threshold range unavailable; using "
                "fallback levels 0.2, 0.3, and 0.4."
            )
        validation = run_final_intensity_validation(
            subject=subject,
            display=display,
            minimum_allowed=float(summary["minimum_intensity"]),
            initial_minimum=initial_minimum,
            initial_threshold=initial_threshold,
            initial_maximum=initial_maximum,
            adjustment_step=validation_adjustment_step,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            simulate_device=simulate_device,
            language=language,
            automatic_mode=automatic_mode,
        )
        if validation is None:
            return None

        final_minimum = validation["validated_minimum"]
        adjusted_threshold = validation["validated_threshold"]
        levels = validation["levels"]
        print(
            "Final three pleasure-test intensities: "
            + ", ".join(f"{level:.3f}" for level in levels)
        )
        review_title = "Review the final trial intensities"
        review_message = "Selected levels: " + ", ".join(
            f"{level:.3f}" for level in levels
        )
        if validation["accepted_by_pleasure"]:
            review_title = "Review the provisionally accepted intensities"
            review_message = (
                "Validation did not pass. Pleasure was reported at the "
                "threshold or maximum in the last run, so these levels will "
                "be retained:\n"
                + ", ".join(f"{level:.3f}" for level in levels)
            )
        accepted, _ = show_break_review(
            display[0],
            title=review_title,
            message=review_message,
            language=language,
            automatic_mode=automatic_mode,
            subject=subject,
            phase="final intensity review",
        )
        if not accepted:
            return None

        # The intensity VAS is first used in the post-validation habituation:
        # introduce and practise it here.
        from .psychopy_fun import run_vas_practice

        if practice:
            run_vas_practice(display, subject, language=language)

        habituation = run_post_validation_habituation(
            subject=subject,
            display=display,
            intensities=levels,
            seed=seed,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            simulate_device=simulate_device,
            language=language,
        )
        summary.update({
            "intensity_step": intensity_step,
            "safe_ceiling_automatic_floor_applied": (
                automatic_mode
                and selected_ceiling > float(summary["safe_ceiling"])
            ),
            "automatic_intensity_fallback_used": fallback_used,
            "pleasure_threshold_before_validation": original_threshold,
            "pleasure_threshold": adjusted_threshold,
            "pleasure_threshold_adjusted_for_range": (
                not math.isclose(original_threshold, adjusted_threshold)
            ),
            "final_minimum_intensity": final_minimum,
            "final_maximum_intensity": validation["validated_maximum"],
            "validation_adjustment_step": validation_adjustment_step,
            "validation_trials": validation["trials"],
            "validation_log": validation["log_path"],
            "validation_cycles": validation["validation_cycles"],
            "validation_passed": validation["validation_passed"],
            "validation_accepted_by_pleasure": validation[
                "accepted_by_pleasure"
            ],
            "post_validation_habituation_trials": habituation["trials"],
            "post_validation_habituation_log": habituation["log_path"],
            "final_intensities": levels,
            "final_n_trials": final_n_trials,
            "final_trials_per_intensity": final_trials_per_intensity,
            "final_break_interval": final_break_interval,
            "random_seed": seed,
        })
        _save_summary(subject, summary)
        if habituation["safety_stop"]:
            return None

        final_trials = run_final_pleasure_trials(
            subject=subject,
            levels=levels,
            n_trials=final_n_trials,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            simulate_device=simulate_device,
            seed=seed,
            display=display,
            language=language,
            automatic_mode=automatic_mode,
            break_interval=final_break_interval,
            arousal_every=arousal_every,
        )
        if return_details:
            return {
                "trials": final_trials,
                "final_intensities": levels,
                "validated_maximum": validation["validated_maximum"],
                "final_minimum": final_minimum,
                "pleasure_threshold": adjusted_threshold,
                "validation_passed": validation["validation_passed"],
                "validation_accepted_by_pleasure": validation[
                    "accepted_by_pleasure"
                ],
            }
        return final_trials
    except KeyboardInterrupt as exc:
        print(f"\n{exc}")
        return None
    finally:
        if owns_display:
            display[0].close()


def run_pleasure_pipeline(
    subject,
    annoyance_ntrials,
    pleasure_ntrials,
    habituation,
    stim_duration,
    jitter_wait,
    jitter_response,
    min_isi=10.0,
    isi_jitter=0.0,
    minimum_intensity=0.1,
    maximum_intensity=1.0,
    intensity_step=0.05,
    safety_margin_sd=1.0,
    final_trials_per_intensity=10,
    final_break_interval=10,
    simulate_device=False,
    seed=None,
    validation_adjustment_step=0.1,
    language="en",
    automatic_mode=False,
    practice=True,
    arousal_every=0,
):
    if (
        not isinstance(final_trials_per_intensity, int)
        or isinstance(final_trials_per_intensity, bool)
        or final_trials_per_intensity < 1
    ):
        raise ValueError("final_trials_per_intensity must be a positive integer.")
    if (
        not isinstance(final_break_interval, int)
        or isinstance(final_break_interval, bool)
        or final_break_interval < 0
    ):
        raise ValueError("final_break_interval must be a non-negative integer.")

    display = _create_display(language)
    try:
        annoyance = run_annoyance_stage(
            subject=subject,
            ntrials=annoyance_ntrials,
            habituation=habituation,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            minimum_intensity=minimum_intensity,
            maximum_intensity=maximum_intensity,
            simulate_device=simulate_device,
            display=display,
            language=language,
            automatic_mode=automatic_mode,
            practice=practice,
            arousal_every=arousal_every,
        )
        if annoyance is None:
            return None

        pleasure = run_pleasure_threshold_stage(
            subject=subject,
            ntrials=pleasure_ntrials,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            safety_margin_sd=safety_margin_sd,
            simulate_device=simulate_device,
            display=display,
            language=language,
            automatic_mode=automatic_mode,
            practice=practice,
            arousal_every=arousal_every,
        )
        if pleasure is None:
            return None

        summary = _load_summary(subject)
        final_result = run_final_pleasure_stage(
            subject=subject,
            intensity_step=intensity_step,
            final_trials_per_intensity=final_trials_per_intensity,
            final_break_interval=final_break_interval,
            stim_duration=stim_duration,
            jitter_wait=jitter_wait,
            jitter_response=jitter_response,
            min_isi=min_isi,
            isi_jitter=isi_jitter,
            simulate_device=simulate_device,
            seed=seed,
            display=display,
            validation_adjustment_step=validation_adjustment_step,
            return_details=True,
            language=language,
            automatic_mode=automatic_mode,
            practice=practice,
            arousal_every=arousal_every,
        )
        if final_result is None:
            return None
        return {
            "annoyance": annoyance,
            "safe_ceiling": summary["safe_ceiling"],
            "pleasure": pleasure,
            "final_intensities": final_result["final_intensities"],
            "final_trials": final_result["trials"],
        }
    finally:
        display[0].close()
