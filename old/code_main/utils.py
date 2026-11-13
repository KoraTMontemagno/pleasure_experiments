#from .psychopy_fun import core, event, monitors, visual
import glob
import os
import pandas as pd

def check_thresholds_files(subject, directories):
    """
    Check whether a subject-specific folder already exists and
    list all files inside it.

    Parameters
    ----------
    subject : str
        Subject number, e.g. "01"

    directories : list
        Parent directories to search, e.g.
        ["data", "subject_temperatures"]

    Returns
    -------
    bool
        True if the experiment should proceed.
        False if the user chooses to cancel.
    """

    subject_folder = f"sub-{subject}"

    existing_files = {}

    for directory in directories:

        subject_path = os.path.join(directory, subject_folder)

        if not os.path.exists(subject_path):
            continue

        files_in_folder = []

        for root, dirs, files in os.walk(subject_path):

            for filename in files:
                filepath = os.path.join(root, filename)
                files_in_folder.append(filepath)

        if files_in_folder:
            existing_files[directory] = sorted(files_in_folder)

    # --------------------------------------------------
    # No files found
    # --------------------------------------------------

    if not existing_files:

        print(
            f"\nNo existing files found for participant "
            f"{subject_folder}."
        )

        return True

    # --------------------------------------------------
    # Print existing files
    # --------------------------------------------------

    print("\n" + "=" * 70)
    print(f"WARNING: EXISTING DATA FOUND FOR {subject_folder}")
    print("=" * 70)

    for directory, files in existing_files.items():

        print(f"\n{directory}/{subject_folder}/")

        for filepath in files:
            relative_path = os.path.relpath(filepath, directory)
            print(f"    {relative_path}")

    print("\n" + "=" * 70)

    # --------------------------------------------------
    # Ask whether to proceed
    # --------------------------------------------------

    while True:

        answer = input(
            "\nData already exists for this participant.\n"
            "Do you want to proceed? [y/n]: "
        ).strip().lower()

        if answer in ("y", "yes"):

            print("\nProceeding...\n")
            return True

        elif answer in ("n", "no"):

            print("\nExperiment cancelled.")
            return False

        else:

            print("Please enter 'y' or 'n'.")

def check_participant_info(participant_id, baseline, temp_data, csv_cold, csv_warm, stimuli_type, show_params = True):
    if participant_id == 0:
        participant_id = input("Enter participant ID: ").strip()
        if participant_id == "":
            print("No ID entered. Aborting.")
            core.quit()

    if show_params == True:

        cold_df = pd.read_csv(csv_cold)
        warm_df = pd.read_csv(csv_warm)

        # Combine the two CSVs so we can look up the stimulus labels
        temp_df = pd.concat(
            [cold_df, warm_df],
            axis=1
        ).reindex(cold_df.index)

        print(f"""
        We are about to start the experiment for:

        Subject: {participant_id}
        Baseline temperature: {baseline}

        Temperatures:
        """)

        for stim in stimuli_type:
            temperature = temp_df[stim].iloc[0]
            print(f"               {stim}: {temperature} °C")

        print(f"""
        Jitter post: {temp_data["jitter_response"]}
        Jitter pre: {temp_data["jitter_wait"]}
        Stimulus duration: {temp_data["duration"]}
        Plateau: {temp_data["plateau"]}
        """)


        while True:
                choice1 = input("Do you want to continue? (y/n): ").strip().lower()
                if choice1 == 'n':
                    print("Aborting...")
                    core.quit()
                elif choice1 == 'y':
                    print("Proceeding with the experiment...")
                    break
                else:
                    print("Invalid input. Please enter 'y' or 'n'.")

def check_files(participant_id, check=False):
    # Find ALL files starting with participant ID
    existing_files = glob.glob(f"Data/{participant_id}/experiment_data_sub_{participant_id}*.csv")

    # ----------------------------------------------------------
    # Determine safe filename WITHOUT overwriting anything
    # ----------------------------------------------------------
    if not existing_files:
        # No collision → safe to use original ID
        filename = participant_id
    else:
        suffixes = []

        for file in existing_files:
            # Extract name without extension
            name = os.path.splitext(os.path.basename(file))[0]

            # Remove initial prefix to isolate suffix area
            # experiment_data_sub_{participant_id}____
            prefix = f"experiment_data_sub_{participant_id}"
            suffix_part = name.replace(prefix, "", 1)

            # Example suffix_part outputs:
            # ""                      (no suffix)
            # "_1"
            # "_ses-block-1"
            # "_ses-block-1_2"

            # Look at the LAST segment after splitting by "_"
            last_piece = suffix_part.split("_")[-1]

            # If last piece is a digit → store it
            if last_piece.isdigit():
                suffixes.append(int(last_piece))

        # Next available numeric suffix
        next_suffix = (max(suffixes) + 1) if suffixes else 1

        filename = f"{participant_id}_{next_suffix}"

    print(f"Saving file as: {filename}")

    # ----------------------------------------------------------
    # Optional HUMAN CHECK to warn user before overwriting
    # ----------------------------------------------------------
    if check:
        if existing_files:
            print(f"\nParticipant ID '{participant_id}' already exists. Found:")
            for file in existing_files:
                print(f"  - {file}")

            while True:
                choice = input("Continue anyway and create a NEW suffixed file? (y/n): ").strip().lower()
                if choice == "n":
                    print("Aborting to avoid accidental overwrite.")
                    core.quit()
                elif choice == "y":
                    print("Proceeding...")
                    break
                else:
                    print("Invalid input, type 'y' or 'n'.")

    return filename
