import numpy as np
from . import PsiMarginal
import matplotlib.pyplot as plt
from scipy.stats import norm
from psychopy import core, event, monitors, visual  
from .psychopy_fun import psycho_stuff
from psychopy.hardware import keyboard
import pandas as pd
from .repeat_vibration import scan_for_devices, vibrate_device, go_vibrate
import asyncio
import pandas as pd
import os
from .stimulation_utils import update_habituation_vibration, run_trial

def run_threshold(
        subject: str = "pilot",
        pattern: str = "pleasure", # or pain
        ntrials: int = 30,
        habituation: int = 5,
        stim_duration: float = 2.5,
        jitter_wait: float = 2,
        jitter_response: float = 2,
        simulate_device: bool = False,
):

    """Run habituation trials followed by adaptive Psi thresholding."""

    if pattern not in ("pleasure", "pain"):
        raise ValueError("pattern must be 'pleasure' or 'pain'")

    if ntrials < 1 or habituation < 0:
        raise ValueError("ntrials must be >= 1 and habituation >= 0")

    output_dir = f"data_threshold/sub-{subject}"
    os.makedirs(output_dir, exist_ok=True)

    ### VIBRATION PARAMETERS ###
    min_vibr = 0.1
    max_vibr = 1

    ### INTIFACE SETUP ###
    #client = asyncio.run(scan_for_devices())
    # Make sure we actually found one
    #if not client.devices:
    #    raise RuntimeError("No devices found! Make sure your vibrator is on and Intiface is running.")
    #device = list(client.devices.values())[0]

    ### PSIMARGINAL SETUP ###
    mu = np.linspace(min_vibr, max_vibr, 50) # limits of the mu
    sigma = np.linspace(0.001, 1, 100) # limits of slope
    x = np.arange(min_vibr, max_vibr, 0.05)  # stimulus values in 1/20 percentage increases
    lapse = np.linspace(0, 0.1, 15)
    guessRate = 0.05

    # set priors (flat priors or from experiments - look at the code)
    thresholdPrior = ('uniform', None)
    slopePrior = ('uniform', None)
    lapsePrior = ('uniform', None)

    psi = PsiMarginal.Psi(
        x, Pfunction='cGauss', nTrials=ntrials,
        threshold=mu, thresholdPrior=thresholdPrior,
        slope=sigma, slopePrior=slopePrior,
        guessRate=guessRate, guessPrior=('uniform', None),
        lapseRate=lapse, lapsePrior=lapsePrior,
        marginalize=True
    )

    print(
        f"\nRunning {pattern}: {ntrials} adaptive trials, "
        f"{habituation} habituation trials."
    )


    try:
        #### PSYCHOPY ####
        # define the window fixation and rating scale:
        win, fixation, quality, quality_question, no_label, yes_label, ready_text = psycho_stuff()

        ready_text.draw()
        win.flip()

        # Wait for SPACE or ENTER
        while True:
            keys = event.waitKeys(keyList=['space', 'return', 'escape'])
            if 'escape' in keys:
                print("Experiment aborted at ready screen.")
                core.quit()
            elif 'space' in keys or 'return' in keys:
                break

        # -----------------------------------------------------
        # HABITUATION: no Psi updates and no threshold records
        # -----------------------------------------------------
        print("\n--- Starting habituation ---")

        vibr = 0.2 #assign a value for fallback

        for h in range(habituation):
            print(
                f"\n--- Habituation trial {h + 1} "
                f"of {habituation} ---"
            )

            trial = run_trial(
                vibr=vibr,
                win=win,
                fixation=fixation,
                quality_pleasure=quality,
                quality_question_pleasure=quality_question,
                no_label=no_label,
                yes_label=yes_label,
                stim_duration=stim_duration,
                jitter_wait=jitter_wait,
                jitter_response=jitter_response,
                simulate_device=simulate_device,
            )

            r = trial["response"]
            vibr = update_habituation_vibration(vibr, r)

            print(f"Next habituation intensity: {np.round(vibr, 3)} ")

        print("\n--- Habituation completed ---")


        ### RUN ADAPTIVE THRESHOLD LOOP ###¨
        trials = []
        vibrs = []
        thresholds = []
        threshold_uncertainty = []  # std or credible interval width

        #initialize results
        results = pd.DataFrame(columns=[
            "participant", "pattern", "trial",
            "vibration","stim_duration",
            "ramp_speed", "return_speed",
            "wait_time", "response_jitter",
            "response", "marker_position",
            "estimated_threshold", "threshold_std",
            "threshold_low_2sd", "threshold_high_2sd",
            "estimated_slope", "estimated_lapse",
            "trial_start_time", "trial_end_time",
            "trial_duration",
        ])

        results_filename = (
            f"{output_dir}/sub-{subject}_{pattern}_"
            "trial_data_detailed.csv"
        )

        for i in range(ntrials):

            vibr = psi.xCurrent # calculate vibration intensity to deliver (I let the algorithm decide the first vibration)
                
            ### Experimenter View ###
            print(f"\n--- Trial {i + 1} of {ntrials} ---")

            # append everything when needed
            trials.append(i + 1)
            vibrs.append(vibr) # append the vibration intensity

            trial = run_trial(
                vibr=vibr,
                win=win,
                fixation=fixation,
                quality_pleasure=quality,
                quality_question_pleasure=quality_question,
                no_label=no_label,
                yes_label=yes_label,
                stim_duration=stim_duration,
                jitter_wait=jitter_wait,
                jitter_response=jitter_response,
                simulate_device=simulate_device,
            )

            # Update Psi model
            r = trial["response"]
            if r == 1000:

                print("Pain reported!")

                # Do not incorporate this trial into Psi
                # Select a lower intensity for a possible later trial
                psi.forceStimulus(vibr - 0.1)

            else:

                psi.addData(r)

            est_threshold = psi.eThreshold
            thresholds.append(est_threshold)
            threshold_uncertainty.append(psi.stdThreshold)
            threshold_low = [a_i - 2*b_i for a_i, b_i in zip(thresholds, threshold_uncertainty)]
            threshold_high = [a_i + 2*b_i for a_i, b_i in zip(thresholds, threshold_uncertainty)]

            ### Save trials

            #small version for readability
            df_trials = pd.DataFrame({
                'Trial': trials,
                'Delivered_Temp': vibrs,
                'Estimated_Threshold': thresholds,
                'Response': psi.response 
            })

            df_trials.to_csv(f"{output_dir}/sub-{subject}_trial_data_{pattern}.csv", index=False)


            results.loc[len(results)] = {
                "participant": subject,
                "pattern": pattern,
                "trial": i + 1,
                "vibration": vibr,
                "stim_duration": stim_duration,
                "wait_time": trial["wait_time"],
                "response_jitter": trial["response_jitter"],
                "response": r,
                "marker_position": trial["marker_position"],
                "estimated_threshold": est_threshold,
                "threshold_std": threshold_uncertainty,
                "threshold_low_2sd": threshold_low,
                "threshold_high_2sd": threshold_high,
                "estimated_slope": psi.eSlope,
                "estimated_lapse": psi.eLapse,
                "trial_start_time": trial["trial_start_time"],
                "trial_end_time": trial["trial_end_time"],
                "trial_duration": trial["trial_duration"],
            }

            # Save every adaptive trial.
            results.to_csv(results_filename, index=False)

            #final summary
            with open(f"{output_dir}/sub-{subject}_thresholds.txt", "w") as f:
                f.write(f"Estimated Threshold: {psi.eThreshold:.2f}\n")
                f.write(f"STD Threshold: {psi.stdThreshold:.2f}\n")
                f.write(f"Estimated Slope: {psi.eSlope:.3f}\n")
                f.write(f"Estimated Lapse Rate: {psi.eLapse:.3f}\n")
                f.write(f"Total Trials: {ntrials}\n")

            # Wait for next trial value
            while psi.xCurrent is None:
                pass

    except KeyboardInterrupt as exc:
        print(f"\n{exc}")

    win.close()

    ### REPORT RESULTS ###
    print("\n--- Final Estimated Parameters ---")
    print(f"μ (threshold): {psi.eThreshold:.2f}")
    print(f"standard deviation of threshold: {psi.stdThreshold:.2f}")
    print(f"σ (slope): {psi.eSlope:.2f}")
    print(f"Lapse rate: {psi.eLapse:.2f}")

    ### Plot the psychometric function ###
    x_vals = np.linspace(min(x), max(x), 500)
    p_yes = (1 - psi.eLapse) * norm.cdf(x_vals, loc=psi.eThreshold, scale=psi.eSlope) + psi.guessRate * psi.eLapse

    plt.figure(figsize=(6, 4))
    plt.plot(x_vals, p_yes, label='Psychometric Function')
    plt.axvline(psi.eThreshold, color='r', linestyle='--', label=f'Threshold ≈ {psi.eThreshold:.2f}°C')
    plt.xlabel('Intensity')
    plt.ylabel('P("Yes")')
    plt.title('Estimated Psychometric Function')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/sub-{subject}__psychometric_function_{pattern}.png", dpi=300)
    plt.close()

    ### Plot the trial and thresholds
    fig, axs = plt.subplots(1, 1, figsize=(8, 4))
    axs.plot(trials, vibrs, '.', label='Intensity Delivered')
    axs.plot(trials, thresholds, '-.', label='Estimated Threshold', color="darkred")
    axs.fill_between(trials, threshold_low, threshold_high, color='pink', alpha=0.3, label='2SD')
    axs.set_xlabel('Trial')
    axs.set_ylabel('Intensity')
    axs.set_title('Intensity and Threshold Estimate Over Trials')
    axs.legend()
    axs.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/sub-{subject}_threshold_evolution_{pattern}.png", dpi=300)
    plt.close()
