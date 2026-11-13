import time
from datetime import datetime

import numpy as np

from .psychopy_fun import (
    RESPONSE_LABEL_X,
    VAS_MARKER_COLOR,
    core,
    event,
)
from .display import as_display
from .pleasure_outputs import (
    AROUSAL_FIELDS,
    TIMING_FIELDS,
    append_csv,
    arousal_path,
    now_iso,
    timing_path,
)
from .repeat_vibration import vibrate


def _wait_with_participant_controls(duration, controls, fixation):
    deadline = time.perf_counter() + max(0.0, duration)
    while True:
        controls.process_keys(
            event.getKeys(keyList=["o", "e", "escape"]),
            fixation=fixation,
        )
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        core.wait(min(0.05, remaining))


def update_habituation_vibration(vibr, r):
    """Update staircase temperature after a habituation response."""
    if r == 1:  # Painful
        vibr= max(0.01, vibr - 0.1)
    else:       # Not painful
        vibr = min(1, vibr + 0.1)


    return float(vibr)

def collect_vas(display, controls, question):
    """Rate on the 0-100 VAS: LEFT/RIGHT move, UP confirms. Returns the rating.

    The question text is set every time, so a previous screen (e.g. the
    practice prompts) never leaks into the real rating.
    """
    display = as_display(display)
    win, fixation = display.win, display.fixation
    text, scale = display.intensity_question, display.intensity_scale
    text.text = question
    scale.reset()
    scale.setRating(0)
    scale.markerColor = scale.markerFillColor = VAS_MARKER_COLOR
    value = 0
    while True:
        text.draw()
        scale.draw()
        display.intensity_instruction.draw()
        controls.draw()
        win.flip()
        keys = event.getKeys(keyList=["left", "right", "up", "escape", "o", "e"])
        controls.process_keys(keys, fixation=fixation)
        if "left" in keys:
            value = max(value - 1, 0)
            scale.setRating(value)
        elif "right" in keys:
            value = min(value + 1, 100)
            scale.setRating(value)
        elif "up" in keys:
            scale.markerColor = scale.markerFillColor = "lightcoral"
            text.draw()
            scale.draw()
            controls.draw()
            win.flip()
            _wait_with_participant_controls(1, controls, fixation)
            return float(value)


def arousal_moment(trials_done, total, every_n):
    """'start' / 'after trial N' / 'end', or None when no check is due."""
    if not every_n or every_n <= 0:
        return None
    if trials_done == 0:
        return "start"
    if trials_done >= total:
        return "end"
    if trials_done % every_n == 0:
        return f"after trial {trials_done}"
    return None


def check_arousal(display, subject, language, phase, trials_done, total,
                  every_n, reposition=True):
    """Every n trials (and at start/end): excitement VAS, then the screen to
    reposition the vibrator (ENTER to continue). Saved to
    sub-<ID>_arousal_ratings.csv in the experiment folder."""
    moment = arousal_moment(trials_done, total, every_n)
    if moment is None:
        return None
    from .participant_controls import get_participant_controls
    from .psychopy_fun import participant_text

    display = as_display(display)
    controls = get_participant_controls(display.win, subject, language)
    controls.set_context(phase, f"arousal {moment}")
    rating = collect_vas(display, controls,
                         participant_text("arousal_question", language))
    append_csv(arousal_path(subject), AROUSAL_FIELDS, {
        "timestamp": now_iso(), "subject": subject, "phase": phase,
        "moment": moment, "trials_done": trials_done,
        # trial number that follows the rating (empty after the last trial)
        "before_trial": trials_done + 1 if trials_done < total else "",
        "rating": rating,
    })
    print(f"Arousal ({phase}, {moment}): {rating:.0f}")
    if not reposition:  # e.g. after the very last trial: nothing follows
        return rating

    text = display.ready_text
    previous = text.text
    text.text = participant_text("reposition", language)
    try:
        while True:
            text.draw()
            controls.draw()
            display.win.flip()
            keys = event.waitKeys(keyList=["return", "space", "escape", "o", "e"])
            controls.process_keys(keys, fixation=display.fixation)
            if {"return", "space"}.intersection(keys):
                break
    finally:
        text.text = previous
    return rating


def show_finished(display, language):
    """End of the whole experiment: thank-you screen until the experimenter
    presses ENTER (no O/E banner: the participant has nothing left to do)."""
    from .psychopy_fun import participant_text

    display = as_display(display)
    display.ready_text.text = participant_text("finished", language)
    while True:
        display.ready_text.draw()
        display.win.flip()
        keys = event.waitKeys(keyList=["return", "space", "escape"])
        if keys:
            return


