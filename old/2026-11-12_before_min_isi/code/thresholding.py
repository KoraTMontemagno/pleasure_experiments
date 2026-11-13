import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from psychopy import event
from scipy.stats import norm

from . import PsiMarginal
from .display import as_display
from .pleasure_outputs import log_trial, participant_output_dir
from .psychopy_fun import (
    participant_text,
    psycho_stuff,
    run_participant_practice,
    show_break_review,
)
from .stimulation_utils import (
    check_arousal,
    run_trial,
    update_habituation_vibration,
)


def run_threshold(
        subject: str = "pilot",
        pattern: str = "pleasure",
        ntrials: int = 30,
        habituation: int = 5,
        stim_duration: float = 2.5,
        jitter_wait: float = 2,
        jitter_response: float = 2,
        simulate_device: bool = False,
        min_vibr: float = 0.1,
        max_vibr: float = 1.0,
        display=None,
        review_threshold: bool = False,
        language: str = "en",
        automatic_mode: bool = False,
        practice: bool = True,
        arousal_every: int = 0,
):

    """Run habituation trials followed by adaptive Psi thresholding.

    practice=False skips the response-key practice after the ready screen.
    """

    if pattern not in ("pleasure", "annoyance"):
        raise ValueError("pattern must be 'pleasure' or 'annoyance'")

    if ntrials < 1 or habituation < 0:
        raise ValueError("ntrials must be >= 1 and habituation >= 0")

    if not 0 < min_vibr < max_vibr <= 1:
        raise ValueError("vibration limits must satisfy 0 < min_vibr < max_vibr <= 1")

    output_category = "pain" if pattern == "annoyance" else "pleasure"
    output_dir = participant_output_dir(subject, output_category)
    output_dir.mkdir(parents=True, exist_ok=True)

    ### PSIMARGINAL SETUP ###
    x = np.arange(min_vibr, max_vibr, 0.05)
    if x.size == 0 or x[-1] < max_vibr:
        x = np.append(x, max_vibr)
    mu = np.linspace(min_vibr, max_vibr, 50)
    sigma = np.linspace(0.001, max_vibr - min_vibr, 100)
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
        marginalize=True,
        thread=False,
    )

    print(
        f"\nRunning {pattern}: {ntrials} adaptive trials, "
        f"{habituation} habituation trials."
    )
    owns_window = display is None
    win = None
    selected_threshold = None
    try:
        #### PSYCHOPY ####
        # define the window fixation and rating scale:
        if language not in {"en", "it"}:
            raise ValueError("language must be 'en' or 'it'.")
        question_text = participant_text(f"{pattern}_question", language)
        instruction_text = participant_text(
            f"{pattern}_threshold_ready",
            language,
        )
        if display is None:
            display = psycho_stuff(
                question_text=question_text,
                instruction_text=instruction_text,
                language=language,
            )
        display = as_display(display)
        win = display.win
        fixation = display.fixation
        quality_question = display.quality_question
        no_label = display.no_label
        yes_label = display.yes_label
        ready_text = display.ready_text
        quality_question.text = question_text
        ready_text.text = instruction_text
        if pattern == "annoyance":
            no_label.text = f"←\n{participant_text('no', language)}"
            yes_label.text = f"→\n{participant_text('yes', language)}"

        from .participant_controls import get_participant_controls

        controls = get_participant_controls(win, subject, language)
        controls.set_context(f"{pattern} threshold", "ready")
        # Wait for SPACE or ENTER
        while True:
            ready_text.draw()
            controls.draw()
            win.flip()
            keys = event.waitKeys(
                keyList=["space", "return", "escape", "o", "e"]
            )
            controls.process_keys(keys, fixation=fixation)
            if "escape" in keys:
                raise KeyboardInterrupt("Experiment aborted at ready screen.")
            elif 'space' in keys or 'return' in keys:
                break

        if practice:
            run_participant_practice(
                display, subject, language=language, mode=pattern
            )

        # -----------------------------------------------------
        # HABITUATION: no Psi updates and no threshold records
        # -----------------------------------------------------
        vibr = 0.2 #assign a value for fallback

        for h in range(habituation):
            trial = run_trial(
                vibr=vibr,
                display=display,
                stim_duration=stim_duration,
                jitter_wait=jitter_wait,
                jitter_response=jitter_response,
                simulate_device=simulate_device,
                response_mode="annoyance" if pattern == "annoyance" else "pleasure",
                collect_intensity_rating=False,
                subject=subject,
                participant_phase=f"{pattern} habituation",
                trial_number=f"habituation-{h + 1}",
                language=language,
            )

            r = trial["response"]
            log_trial("Familiarisation", h + 1, habituation, vibr, r)
            if r == 1000:
                vibr = max(min_vibr, vibr - 0.1)
            else:
                vibr = update_habituation_vibration(vibr, r)




        ### RUN ADAPTIVE THRESHOLD LOOP ###¨
        trials = []
        vibrs = []
        thresholds = []
        responses = []
        intensity_ratings = []
        orgasm_reports = []
        threshold_uncertainty = []  # std or credible interval width
        safety_stop = False
        pain_free_maximum_trials = 0
        pain_free_maximum_stop = False

        #initialize results
        results = pd.DataFrame(columns=[
            "participant", "pattern", "trial",
            "vibration","stim_duration",
            "ramp_speed", "return_speed",
            "wait_time", "response_jitter",
            "response", "marker_position",
            "intensity_rating",
            "orgasm_reports",
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
            # excitement VAS + reposition screen at start and every n trials
            check_arousal(display, subject, language, f"{pattern} threshold",
                          i, ntrials, arousal_every)

            vibr = psi.xCurrent # calculate vibration intensity to deliver (I let the algorithm decide the first vibration)
                
            ### Experimenter View ###

            # append everything when needed
            trials.append(i + 1)
            vibrs.append(vibr) # append the vibration intensity

            trial = run_trial(
                vibr=vibr,
                display=display,
                stim_duration=stim_duration,
                jitter_wait=jitter_wait,
                jitter_response=jitter_response,
                simulate_device=simulate_device,
                response_mode="annoyance" if pattern == "annoyance" else "pleasure",
                collect_intensity_rating=False,
                subject=subject,
                participant_phase=f"{pattern} threshold",
                trial_number=i + 1,
                language=language,
            )

            # Update Psi model
            r = trial["response"]
            if pattern == "annoyance" and np.isclose(
                float(vibr), max_vibr, rtol=0.0, atol=0.05
            ):
                if r == 0:
                    pain_free_maximum_trials += 1
                else:
                    pain_free_maximum_trials = 0
                if pain_free_maximum_trials >= 4:
                    pain_free_maximum_stop = True
                    print(
                        "Four pain-free trials at maximum intensity reached; "
                        "stopping threshold testing and opening the pleasure "
                        "stage ceiling to the configured maximum."
                    )
            responses.append(r)
            intensity_ratings.append(trial["intensity_rating"])
            orgasm_reports.append(trial.get("orgasm_reports", 0))
            stop_for_safety = False
            if pattern == "annoyance" and r == 1 and float(vibr) <= min_vibr + 1e-9:
                print(
                    "Annoyance was reported at minimum intensity; "
                    "stopping because no safe test range is established."
                )
                safety_stop = True
                psi.addData(r)
                stop_for_safety = True
            elif pattern == "pleasure" and r == 1000:

                print("  (painful: not used for the threshold estimate)")

                next_intensity = max(min_vibr, float(vibr) - 0.1)
                if next_intensity >= float(vibr):
                    print(
                        "Pain or annoyance was reported at minimum intensity; "
                        "stopping to avoid repeating an unsafe stimulus."
                    )
                    stop_for_safety = True
                    safety_stop = True
                else:
                    psi.skipData(next_intensity)

            else:
                psi.addData(r)

            est_threshold = float(getattr(psi, "eThreshold", np.nan))
            threshold_std = float(getattr(psi, "stdThreshold", np.nan))
            log_trial(f"{pattern.capitalize()} threshold", i + 1, ntrials, vibr,
                      r, note=f"estimate {est_threshold:.3f} ± {threshold_std:.3f}")
            thresholds.append(est_threshold)
            threshold_uncertainty.append(threshold_std)
            threshold_low = [
                threshold - 2 * uncertainty
                for threshold, uncertainty in zip(thresholds, threshold_uncertainty)
            ]
            threshold_high = [
                threshold + 2 * uncertainty
                for threshold, uncertainty in zip(thresholds, threshold_uncertainty)
            ]

            ### Save trials

            #small version for readability
            df_trials = pd.DataFrame({
                'Trial': trials,
                'Delivered_Temp': vibrs,
                'Estimated_Threshold': thresholds,
                'Response': responses,
                'Intensity_Rating': intensity_ratings,
                'Orgasm_Reports': orgasm_reports,
            })

            df_trials.to_csv(
                f"{output_dir}/sub-{subject}_trial_data_{pattern}.csv",
                index=False,
            )


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
                "intensity_rating": trial["intensity_rating"],
                "orgasm_reports": trial.get("orgasm_reports", 0),
                "estimated_threshold": est_threshold,
                "threshold_std": threshold_std,
                "threshold_low_2sd": threshold_low[-1],
                "threshold_high_2sd": threshold_high[-1],
                "estimated_slope": getattr(psi, "eSlope", np.nan),
                "estimated_lapse": getattr(psi, "eLapse", np.nan),
                "trial_start_time": trial["trial_start_time"],
                "trial_end_time": trial["trial_end_time"],
                "trial_duration": trial["trial_duration"],
            }

            # Save every adaptive trial.
            results.to_csv(results_filename, index=False)

            if psi.response:
                with open(
                    f"{output_dir}/sub-{subject}_{pattern}_thresholds.txt",
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(f"Estimated Threshold: {psi.eThreshold:.2f}\n")
                    f.write(f"STD Threshold: {psi.stdThreshold:.2f}\n")
                    f.write(f"Estimated Slope: {psi.eSlope:.3f}\n")
                    f.write(f"Estimated Lapse Rate: {psi.eLapse:.3f}\n")
                    f.write(f"Total Trials: {len(trials)}\n")

            if stop_for_safety:
                break
            if pain_free_maximum_stop:
                break

        if not safety_stop:
            check_arousal(display, subject, language, f"{pattern} threshold",
                          ntrials, ntrials, arousal_every)

        if psi.response and not safety_stop and review_threshold:
            fitted_threshold = float(psi.eThreshold)
            accepted, selected_threshold = show_break_review(
                win,
                title=f"{pattern.capitalize()} threshold review",
                message=(
                    f"Estimated threshold: {fitted_threshold:.3f}\n"
                    f"Estimated SD: {float(psi.stdThreshold):.3f}\n\n"
                    "The manual value, if entered, replaces the threshold "
                    "estimate. The fitted SD is retained."
                ),
                threshold=fitted_threshold,
                minimum=min_vibr,
                maximum=max_vibr,
                language=language,
                automatic_mode=automatic_mode,
                subject=subject,
                phase=f"{pattern} threshold review",
            )
            if not accepted:
                return None

    except KeyboardInterrupt as exc:
        print(f"\n{exc}")
        return None
    finally:
        if owns_window and win is not None:
            win.close()

    if not psi.response:
        raise RuntimeError(
            f"No valid {pattern} responses were recorded; no threshold can be estimated."
        )
    if safety_stop:
        raise RuntimeError(
            "Pain or annoyance was reported at the minimum pleasure intensity; "
            "the pleasure pipeline cannot safely continue."
        )

    ### REPORT RESULTS ###
    print(f"{pattern.capitalize()} threshold: {psi.eThreshold:.3f} "
          f"(SD {psi.stdThreshold:.3f}, slope {psi.eSlope:.2f}, "
          f"lapse {psi.eLapse:.2f})")
    fitted_threshold = float(psi.eThreshold)
    if selected_threshold is None:
        selected_threshold = fitted_threshold
    with open(
        f"{output_dir}/sub-{subject}_{pattern}_thresholds.txt",
        "w",
        encoding="utf-8",
    ) as f:
        f.write(f"Estimated Threshold: {fitted_threshold:.2f}\n")
        f.write(f"Selected Threshold: {selected_threshold:.2f}\n")
        f.write(
            "Manually Overridden: "
            f"{not np.isclose(selected_threshold, fitted_threshold)}\n"
        )
        f.write(f"STD Threshold: {psi.stdThreshold:.2f}\n")
        f.write(f"Estimated Slope: {psi.eSlope:.3f}\n")
        f.write(f"Estimated Lapse Rate: {psi.eLapse:.3f}\n")
        f.write(f"Total Trials: {len(trials)}\n")

    plot_label = "Pain/annoyance" if pattern == "annoyance" else "Pleasure"

    ### Plot the psychometric function ###
    x_vals = np.linspace(min(x), max(x), 500)
    p_yes = (
        (1 - psi.eLapse)
        * norm.cdf(x_vals, loc=psi.eThreshold, scale=max(psi.eSlope, 1e-9))
        + psi.guessRate * psi.eLapse
    )

    plt.figure(figsize=(6, 4))
    plt.plot(x_vals, p_yes, label='Psychometric Function')
    plt.axvline(
        psi.eThreshold,
        color='r',
        linestyle='--',
        label=f"Threshold ≈ {psi.eThreshold:.2f}",
    )
    plt.xlabel('Intensity')
    plt.ylabel('P("Yes")')
    plt.title(f'{plot_label} Threshold: Estimated Psychometric Function')
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
    axs.set_title(f'{plot_label} Threshold: Intensity and Estimate Over Trials')
    axs.legend()
    axs.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/sub-{subject}_threshold_evolution_{pattern}.png", dpi=300)
    plt.close()

    return {
        "threshold": float(selected_threshold),
        "estimated_threshold": fitted_threshold,
        "manually_overridden": not np.isclose(selected_threshold, fitted_threshold),
        "std": float(psi.stdThreshold),
        "slope": float(psi.eSlope),
        "lapse": float(psi.eLapse),
        "stimulus_min": float(min_vibr),
        "stimulus_max": float(max_vibr),
        "pain_free_maximum_stop": pain_free_maximum_stop,
        "pain_free_maximum_trials": pain_free_maximum_trials,
    }
