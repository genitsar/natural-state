""" Runs the bird analysis from start to finish.

Run this file from the project root so that imports from src and
paths under input_data and output_data resolve correctly.
"""
import pandas as pd

from src.birds_src.class_balance import Balancer
from src.birds_src.calibrate import Calibrator
from src.birds_src.label_predictions import Labeller
from src.birds_src.plot_calibration import CalibrationPlotter

VALIDATION_PATH = "input_data/birds_input/validation_results.csv"
PREDICTIONS_PATH = "input_data/birds_input/birdnet_predictions.csv"

OUTPUT_PATH = "output_data/birds_output/class_balance.csv"
THRESHOLDS_PATH = "output_data/birds_output/thresholds.csv"
LABELLED_PATH = "output_data/birds_output/birdnet_predictions_labelled.csv"
FIGURE_PATH = "output_data/birds_output/figures/calibration_curves.png"

def main():

    # Read validation data
    validation = pd.read_csv(VALIDATION_PATH)

    # Step 1: Count true/false counts per species to evaluate balance of target
    Balancer.compute_class_balance(validation)

    # Step 2: Calibrate the scores per species and find the 99% threshold
    thresholds = Calibrator.calibrate(validation)
    print(thresholds.to_string(index=False))
    thresholds.to_csv(THRESHOLDS_PATH, index=False)

    # Draw the validated clips and the fitted curve per species
    CalibrationPlotter.draw_calibration(validation, thresholds, FIGURE_PATH)

    # Read predictions data
    predictions = pd.read_csv(PREDICTIONS_PATH)

    # Step 3: Add the observation column to the predictions
    labelled = Labeller.label_observations(predictions, thresholds)
    print(Labeller.count_observations(labelled).to_string(index=False))
    labelled.to_csv(LABELLED_PATH, index=False)


if __name__ == "__main__":
    main()
