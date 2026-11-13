import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


# The experiment only saves plots; avoid GTK-backed Matplotlib GUI startup.
os.environ["MPLBACKEND"] = "Agg"
os.environ.pop("GSETTINGS_SCHEMA_DIR", None)

EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXPERIMENT_DIR.parent
CONFIG_PATH = EXPERIMENT_DIR / "parameters.json"
REQUIRED_PACKAGES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "scikit-learn": "sklearn",
    "psychopy": "psychopy",
    "buttplug": "buttplug",
}


def missing_dependencies(simulate_device=False):
    return [
        package
        for package, import_name in REQUIRED_PACKAGES.items()
        if not (simulate_device and package == "buttplug")
        if importlib.util.find_spec(import_name) is None
    ]


def check_dependencies(simulate_device=False):
    missing = missing_dependencies(simulate_device=simulate_device)
    if not missing:
        print("All required Python packages are available.")
        return True

    print("Missing experiment dependencies: " + ", ".join(missing))
    print(
        "\nInstall them into the Python environment used to run this script with:"
        f"\n  python -m pip install -r {EXPERIMENT_DIR / 'requirements.txt'}"
    )
    return False


def load_config(path):
    try:
        with path.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise SystemExit(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Invalid JSON in {path} (line {exc.lineno}, column {exc.colno}): "
            f"{exc.msg}"
        ) from exc

    required_settings = (
        "duration",
        "jitter_response",
        "jitter_wait",
        "min_ISI",
        "habituation",
    )
    required_pipeline = ("annoyance_ntrials", "pleasure_ntrials")
    missing_settings = [
        setting for setting in required_settings if setting not in config
    ] + [
        f"pleasure_pipeline.{setting}" for setting in required_pipeline
        if setting not in config.get("pleasure_pipeline", {})
    ]
    if missing_settings:
        raise SystemExit(
            "Missing settings in parameters.json: " + ", ".join(missing_settings)
        )
    return config


