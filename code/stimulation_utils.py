import numpy as np
from psychopy import core
from . import PsiMarginal
import matplotlib.pyplot as plt
from scipy.stats import norm
from .psychopy_fun import core, event, monitors, visual, psycho_stuff
from psychopy.hardware import keyboard
import pandas as pd
import json
import time
from datetime import datetime
import os
import csv
import asyncio
from .repeat_vibration import go_vibrate

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

    wait_time = 0.0
    response_jitter = 0.0


    # Check for escape before starting the trial.
    if "escape" in event.getKeys():
        raise KeyboardInterrupt("Experiment aborted by user.")

    # Fixation
    win.mouseVisible = False
    fixation.draw()
    win.flip()

    print("Stimulate with intensity: ", np.round(vibr,3), "\n")

    # Pre-stimulation jitter
    wait_time = float(np.random.uniform(jitter_wait - 0.5, jitter_wait + 0.5))
    core.wait(max(0, wait_time))
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
    core.wait(max(0, response_jitter))
    print("Post-stimulation jitter: ", np.round(response_jitter, 3))

    # Collect response using the original PsychoPy rating scale.
    quality_pleasure.reset()
    confirmed = False

    while not confirmed:
        quality_pleasure.draw()
        no_label.color = "white"
        yes_label.color = "white"
        yes_label.draw()
        no_label.draw()
        quality_question_pleasure.draw()
        win.flip()

        keys = event.getKeys(
            keyList=["left", "right", "up", "escape"]
        )

        for key in keys:
            if key == "escape":
                raise KeyboardInterrupt(
                    "Experiment aborted during response."
                )

            if key == "left":
                quality_pleasure.markerPos = 1
                no_label.color = "teal"
                no_label.draw()
                yes_label.draw()
                quality_question_pleasure.draw()
                win.flip()
                core.wait(1)
                confirmed = True
                break

            elif key == "right":
                quality_pleasure.markerPos = 2
                yes_label.color = "teal"
                no_label.draw()
                yes_label.draw()
                quality_question_pleasure.draw()
                win.flip()
                core.wait(1)
                confirmed = True
                break

    # Preserve the response coding from the original code.
    if quality_pleasure.markerPos == 2:
        r = 1 
        response_print = "Yes",
    else:
        r = 0 
        response_print = "No"

    print(f"Response: {r}, marker: {quality_pleasure.markerPos}, meaning {response_print}")

    trial_end_perf = time.perf_counter()
    trial_end_datetime = datetime.now().isoformat(
        timespec="milliseconds"
    )
    trial_duration = trial_end_perf - trial_start_perf

    # Preserve the minimum trial duration.
    if trial_duration <= 15:
        core.wait(max(0, 15 - trial_duration))
        trial_end_perf = time.perf_counter()
        trial_end_datetime = datetime.now().isoformat(
            timespec="milliseconds"
        )
        trial_duration = trial_end_perf - trial_start_perf

    return {
        "response": r,
        "marker_position": quality_pleasure.markerPos,
        "wait_time": wait_time,
        "response_jitter": response_jitter,
        "trial_start_time": trial_start_datetime,
        "trial_end_time": trial_end_datetime,
        "trial_duration": trial_duration,
    }
