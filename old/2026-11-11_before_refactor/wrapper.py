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
        "ntrials",
        "habituation",
    )
    missing_settings = [
        setting for setting in required_settings if setting not in config
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
    from pleasure_experiments.code_main.utils import check_thresholds_files

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
        directories=["data", "data_threshold"],
    ):
        raise SystemExit("Experiment cancelled.")

    pipeline = config.get("pleasure_pipeline", {})
    minimum_intensity = pipeline.get("minimum_intensity", 0.1)
    maximum_intensity = pipeline.get("maximum_intensity", 1.0)
    intensity_step = pipeline.get("intensity_step", 0.05)
    validation_adjustment_step = pipeline.get(
        "validation_adjustment_step", 0.1
    )
    automatic_mode = pipeline.get("automatic_mode", False)
    if not isinstance(automatic_mode, bool):
        raise SystemExit("pleasure_pipeline.automatic_mode must be true or false.")
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

    try:
        if choice == "1":
            result = run_pleasure_pipeline(
                subject=subject,
                annoyance_ntrials=pipeline.get("annoyance_ntrials", config["ntrials"]),
                pleasure_ntrials=pipeline.get("pleasure_ntrials", config["ntrials"]),
                habituation=config["habituation"],
                stim_duration=config["duration"],
                jitter_wait=config["jitter_wait"],
                jitter_response=config["jitter_response"],
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
                ntrials=pipeline.get("annoyance_ntrials", config["ntrials"]),
                habituation=config["habituation"],
                stim_duration=config["duration"],
                jitter_wait=config["jitter_wait"],
                jitter_response=config["jitter_response"],
                minimum_intensity=minimum_intensity,
                maximum_intensity=maximum_intensity,
                simulate_device=simulate_device,
                language=language,
                automatic_mode=automatic_mode,
                practice=practice,
            )
            print("\nAnnoyance stage completed." if result else "\nAnnoyance stage was cancelled.")
        elif choice == "3":
            result = run_pleasure_threshold_stage(
                subject=subject,
                ntrials=pipeline.get("pleasure_ntrials", config["ntrials"]),
                stim_duration=config["duration"],
                jitter_wait=config["jitter_wait"],
                jitter_response=config["jitter_response"],
                safety_margin_sd=safety_margin_sd,
                simulate_device=simulate_device,
                language=language,
                automatic_mode=automatic_mode,
                practice=practice,
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
                simulate_device=simulate_device,
                seed=seed,
                validation_adjustment_step=validation_adjustment_step,
                language=language,
                automatic_mode=automatic_mode,
                practice=practice,
            )
            if result is None:
                print("\nFinal trial stage was cancelled.")
            elif len(result) < final_n_trials:
                print("\nFinal trials stopped early; partial data were saved.")
            else:
                print("\nFinal trial stage completed.")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise SystemExit(f"Could not start selected stage: {exc}") from exc


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