def run_experiment(config, simulate_device=False):
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))

    # Keep participant data and the configuration path stable when launched elsewhere.
    os.chdir(EXPERIMENT_DIR)

    from pleasure_experiments.code.pleasure_pipeline import (
        run_annoyance_stage,
        run_final_pleasure_stage,
        run_pleasure_pipeline,
        run_pleasure_threshold_stage,
    )
    from pleasure_experiments.code.pleasure_outputs import check_thresholds_files

    choice = input(
        "\nWelcome! Select what to run:\n"
        "- 1: full pleasure pipeline\n"
        "- 2: annoyance threshold only\n"
        "- 3: pleasure threshold only (requires a saved annoyance threshold)\n"
        "- 4: final 3-level trials only (requires saved annoyance and pleasure thresholds)\n"
    ).strip().lower()
    if choice not in {"1", "2", "3", "4"}:
        print("Invalid choice.")
        return

    subject = input(
        "\nWonderful! Now input subject number "
        "(take a sec to check in order not to overwrite existing data :)) : \n"
    ).strip()
    if not subject:
        raise SystemExit("A subject number is required.")

    if not check_thresholds_files(
        subject,
        directories=["data"],
    ):
        raise SystemExit("Experiment cancelled.")

    pipeline = config.get("pleasure_pipeline", {})
    # every trial lasts at least min_ISI ± ISI_jitter seconds (per trial)
    min_isi = float(config["min_ISI"])
    isi_jitter = float(config.get("ISI_jitter", 0))
    if not 0 <= isi_jitter <= min_isi:
        raise SystemExit("ISI_jitter must be between 0 and min_ISI.")
    minimum_intensity = pipeline.get("minimum_intensity", 0.1)
    maximum_intensity = pipeline.get("maximum_intensity", 1.0)
    intensity_step = pipeline.get("intensity_step", 0.05)
    validation_adjustment_step = pipeline.get(
        "validation_adjustment_step", 0.1
    )
    automatic_mode = pipeline.get("automatic_mode", False)
    if not isinstance(automatic_mode, bool):
        raise SystemExit("pleasure_pipeline.automatic_mode must be true or false.")
    arousal_every = pipeline.get("arousal_every_n_trials", 0)
    if not isinstance(arousal_every, int) or isinstance(arousal_every, bool) or arousal_every < 0:
        raise SystemExit("pleasure_pipeline.arousal_every_n_trials must be a "
                         "whole number >= 0 (0 = off).")
    practice = pipeline.get("practice", True)
    if not isinstance(practice, bool):
        raise SystemExit("pleasure_pipeline.practice must be true or false.")
    language = pipeline.get("language", "en")
    if language not in {"en", "it"}:
        raise SystemExit(
            "pleasure_pipeline.language must be either 'en' or 'it'."
        )
    safety_margin_sd = pipeline.get("safety_margin_sd", 1.0)
    final_trials_per_intensity = pipeline.get("final_trials_per_intensity", 10)
    final_n_trials = final_trials_per_intensity * 3
    final_break_interval = pipeline.get("final_break_interval", 10)
    seed = sum(ord(character) for character in subject)

    from pleasure_experiments.code import repeat_vibration

    if not simulate_device:
        # Connect to Intiface and find the device once, before the participant
        # starts; every stimulus of the session reuses this connection.
        try:
            repeat_vibration.connect()
        except Exception as exc:  # noqa: BLE001 - shown to the experimenter
            raise SystemExit(f"Could not connect to the vibrator: {exc}") from exc

    try:
        if choice == "1":
            result = run_pleasure_pipeline(
                subject=subject,
                annoyance_ntrials=pipeline["annoyance_ntrials"],
                pleasure_ntrials=pipeline["pleasure_ntrials"],
                habituation=config["habituation"],
                stim_duration=config["duration"],
                jitter_wait=config["jitter_wait"],
                jitter_response=config["jitter_response"],
                min_isi=min_isi,
                isi_jitter=isi_jitter,
                minimum_intensity=minimum_intensity,
                maximum_intensity=maximum_intensity,
                intensity_step=intensity_step,
                safety_margin_sd=safety_margin_sd,
                final_trials_per_intensity=final_trials_per_intensity,
                final_break_interval=final_break_interval,
                simulate_device=simulate_device,
                seed=seed,
                validation_adjustment_step=validation_adjustment_step,
                language=language,
                automatic_mode=automatic_mode,
                practice=practice,
                arousal_every=arousal_every,
            )
            if result is None:
                print("\nPleasure pipeline stopped or cancelled.")
            elif len(result["final_trials"]) < final_n_trials:
                print("\nFinal pleasure trials stopped early; partial data were saved.")
            else:
                print("\nPleasure pipeline completed.")
        elif choice == "2":
            result = run_annoyance_stage(
                subject=subject,
                ntrials=pipeline["annoyance_ntrials"],
                habituation=config["habituation"],
                stim_duration=config["duration"],
                jitter_wait=config["jitter_wait"],
                jitter_response=config["jitter_response"],
                min_isi=min_isi,
                isi_jitter=isi_jitter,
                minimum_intensity=minimum_intensity,
                maximum_intensity=maximum_intensity,
                simulate_device=simulate_device,
                language=language,
                automatic_mode=automatic_mode,
                practice=practice,
                arousal_every=arousal_every,
            )
            print("\nAnnoyance stage completed." if result else "\nAnnoyance stage was cancelled.")
        elif choice == "3":
            result = run_pleasure_threshold_stage(
                subject=subject,
                ntrials=pipeline["pleasure_ntrials"],
                stim_duration=config["duration"],
                jitter_wait=config["jitter_wait"],
                jitter_response=config["jitter_response"],
                min_isi=min_isi,
                isi_jitter=isi_jitter,
                safety_margin_sd=safety_margin_sd,
                simulate_device=simulate_device,
                language=language,
                automatic_mode=automatic_mode,
                practice=practice,
                arousal_every=arousal_every,
            )
            print("\nPleasure-threshold stage completed." if result else "\nPleasure-threshold stage was cancelled.")
        else:
            result = run_final_pleasure_stage(
                subject=subject,
                intensity_step=intensity_step,
                final_trials_per_intensity=final_trials_per_intensity,
                final_break_interval=final_break_interval,
                stim_duration=config["duration"],
                jitter_wait=config["jitter_wait"],
                jitter_response=config["jitter_response"],
                min_isi=min_isi,
                isi_jitter=isi_jitter,
                simulate_device=simulate_device,
                seed=seed,
                validation_adjustment_step=validation_adjustment_step,
                language=language,
                automatic_mode=automatic_mode,
                practice=practice,
                arousal_every=arousal_every,
            )
            if result is None:
                print("\nFinal trial stage was cancelled.")
            elif len(result) < final_n_trials:
                print("\nFinal trials stopped early; partial data were saved.")
            else:
                print("\nFinal trial stage completed.")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise SystemExit(f"Could not start selected stage: {exc}") from exc
    finally:
        repeat_vibration.disconnect()
        # the experimenter monitor's plots, saved in the experiment folder
        try:
            from pleasure_experiments.code.qc_plots import save_overview

            print(f"Overview plot saved: {save_overview(subject)}")
        except Exception as exc:  # noqa: BLE001 - never block the end of a run
            print(f"Could not save the overview plot: {exc!r}")


def main():
    parser = argparse.ArgumentParser(description="Run the pleasure threshold experiment.")
    parser.add_argument(
        "--check-dependencies",
        action="store_true",
        help="check required packages without starting the experiment",
    )
    parser.add_argument(
        "--simulate-device",
        action="store_true",
        help="skip vibrator output while keeping PsychoPy and response prompts active",
    )
    args = parser.parse_args()

    if args.check_dependencies:
        if not check_dependencies(simulate_device=args.simulate_device):
            raise SystemExit(1)
        return

    if not check_dependencies(simulate_device=args.simulate_device):
        raise SystemExit(1)

    run_experiment(
        load_config(CONFIG_PATH),
        simulate_device=args.simulate_device,
    )


if __name__ == "__main__":
    main()
