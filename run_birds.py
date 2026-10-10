""" Runs the bird analysis from start to finish.

Run this file from the project root so that imports from src and
paths under input_data and output_data resolve correctly.
"""

from src.birds_src.class_balance import Balancer


def main():
    # Step 1: Count true, correct and wrong clips per species
    Balancer.run()

    # Step 2: Fit the model per species and find the 99% cut-off
    # (src/birds_src/fit_thresholds.py, not written yet)

    # Step 3: Add the observation column to the predictions
    # (src/birds_src/label_predictions.py, not written yet)


if __name__ == "__main__":
    main()
