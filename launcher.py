"""Point-and-click launcher for the pleasure experiment (experimenter screen).

Run:  python launcher.py        (or double-click start_experiment.bat)

Modelled on pain_experiment/launcher.py. The experimenter picks participant,
language and options in a dialog, then the stage to run (only stages whose
earlier results are saved are offered, the next one preselected). The
launcher runs wrapper.py's experiment unchanged and answers its terminal
prompts with dialog boxes:

    - "data already exist" -> Yes/No dialog
    - experimenter review after a stage (threshold / safe ceiling /
      validation) -> dialog with the estimate: continue, stop, or type a
      manual value

Every run writes a full log to data/sub-<ID>/logs/. The live QC monitor
(qc_monitor.py) opens in its own window when the participant window opens.
Simulation mode runs without the vibrator and saves data as sub-sim<ID>.
"""
import builtins
import collections
import copy
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE.parent))

from psychopy import gui, visual  # noqa: E402
from psychopy.gui import qtgui  # noqa: E402

from pleasure_experiments import wrapper  # noqa: E402
from pleasure_experiments.code import experiment_progress as progress  # noqa: E402


class OnTopDlg(gui.Dlg):
    """PsychoPy dialog that stays on top (participant window, QC monitor)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        flags = getattr(qtgui.Qt, "WindowType", qtgui.Qt)  # PyQt6 / PyQt5
        self.setWindowFlags(self.windowFlags() | flags.WindowStaysOnTopHint)


gui.Dlg = OnTopDlg

LANGUAGES = ["it", "en"]

# Lines not shown in dialogs (still in the terminal and the log file):
# per-trial lines and file-saving notices.
NOISE = ("Familiarisation", "Annoyance threshold ", "Pleasure threshold ",
         "Validation ", "Habituation ", "Final experiment ",
         "Pipeline progress saved", "Final pleasure-trial log", "Saving",
         "All required Python packages")


class RecentOutput:
    """Copy of stdout: keeps the last lines for the dialogs, writes the log."""

    def __init__(self, stream, n_lines=25):
        self.stream = stream
        self.lines = collections.deque(maxlen=n_lines)
        self._partial = ""
        self.log = None

    def start_log(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(path, "a", encoding="utf-8")
        self.lines.clear()

    def stop_log(self):
        if self.log:
            self.log.close()
            self.log = None

    def write(self, text):
        self.stream.write(text)
        if self.log:
            self.log.write(text)
            self.log.flush()
        self._partial += text
        *done, self._partial = self._partial.split("\n")
        self.lines.extend(line for line in done
                          if line.strip()
                          and not line.strip().startswith(NOISE))

    def flush(self):
        self.stream.flush()

    def recent(self, n=6):
        return "\n".join(list(self.lines)[-n:])


recent_output = RecentOutput(sys.stdout)


def _values(dlg, data):
    """Dlg.show() returns a list in older PsychoPy versions, a dict in newer."""
    return list(data.values()) if isinstance(data, dict) else list(data)


def message(title, text):
    dlg = gui.Dlg(title=title)
    dlg.addText(text)
    dlg.show()


def ask_yes_no(question, context=""):
    dlg = gui.Dlg(title="Please confirm")
    if context:
        dlg.addText(context)
        dlg.addText("")
    dlg.addText(question)
    dlg.show()
    return "y" if dlg.OK else "n"


def ask_review(review):
    """Experimenter review after a stage -> '' (continue), 'q' or 'm'."""
    options = ["Continue", "Stop the experiment"]
    if review["manual_label"]:
        options.insert(1, f"Enter a manual {review['manual_label']}")
    dlg = gui.Dlg(title=f"Experimenter review - {review['title']}")
    dlg.addText(review["message"])
    dlg.addField("Decision", choices=options, initial=options[0])
    data = dlg.show()
    if not dlg.OK:
        return "q"
    choice = _values(dlg, data)[0]
    if choice.startswith("Enter a manual"):
        return "m"
    return "" if choice == "Continue" else "q"


def ask_manual_value(prompt):
    """'Enter threshold (0.100–0.600), or press ENTER to keep...' -> text."""
    label = prompt.strip().split(", or press ENTER")[0]
    dlg = gui.Dlg(title="Manual value")
    dlg.addText(recent_output.recent(4))  # e.g. "must be between ..." retries
    dlg.addField(f"{label} (empty = keep the estimate)", initial="")
    data = dlg.show()
    return str(_values(dlg, data)[0]).strip() if dlg.OK else ""


def ask_text(prompt):
    dlg = gui.Dlg(title="Please enter")
    dlg.addField(prompt.strip().rstrip(":").strip(), initial="")
    data = dlg.show()
    if not dlg.OK:
        raise SystemExit("Cancelled.")
    return str(_values(dlg, data)[0])


def make_input(subject, step_code):
    """Replacement for input(): known prompts are answered from the dialogs."""

    def gui_input(prompt=""):
        print(prompt, end="")
        lower = prompt.lower()
        review = progress.parse_review(prompt)
        if "select what to run" in lower:
            answer = step_code
        elif "subject number" in lower:
            answer = subject
        elif review:
            answer = ask_review(review)
        elif "or press enter to keep the estimate" in lower:
            answer = ask_manual_value(prompt)
        elif "data already exists" in lower:
            answer = ask_yes_no(
                "Data already exist for this participant.\n"
                "Continue? (stages you run again are overwritten)",
                context=recent_output.recent(3),
            )
        elif "y/n" in lower:
            answer = ask_yes_no(prompt.strip(), context=recent_output.recent())
        else:
            answer = ask_text(prompt)
        print(answer)
        return answer

    return gui_input


def read_parameters():
    return wrapper.load_config(wrapper.CONFIG_PATH)


def existing_participants():
    if not progress.DATA_ROOT.is_dir():
        return []
    return sorted(path.name[4:] for path in progress.DATA_ROOT.glob("sub-*")
                  if path.is_dir())


def choose_participant(choice):
    """Dialog 1: participant and options. False if closed (quit)."""
    known = [s for s in existing_participants() if not s.startswith("sim")]
    dlg = gui.Dlg(title="Pleasure experiment")
    if known:
        dlg.addText("Participants with data: " + ", ".join(known))
    dlg.addField("Participant ID", initial=choice["participant"])
    dlg.addField("Language", choices=LANGUAGES, initial=choice["language"])
    dlg.addField("Practice (key and rating-scale practice)",
                 initial=choice["practice"])
    dlg.addField("Excitement VAS + reposition every n trials (0 = off)",
                 initial=str(choice["arousal"]))
    dlg.addField("Automatic mode (skip experimenter reviews)",
                 initial=choice["automatic"])
    dlg.addField("Simulation (no vibrator, debugging only)",
                 initial=choice["sim"])
    dlg.addField("Live experimenter monitor (vibrator, trials, timing)",
                 initial=choice["qc"])
    data = dlg.show()
    if not dlg.OK:
        return False
    participant, language, practice, arousal, automatic, sim, qc = _values(dlg, data)
    participant = str(participant).strip()
    try:
        arousal = int(str(arousal).strip() or 0)
        if arousal < 0:
            raise ValueError
    except ValueError:
        message("Excitement VAS", "Enter a whole number of trials (0 = off).")
        return choose_participant(choice)
    if not participant or any(c in participant for c in r' \/:*?"<>|'):
        message("Participant ID", "Enter a participant ID without spaces "
                "or special characters.")
        return choose_participant(choice)
    choice.update(participant=participant, language=language,
                  practice=bool(practice), arousal=arousal,
                  automatic=bool(automatic),
                  sim=bool(sim), qc=bool(qc))
    return True


def data_id(choice):
    return f"sim{choice['participant']}" if choice["sim"] else choice["participant"]


def choose_step(choice, config, last):
    """Dialog 2: stages that can run now, the next one preselected."""
    per_level = config["pleasure_pipeline"].get("final_trials_per_intensity", 10)
    state = progress.progress(data_id(choice), per_level)
    steps = progress.available_steps(state)
    header = (f"Participant {choice['participant']}   language {choice['language']}"
              f"   practice {'on' if choice['practice'] else 'off'}"
              f"   excitement VAS {'every ' + str(choice['arousal']) if choice['arousal'] else 'off'}"
              f"   automatic {'on' if choice['automatic'] else 'off'}")
    if choice["sim"]:
        header += "   SIMULATION (data saved as sub-" + data_id(choice) + ")"
    dlg = gui.Dlg(title="Pleasure experiment")
    if last:
        dlg.addText(last)
    dlg.addText(header)
    dlg.addText(progress.progress_text(state))
    dlg.addField("Stage", choices=steps, initial=progress.next_step(state))
    data = dlg.show()
    return _values(dlg, data)[0] if dlg.OK else None


REAL_WINDOW = visual.Window


def start_qc_with_window(monitor, subject):
    """Open the QC monitor (once) just before the participant window opens."""

    class WindowStartingQC(REAL_WINDOW):
        def __init__(self, *args, **kwargs):
            process = monitor["process"]
            if process is None or process.poll() is not None:
                env = dict(os.environ)
                env.pop("MPLBACKEND", None)  # wrapper sets Agg; the monitor needs a window
                monitor["process"] = subprocess.Popen(
                    [sys.executable, str(HERE / "qc_monitor.py"), subject],
                    cwd=HERE, env=env,
                )
                monitor["subject"] = subject
            super().__init__(*args, **kwargs)

    visual.Window = WindowStartingQC


def stop_monitor(monitor):
    for key in ("process",):
        process = monitor.get(key)
        if process is not None and process.poll() is None:
            process.terminate()
        monitor[key] = None


def run_record(config):
    """Code version and the parameters actually used, for the log."""
    try:
        commit = subprocess.run(
            ["git", "log", "-1", "--format=%h %ad %s", "--date=short"],
            cwd=HERE, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = ""
    return (f"Code version: {commit or 'unknown (no git)'}\n"
            f"Parameters: {json.dumps(config)}")


def main():
    base_config = read_parameters()
    pipeline = base_config.get("pleasure_pipeline", {})
    choice = {
        "participant": "",
        "language": pipeline.get("language", "it"),
        "practice": pipeline.get("practice", True),
        "arousal": pipeline.get("arousal_every_n_trials", 0),
        "automatic": pipeline.get("automatic_mode", False),
        "sim": False,
        "qc": True,
    }
    monitor = {"process": None, "subject": None}
    real_input = builtins.input
    real_stdout = sys.stdout
    sys.stdout = recent_output

    last = ""
    pick_participant = True
    try:
        while True:
            if pick_participant:
                if not choose_participant(choice):
                    break
                last = ""
            config = copy.deepcopy(read_parameters())  # re-read: may be edited
            config.setdefault("pleasure_pipeline", {}).update(
                language=choice["language"],
                practice=choice["practice"],
                arousal_every_n_trials=choice["arousal"],
                automatic_mode=choice["automatic"],
            )
            step = choose_step(choice, config, last)
            pick_participant = step is None  # Cancel: back to dialog 1
            if step is None:
                continue

            if not wrapper.check_dependencies(simulate_device=choice["sim"]):
                message("Missing packages", "Some Python packages are missing "
                        "(see the terminal). Install them, or use Simulation.")
                continue

            subject = data_id(choice)
            log_file = (progress.subject_dir(subject) / "logs"
                        / f"{datetime.now():%Y%m%d_%H%M%S}_step{progress.STEPS[step]}.txt")
            recent_output.start_log(log_file)
            if monitor["process"] is not None and (
                not choice["qc"] or monitor["subject"] != subject
            ):
                stop_monitor(monitor)
            if choice["qc"]:
                start_qc_with_window(monitor, subject)
            print(f"Participant {subject}\nStage: {step}")
            print(run_record(config))
            if choice["sim"]:
                print(f"*** SIMULATION: no vibrator. Data saved as sub-{subject}. ***")
            builtins.input = make_input(subject, progress.STEPS[step])
            outcome, error = "finished", ""
            try:
                wrapper.run_experiment(config, simulate_device=choice["sim"])
            except (SystemExit, KeyboardInterrupt) as exc:
                code = getattr(exc, "code", None)
                outcome = "stopped"
                error = code if isinstance(code, str) else ""
                print(f"Stage stopped. {error}")
            except Exception as exc:  # noqa: BLE001 - shown to the experimenter
                outcome, error = "error", repr(exc)
                print(f"ERROR: {error}")
            finally:
                builtins.input = real_input
                visual.Window = REAL_WINDOW
                recent_output.stop_log()
                os.chdir(HERE)

            if outcome == "error":
                message("Error", f"The stage stopped with an error:\n{error}"
                        f"\n\nFull log: {log_file}")
                last = ""
            elif outcome == "stopped":
                last = f"{step} stopped. {error}".strip()
            else:
                last = f"{step}: done."
    finally:
        sys.stdout = real_stdout
        stop_monitor(monitor)


if __name__ == "__main__":
    main()
