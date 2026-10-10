""" Runs the bird analysis from start to finish.

Run this file from the project root so that imports from src and
paths under input_data and output_data resolve correctly.
"""
import pandas as pd

from src.birds_src.class_balance import Balancer
from src.birds_src.calibrate import Calibrator

VALIDATION_PATH = "input_data/birds_input/validation_results.csv"
OUTPUT_PATH = "output_data/birds_output/class_balance.csv"
THRESHOLDS_PATH = "output_data/birds_output/thresholds.csv"

def main():

    # Read validation data
    validation = pd.read_csv(VALIDATION_PATH)

    # Step 1: Count true/false counts per species to evaluate balance of target
    Balancer.compute_class_balance(validation)

    # Step 2: Calibrate the scores per species and find the 99% threshold
    thresholds = Calibrator.calibrate(validation)
    print(thresholds.to_string(index=False))
    thresholds.to_csv(THRESHOLDS_PATH, index=False)

    # Step 3: Add the observation column to the predictions
    # (src/birds_src/label_predictions.py, not written yet)


if __name__ == "__main__":
    main()
