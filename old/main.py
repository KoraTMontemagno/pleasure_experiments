import numpy as np
import pleasure_experiments.old.PsiMarginal as PsiMarginal
import matplotlib.pyplot as plt
from scipy.stats import norm
from psychopy import core, event, monitors, visual  
from pleasure_experiments.old.psychopy_fun import psycho_stuff
from psychopy.hardware import keyboard
import pandas as pd
from pleasure_experiments.old.repeat_vibration import scan_for_devices, vibrate_device, go_vibrate
import asyncio
import pandas as pd

subject_df = pd.read_csv("subject_data.csv", sep=";")
subject = subject_df["participant_id"].iloc[0]
stim_duration = float(subject_df["duration"].iloc[0])
jitter_response = float(subject_df["jitter_response"].iloc[0])
jitter_wait = float(subject_df["jitter_wait"].iloc[0])

### USER SETTINGS ###
ntrials = 30
jitter = True
show_temp = True
interactive_plot = False

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

#### PSYCHOPY ####
# define the window fixation and rating scale:
win, fixation, quality, quality_question, no_label, yes_label = psycho_stuff()

ready_text = visual.TextStim(
    win,
    text="You will receive some vibration stimuli. After each stimulus you will be asked whether it was pleasurable or not - use your left and right arrow on the keyboard to answer.\n Are you ready?\n\nPress SPACE or ENTER to start.",
    color='white',
    height=60,
    wrapWidth=1000,
    font= "Times New roman"
)

ready_text.draw()
win.flip()

# Wait for SPACE or ENTER
while True:
    keys = event.waitKeys(keyList=['space', 'return', 'escape'])
    if 'escape' in keys:
        print("Experiment aborted at ready screen.")
        win.close()
        core.quit()
    elif 'space' in keys or 'return' in keys:
        break


### RUN ADAPTIVE THRESHOLD LOOP ###¨
trials = []
vibrs = []
thresholds = []
threshold_uncertainty = []  # std or credible interval width
if interactive_plot is True:
    plt.ion()  # interactive mode on
    fig, axs = plt.subplots(1, 1, figsize=(10, 8))

for i in range(ntrials):

    ### Experimenter View ###
    vibr = psi.xCurrent # calculate vibration intensity to deliver
    print(f"\nTrial {i + 1} of {ntrials}")
    if show_temp == True:
        print(f" Delivering: {psi.xCurrent} vibration")
    # take care of visualization
    trials.append(i + 1)
    vibrs.append(vibr) # append the vibration intensity

    ### Participant View ###
    # Set an escape condition
    keys = event.getKeys()
    if 'escape' in keys:
        print("Experiment aborted by user.")
        break
    # Prepare window and show fixation cross
    win.mouseVisible = False
    fixation.draw()
    win.flip()

    # Wait before stimulation
    if jitter is True:
        core.wait(np.random.uniform(jitter_wait - 0.5, jitter_wait + 0.5))


    # Stimulate with the vibrator
    # Stimulate with the vibrator
    print("Now we vibrate!")
    #loop = asyncio.get_event_loop()
    #loop.run_until_complete(vibrate_device(device, intensity=vibr, duration=stim_duration))
    asyncio.run(go_vibrate(duration = stim_duration, intensity = vibr))
    
    if jitter == True:
        response_jitter = np.random.uniform(jitter_response - 0.5,jitter_response + 0.5)
        core.wait(response_jitter)

    # Get response
    # Project psychopy
    quality.reset()
    quality.markerPos = None
    confirmed = False
    while not confirmed:
        quality.draw()
        no_label.color = "white"
        yes_label.color = "white"
        yes_label.draw()
        no_label.draw()
        quality_question.draw()
        win.flip()
        # get possible keys
        keys = event.getKeys(keyList=['left', 'right', 'up', 'escape'])
        for key in keys:
            if key == 'left':
                quality.markerPos = 0  # when key is left go to position 1 (no)
                quality_question.draw()
                no_label.color = "teal"
                no_label.draw()
                yes_label.draw()
                win.flip()
                core.wait(1)
                confirmed = True
                r = 0
                break
            elif key == 'right':
                quality.markerPos = 1 # when key is right go to position 2 (yes)
                quality_question.draw()
                yes_label.color = "teal"
                no_label.draw()
                yes_label.draw()
                win.flip()
                core.wait(1)
                confirmed = True
                r = 1
                break
            elif key == 'escape':
                print("Experiment aborted during quality pleasure.")
                win.close()
                core.quit()
                confirmed = True

    print("Response: ", r)
    # Update Psi model
    psi.addData(r)
    est_threshold = psi.eThreshold
    thresholds.append(est_threshold)
    threshold_uncertainty.append(psi.stdThreshold)
    threshold_low = [a_i - 2*b_i for a_i, b_i in zip(thresholds, threshold_uncertainty)]
    threshold_high = [a_i + 2*b_i for a_i, b_i in zip(thresholds, threshold_uncertainty)]

    ### Save trials

    df_trials = pd.DataFrame({
        'Trial': trials,
        'Delivered_Temp': vibrs,
        'Estimated_Threshold': thresholds,
        'Response': psi.response  # assuming this holds the binary response history
    })

    df_trials.to_csv(f"data/{subject}_trial_data.csv", index=False)

    with open(f"data/{subject}_thresholds.txt", "w") as f:
        f.write(f"Estimated Threshold: {psi.eThreshold:.2f}\n")
        f.write(f"STD Threshold: {psi.stdThreshold:.2f}\n")
        f.write(f"Estimated Slope: {psi.eSlope:.3f}\n")
        f.write(f"Estimated Lapse Rate: {psi.eLapse:.3f}\n")
        f.write(f"Total Trials: {ntrials}\n")

    # Wait for next trial value
    while psi.xCurrent is None:
        pass

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
plt.savefig(f"data/{subject}__psychometric_function.png", dpi=300)
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
plt.savefig(f"data/{subject}__threshold_evolution.png", dpi=300)
plt.close()


