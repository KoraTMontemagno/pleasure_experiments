import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


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

    # Keep data_threshold and the configuration path stable when launched elsewhere.
    os.chdir(EXPERIMENT_DIR)

    from pleasure_experiments.code.thresholding import run_threshold
    from pleasure_experiments.code_main.utils import check_thresholds_files

    choice = input(
        "\nWelcome! Select what to run:\n"
        "- 1: pleasure threshold\n"
    ).strip().lower()
    if choice != "1":
        print("Invalid choice.")
        return

    subject = input(
        "\nWonderful! Now input subject number "
        "(take a sec to check in order not to overwrite existing data :)) : \n"
    ).strip()
    if not subject:
        raise SystemExit("A subject number is required.")

    if not check_thresholds_files(subject, directories=["data_threshold"]):
        raise SystemExit("Experiment cancelled.")

    print("\n================================")
    print("       PLEASURE THRESHOLD")
    print("================================\n")

    run_threshold(
        subject=subject,
        pattern="pleasure",
        ntrials=config["ntrials"],
        habituation=config["habituation"],
        stim_duration=config["duration"],
        jitter_wait=config["jitter_wait"],
        jitter_response=config["jitter_response"],
        simulate_device=simulate_device,
    )

    print("\n================================")
    print("   PLEASURE THRESHOLD COMPLETED")
    print("================================\n")


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
