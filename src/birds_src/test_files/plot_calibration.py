import pandas as pd

from src.birds_src.calibrate import Calibrator
from src.birds_src.plot_calibration import CalibrationPlotter


VALIDATION_PATH = "../../../input_data/birds_input/validation_results.csv"
OUTPUT_PATH = "../../../output_data/birds_output/figures/calibration_curves.png"

# -------- Testing class functionality --------


# Read validation data and find the thresholds
validation = pd.read_csv(VALIDATION_PATH)
thresholds = Calibrator.calibrate(validation)

# Test function draw_calibration
# Expected: a figure with four panels, one per species. Only the Abyssinian Nightjar has a curve
#           and a threshold line; the other three show their points and a note on the method used
CalibrationPlotter.draw_calibration(validation, thresholds, OUTPUT_PATH)
print("Figure saved to", OUTPUT_PATH)