def run_trial(
    vibr,
    display,
    stim_duration,
    jitter_wait,
    jitter_response,
    simulate_device=False,
    response_mode="pleasure",
    collect_intensity_rating=False,
    subject="unknown",
    participant_phase="",
    trial_number="",
    language="en",
):
    """
    Deliver one stimulus and collect one response.

    display: the participant-screen objects from psycho_stuff().
    response_mode "pleasure" offers ← No / Yes → / ↓ painful (1000);
    "annoyance" offers ← No / Yes →.
    Returns the response, marker position, VAS rating and timing.
    """
    display = as_display(display)
    win, fixation = display.win, display.fixation
    quality_pleasure = display.quality
    quality_question_pleasure = display.quality_question
    no_label, yes_label, pain_label = (
        display.no_label, display.yes_label, display.pain_label)

    trial_start_perf = time.perf_counter()
    trial_start_datetime = datetime.now().isoformat(
        timespec="milliseconds"
    )
    from .participant_controls import get_participant_controls

    controls = get_participant_controls(win, subject, language)
    controls.set_context(participant_phase or response_mode, trial_number)

    wait_time = 0.0
    response_jitter = 0.0


    controls.process_keys(
        event.getKeys(keyList=["o", "e", "escape"]),
        fixation=fixation,
    )

    # Fixation
    win.mouseVisible = False
    # No O/E banner on the fixation cross (keys still work).
    fixation.draw()
    win.flip()
    fixation_onset = datetime.now()

    # Pre-stimulation jitter
    wait_time = float(np.random.uniform(jitter_wait - 0.5, jitter_wait + 0.5))
    _wait_with_participant_controls(max(0, wait_time), controls, fixation)

    # Deliver the stimulus (connection to the device is kept for the session)
    stim_onset, stim_offset = vibrate(stim_duration, vibr,
                                      simulate_device=simulate_device)

    # Jitter post response
    response_jitter = float(
            np.random.uniform(
                jitter_response - 0.5,
                jitter_response + 0.5
            )
        )
    _wait_with_participant_controls(
        max(0, response_jitter),
        controls,
        fixation,
    )

    # Collect response using the original PsychoPy rating scale.
    response_onset = datetime.now()  # response screen (first flip follows)
    response_time = None
    quality_pleasure.reset()
    confirmed = False
    marker_position = None
    no_label.pos = (-RESPONSE_LABEL_X, -100)
    yes_label.pos = (RESPONSE_LABEL_X, -100)
    no_label.color = "white"
    yes_label.color = "white"
    if response_mode not in {"annoyance", "pleasure"}:
        raise ValueError("response_mode must be 'annoyance' or 'pleasure'")
    # Pleasure responses: DOWN reports pain/annoyance (response 1000)
    # without stopping the experiment.
    allow_pain = response_mode == "pleasure" and pain_label is not None
    if allow_pain:
        pain_label.color = "white"
    response_keys = ["left", "right", "escape", "o", "e"]
    if allow_pain:
        response_keys.append("down")

    def draw_response_options():
        no_label.draw()
        yes_label.draw()
        if allow_pain:
            pain_label.draw()
        quality_question_pleasure.draw()
        controls.draw()

    while not confirmed:
        quality_pleasure.draw()
        draw_response_options()
        win.flip()
        keys = event.getKeys(keyList=response_keys)
        controls.process_keys(keys, fixation=fixation)

        for key in keys:
            if key == "left":
                quality_pleasure.markerPos = 1
                marker_position = 1
                no_label.color = "lightcoral"
            elif key == "right":
                quality_pleasure.markerPos = 2
                marker_position = 2
                yes_label.color = "lightcoral"
            elif key == "down" and allow_pain:
                marker_position = 3
                pain_label.color = "lightcoral"
            else:
                continue
            draw_response_options()
            win.flip()
            response_time = datetime.now()
            confirmed = True
            break
    # Keep the chosen (coloured) answer on screen for 1 s, also when the VAS
    # follows - otherwise the colour change is never visible.
    _wait_with_participant_controls(1, controls, fixation)

    intensity_rating = None
    if collect_intensity_rating:
        from .psychopy_fun import participant_text

        intensity_rating = collect_vas(
            display, controls, participant_text("intensity_question", language))

    fixation.draw()
    win.flip()

    # marker 1 = No (0), 2 = Yes (1), 3 = painful/annoying (1000)
    r = {3: 1000, 2: 1}.get(marker_position, 0)

    trial_end_perf = time.perf_counter()
    trial_end_datetime = datetime.now().isoformat(
        timespec="milliseconds"
    )
    trial_duration = trial_end_perf - trial_start_perf

    # Preserve the minimum trial duration.
    if trial_duration <= 15:
        _wait_with_participant_controls(
            max(0, 15 - trial_duration),
            controls,
            fixation,
        )
        trial_end_perf = time.perf_counter()
        trial_end_datetime = datetime.now().isoformat(
            timespec="milliseconds"
        )
        trial_duration = trial_end_perf - trial_start_perf

    orgasm_reports = controls.consume_orgasm_reports()

    def iso(moment):
        return moment.isoformat(timespec="milliseconds") if moment else ""

    def seconds(start, end):
        return round((end - start).total_seconds(), 3) if start and end else ""

    # One row per stimulus for troubleshooting / the experimenter monitor.
    append_csv(timing_path(subject), TIMING_FIELDS, {
        "subject": subject, "phase": participant_phase or response_mode,
        "trial": trial_number, "intensity": round(float(vibr), 4),
        "simulated": bool(simulate_device),
        "stim_duration_planned": stim_duration,
        "stim_duration_actual": seconds(stim_onset, stim_offset),
        "jitter_pre_planned": round(wait_time, 3),
        "jitter_pre_actual": seconds(fixation_onset, stim_onset),
        "jitter_post_planned": round(response_jitter, 3),
        "jitter_post_actual": seconds(stim_offset, response_onset),
        "response": r, "intensity_rating": intensity_rating,
        "orgasm_reports": orgasm_reports,
        "fixation_onset": iso(fixation_onset), "stim_onset": iso(stim_onset),
        "stim_offset": iso(stim_offset), "response_onset": iso(response_onset),
        "response_time": iso(response_time), "trial_end": trial_end_datetime,
        "trial_duration": round(trial_duration, 3),
    })

    return {
        "response": r,
        "marker_position": marker_position,
        "intensity_rating": intensity_rating,
        "wait_time": wait_time,
        "response_jitter": response_jitter,
        "trial_start_time": trial_start_datetime,
        "trial_end_time": trial_end_datetime,
        "trial_duration": trial_duration,
        "orgasm_reports": orgasm_reports,
    }
