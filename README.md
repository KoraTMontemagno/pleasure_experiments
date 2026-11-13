# Pleasure vibration pipeline

The wrapper runs three stages:

1. **Annoyance threshold:** an adaptive Psi staircase where right-arrow means the
   vibration felt annoying or painful.
2. **Pleasure threshold:** an adaptive Psi staircase capped at the annoyance
   estimate minus the configured safety margin. Left means not pleasurable,
   right means pleasurable, and down means painful/annoying.
3. **Validation:** the minimum, pleasure threshold, and maximum are each
   presented twice in an interleaved six-trial cycle. Each level must receive
   two non-painful/non-annoying responses. If any level is painful/annoying,
   the range is adjusted and the entire six-trial cycle restarts. Every
   validation response is logged.
4. **Fixed pleasure trials:** the validated minimum, threshold, and maximum
   are used as the three final intensity levels. `final_trials_per_intensity`
   sets the number of trials at each level (30 means 90 total); the schedule
   is shuffled with no adjacent repeats. `final_break_interval` controls how
   often break screens appear across the full trial sequence (10 means after
   every 10 trials; 0 disables scheduled breaks).

Painful/annoying responses in the pleasure-threshold stage are recorded as
`1000`, excluded from `Psi.addData`, and followed by a lower intensity. The Psi
posterior is unchanged for an excluded response; its selected stimulus index is
retargeted so the next valid answer updates the posterior for the intensity
actually delivered.

Thresholding trials ask only for the binary response and do not show the VAS.
Validation trials ask only for the binary response. After validation, three
habituation trials at the validated threshold are administered before the final
trials; those habituation trials and the final trials each include a separate
0-100 VAS screen after the binary choice. Participants use LEFT/RIGHT to move
the cursor along the visible scale line and UP to confirm. The scale has no
middle tick, and the binary choices disappear during the VAS. One second after
confirming the VAS (or the binary response in thresholding/validation), the
fixation cross returns. VAS values are logged as `intensity_rating` for the
post-validation habituation and final trials.

The annoyance threshold stage includes configured habituation; the pleasure
threshold stage has no habituation. If four maximum-intensity trials in the
annoyance stage are pain-free, threshold testing ends early and the pleasure
stage ceiling is set to the configured device maximum (1.0 by default).

During participant-facing screens, the corner controls are available:

- Press **O** to record an orgasm. The experiment displays a fixation message
  and pauses until the participant presses **S**, then resumes the remaining
  stimuli. Orgasm events are written to
  `experiment/sub-<participant>_participant_events.csv` and counted in trial
  logs.
- Press **E** to quit. Completed trials and participant events remain saved.
- During pleasure trials, use LEFT/RIGHT only to report whether the sensation
  was pleasurable. There is no separate pain/annoyance response; press **E**
  to stop if you feel pain or discomfort.

After reading the pain-threshold instructions and before the first vibration,
participants practise E (stop), LEFT/RIGHT (pleasure response), and O/S (pause
and resume) without stimulation. These practice screens show the pleasure
question, No/Yes choices, and the on-screen stop reminder. When the VAS is
introduced before the pleasure-threshold trials, participants practise rating a
very strong, not pleasurable vibration above a very faint, pleasurable one.
The practice explains that VAS measures vibration intensity, not pleasure.

The pleasure response is binary (LEFT/RIGHT). A participant who feels pain or
discomfort can stop with E; the experiment does not ask them to use a separate
pain/annoyance response key.

## Setup and run

Install dependencies into the Python environment used for the experiment:

```bash
python -m pip install -r requirements.txt
```

Start Intiface for a real device run, then launch:

```bash
python wrapper.py
```

Enter the participant ID, choose a stage, and follow the on-screen prompts.
You can run the complete pipeline with option `1`, or run a stage independently:

1. Choose option `2` to estimate the annoyance threshold. This saves the
   annoyance estimate and configured intensity limits.
2. Choose option `3` to estimate the pleasure threshold. It loads the saved
   annoyance threshold, calculates a proposed safe ceiling, and lets the
   experimenter accept or manually enter a ceiling in the terminal.
3. Choose option `4` to validate minimum, threshold, and maximum, then run the
   final fixed-intensity trials. It loads both saved thresholds and runs the
   pseudorandomized trials at the three validated levels.

Run stages 2 and 3 first if you choose option 4 directly. Each threshold stage
updates `sub-<participant>_pleasure_pipeline_summary.json`, so the next stage
can resume from the saved results. The wrapper checks for existing participant
data before proceeding.

During the complete pipeline, one PsychoPy window remains open through the
threshold stages, reviews, and final trials. During experimenter reviews the
participant sees only a break message; threshold and intensity details are
shown in the terminal, not on the participant display. In the terminal, press
ENTER to continue or Q to stop. After the pleasure threshold estimate, press M
in the terminal to enter a manual threshold if needed. During ceiling review,
press M to set the ceiling manually; it must remain within the configured device
intensity range. The summary JSON records the estimated and selected ceiling
and whether it was overridden. The annoyance estimate is used to calculate the
proposed ceiling, but is not separately presented for experimenter review.

