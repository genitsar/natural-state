""" Runs the vegetation QA/QC analysis from start to finish.

Run this file from the project root so that imports from src and
paths under input_data and output_data resolve correctly.
"""


def main():
    # Step 1: Read and join the ODK exports and entity lists
    # (src/vegetation_src/load_data.py, not written yet)

    # Step 2: Run the quality checks and produce the flags
    # (src/vegetation_src/quality_checks.py, not written yet)

    # Step 3: Build the summaries, sampling-effort assessment and map
    # (src/vegetation_src/report.py, not written yet)

    print("Vegetation analysis: no steps implemented yet.")


if __name__ == "__main__":
    main()
