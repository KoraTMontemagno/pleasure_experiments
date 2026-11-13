import numpy as np
from psychopy import core
from . import PsiMarginal
import matplotlib.pyplot as plt
from scipy.stats import norm
from .psychopy_fun import (
    RESPONSE_LABEL_X,
    VAS_MARKER_COLOR,
    core,
    event,
    monitors,
    psycho_stuff,
    visual,
)
from psychopy.hardware import keyboard
import pandas as pd
import json
import time
from datetime import datetime
import os
import csv
import asyncio
import time
from .repeat_vibration import go_vibrate


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

def run_trial(
    vibr,
    win,
    fixation,
    quality_pleasure,
    quality_question_pleasure,
    no_label,
    yes_label,
    stim_duration,
    jitter_wait,
    jitter_response,
    simulate_device=False,
    response_mode="pleasure",
    pain_label=None,
    intensity_question=None,
    intensity_scale=None,
    intensity_instruction=None,
    collect_intensity_rating=False,
    subject="unknown",
    participant_phase="",
    trial_number="",
    language="en",
):
    """
    Deliver one stimulus and collect one response.
    Returns the response, marker position, timing information,
    and vibration-recording information.
    """

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

    print("Stimulate with intensity: ", np.round(vibr,3), "\n")

    # Pre-stimulation jitter
    wait_time = float(np.random.uniform(jitter_wait - 0.5, jitter_wait + 0.5))
    _wait_with_participant_controls(max(0, wait_time), controls, fixation)
    print("Pre-stimulation jitter: ", np.round(wait_time, 3))

    # Deliver the stimulus
    asyncio.run(
        go_vibrate(
            duration=stim_duration,
            intensity=vibr,
            simulate_device=simulate_device,
        )
    )

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
    print("Post-stimulation jitter: ", np.round(response_jitter, 3))

    # Collect response using the original PsychoPy rating scale.
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
            confirmed = True
            break
    intensity_rating = None
    if collect_intensity_rating:
        if intensity_scale is None or intensity_question is None:
            raise ValueError("An intensity VAS scale and question are required.")

        intensity_scale.reset()
        intensity_scale.setRating(0)
        intensity_scale.markerColor = VAS_MARKER_COLOR
        intensity_scale.markerFillColor = VAS_MARKER_COLOR
        intensity_rating_value = 0
        rating_confirmed = False

        while not rating_confirmed:
            intensity_question.draw()
            intensity_scale.draw()
            if intensity_instruction is not None:
                intensity_instruction.draw()
            controls.draw()
            win.flip()
            keys = event.getKeys(
                keyList=["left", "right", "up", "escape", "o", "e"]
            )
            controls.process_keys(keys, fixation=fixation)
            if "left" in keys:
                intensity_rating_value = max(intensity_rating_value - 1, 0)
                intensity_scale.setRating(intensity_rating_value)
            elif "right" in keys:
                intensity_rating_value = min(intensity_rating_value + 1, 100)
                intensity_scale.setRating(intensity_rating_value)
            elif "up" in keys:
                intensity_rating = float(intensity_rating_value)
                intensity_scale.markerColor = "lightcoral"
                intensity_scale.markerFillColor = "lightcoral"
                intensity_question.draw()
                intensity_scale.draw()
                controls.draw()
                win.flip()
                _wait_with_participant_controls(1, controls, fixation)
                rating_confirmed = True
    else:
        core.wait(1)

    fixation.draw()
    win.flip()

    if marker_position == 3:
        r = 1000
        response_print = "Painful/annoying"
    elif marker_position == 2:
        r = 1 
        response_print = "Yes"
    else:
        r = 0 
        response_print = "No"

    print(f"Response: {r}, marker: {marker_position}, meaning {response_print}")

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

    return {
        "response": r,
        "marker_position": marker_position,
        "intensity_rating": intensity_rating,
        "wait_time": wait_time,
        "response_jitter": response_jitter,
        "trial_start_time": trial_start_datetime,
        "trial_end_time": trial_end_datetime,
        "trial_duration": trial_duration,
        "orgasm_reports": controls.consume_orgasm_reports(),
    }