Set `pleasure_pipeline.automatic_mode` to `true` to skip experimenter input at
ceiling, threshold, validation, final-intensity, and between-block reviews.
Automatic mode keeps the wrapper's stage and participant-ID prompts; it does
not remove participant response/ready screens. It raises a calculated ceiling
below 0.5 to 0.5, capped at the configured device maximum. This deliberately
overrides the calculated annoyance-based ceiling. If no symmetric range can be
selected around the pleasure threshold, it tries the fixed 0.2/0.3/0.4 levels.
The fallback is rejected if any level is outside the configured device
minimum/maximum; otherwise it may also exceed the calculated annoyance-based
ceiling. If either override cannot fit the device range, the stage stops with
an error instead of delivering out-of-range intensities. Automatic mode is
disabled by default.

To run the PsychoPy displays and collect responses without sending device
commands, use:

```bash
python wrapper.py --simulate-device
```

Simulation still requires PsychoPy and its display dependencies; it only skips
the Buttplug/Intiface device output.

To simulate a synthetic participant headlessly (without PsychoPy, a display,
or a connected device), run:

```bash
python simulate_agent.py --seed 123
```

By default, the simulated participant has a pain threshold of `0.65` with
Gaussian response spread `0.2`, and a pleasure threshold of `0.35` with spread
`0.3`. The spread is the psychometric curve's sigma, not the Psi posterior's
threshold uncertainty. The simulation runs 30 trials for each adaptive
threshold, feeds painful/annoying pleasure-stage responses through the same
excluded-update/lower-intensity behavior, and simulates interleaved validation
and final-trial safety stops. Override assumptions with `--pain-threshold`,
`--pain-spread`, `--pleasure-threshold`, `--pleasure-spread`,
`--annoyance-trials`, `--pleasure-trials`, and `--seed`. It prints the fitted
thresholds, selected ceiling, validation cycles, and final-trial outcome; it
does not write participant data files.

To run 50 indicative cases spanning the full `[0, 1]` range, use:

```bash
python sweep_agents.py --seed 123
```

This tests the 16 corners of the four-dimensional parameter space plus 34
stratified samples, varying pain threshold, pain-response spread, pleasure
threshold, and pleasure-response spread. It writes one summary row per
simulation to `synthetic_agent_sweep.csv`. Change the case count with
`--cases N` (at least 16 to retain all corners). `--grid-step STEP` instead
runs a full factorial grid, such as `--grid-step 0.5` for 81 cases.
`--replicates N` repeats cases with distinct deterministic seeds. Adaptive
trial counts and output path can be set with `--annoyance-trials`,
`--pleasure-trials`, and `--output`. Zero response spread is modeled as a step
function, with a 50% response probability exactly at the threshold. This sweep
is entirely synthetic and does not launch PsychoPy or contact the device.

## Visualize recorded data

From this directory, generate participant-wise plots of arousal ratings,
reported vibration intensity (VAS), and binary annoyance/pain responses:

```bash
python visualize_data.py
```

The PNG files are saved in `data/visualizations/`. Each participant has a
separate panel, with elapsed session time on the horizontal axis. To use
another input or output directory, pass `--data-dir` or `--output-dir`.

In `parameters.json`, set `pleasure_pipeline.final_trials_per_intensity` and
`pleasure_pipeline.final_break_interval` to configure the final experiment.
For example, the defaults of 30 and 10 produce 90 total final trials, split
evenly across the three intensities, with breaks after trials 10, 20, and so
on (but not after the last trial).

The wrapper sets Matplotlib to its non-GUI `Agg` backend because the experiment
saves plots instead of opening plot windows. It also removes
`GSETTINGS_SCHEMA_DIR` from the process environment before importing the
experiment GUI libraries. If GTK still aborts on a missing GNOME schema key,
run these checks from the same activated environment and send their output to
the experiment maintainer:

```bash
gsettings list-keys org.gnome.settings-daemon.plugins.xsettings | grep -x antialiasing
printf 'GSETTINGS_SCHEMA_DIR=%s\nGTK_PATH=%s\nGTK_DATA_PREFIX=%s\n' \
  "$GSETTINGS_SCHEMA_DIR" "$GTK_PATH" "$GTK_DATA_PREFIX"
python -c 'import sys, psychopy, matplotlib; print("Python:", sys.executable); print("PsychoPy:", psychopy.__version__); print("Matplotlib backend:", matplotlib.get_backend())'
```

An empty first command result means the system schema does not define the
requested key. Simulation does not bypass PsychoPy/GTK startup, so it will not
fix a GTK schema error by itself.

Check packages without starting the task:

```bash
python wrapper.py --check-dependencies
python wrapper.py --simulate-device --check-dependencies
```

## Configure

Edit `parameters.json`. Top-level timing settings (seconds, all required
except `ISI_jitter`):

- `duration`: vibration duration of every stimulus.
- `jitter_wait` / `jitter_response`: fixation before / after the vibration,
  each drawn per trial as the value ± 0.5 s.
- `min_ISI` and `ISI_jitter`: every trial lasts at least `min_ISI` ±
  `ISI_jitter` (drawn per trial, uniform); if the participant answers sooner,
  the fixation cross stays on until then. The planned minimum
  (`min_trial_duration`) and the actual `trial_duration` are saved in every
  trial file and shown in the experimenter log.
- `habituation`: familiarisation trials before the annoyance threshold.

The `pleasure_pipeline` settings are:

- `annoyance_ntrials` and `pleasure_ntrials` (required): adaptive trials per
  threshold stage.
- `practice`: run the key and rating-scale practice (`true` / `false`).
- `arousal_every_n_trials`: excitement VAS (and the reposition screen) at the
  start, every n trials and at the end of the thresholds and final trials;
  `0` turns it off.
- `minimum_intensity` / `maximum_intensity`: allowed device intensity range.
- `validation_adjustment_step`: amount to change the validation intensities
  after a painful/annoying response, and the minimum threshold-to-maximum
  distance used for the initial symmetric validation range (default: `0.1`).
- `automatic_mode`: when `true`, automatically accepts experimenter reviews,
  raises the selected pleasure ceiling to at least 0.5 when the device maximum
  permits, and uses the 0.2/0.3/0.4 fallback if no symmetric range fits. It
  defaults to `false`.
- `language`: question and response-interface language, either `"en"` or
  `"it"` (default: `"en"`).
- `safety_margin_sd`: standard deviations to subtract from the annoyance
  threshold to set the pleasure-stage ceiling (default: 1).
- `final_trials_per_intensity`: number of final trials at each of the three
  validated intensities (default: 10). For example, `30` schedules 90 trials
  total, with 30 at each intensity.
- `final_break_interval`: show a participant break screen after each interval
  of final trials (default: 10). Set it to `0` to disable scheduled breaks.

The estimated annoyance threshold controls initial validation levels. Below
`0.2`, the participant is excluded before the pleasure stage. From `0.2` to
below `0.4`, validation starts at `0.1 / 0.2 / 0.3`. From `0.4` through `0.5`,
the maximum is `0.5`; above `0.5`, the maximum is the selected pleasure ceiling.
In the latter two cases, the pleasure threshold is used as the center when
possible, with symmetric minimum/threshold/maximum spacing of at least
`validation_adjustment_step`, while respecting the configured device minimum.

Validation trials do not include the VAS. Pain at the minimum or threshold
lowers all three levels by one adjustment step. The maximum is lowered only
when both maximum presentations in a six-trial cycle are painful. After
lowering it, if the threshold-to-maximum gap would be smaller than the
adjustment step, the threshold is lowered to restore that minimum gap and the
minimum is moved to preserve the spacing. A single painful maximum response
without pain at another level repeats the same six-trial validation cycle.
Every adjusted range is retested from the beginning, with a maximum of two
six-trial validation runs. Validation passes normally if a run has no painful
responses. If the last run does not pass (or no safe adjustment is possible),
the participant may still proceed when at least one pleasure response was
reported at the threshold or maximum in that last run. In that case, the
intensities from that last run are retained and recorded as accepted based on
pleasure, not as a strict validation pass. Otherwise, the stage stops. If an
adjustment would fall below the configured device minimum, no out-of-range
validation stimulus is delivered.

After validation and experimenter review, the participant receives three
habituation trials at the validated threshold intensity, each followed by a
VAS rating. These responses are logged separately before the randomized final
trials begin. A painful/annoying response during this habituation block stops
the run before the final trials. The VAS cursor is moved with LEFT/RIGHT and
confirmed with UP.

## Output

Participant data are organized under `data/sub-<participant>/`:

- `pain/`: annoyance/pain threshold CSVs, threshold summaries, and threshold
  plots.
- `pleasure/`: pleasure-threshold CSVs, threshold summaries, plots, and the
  pipeline summary JSON.
- `validation/`: validation trial CSV and one stacked Yes/No/Painful response
  barplot per six-trial validation run.
- `experiment/`: post-validation habituation and final experiment trial CSVs,
  a Yes/No/Painful response barplot, and a VAS-intensity boxplot grouped by
  vibration intensity, plus the participant event log when O/E is used.

Each break screen invites the participant to take a break and waits for them
to press ENTER before proceeding. In non-automatic mode, any experimenter
review or override still follows the participant's ENTER press.
