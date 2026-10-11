import pandas as pd

from src.birds_src.calibrate import Calibrator
from src.birds_src.label_predictions import Labeller


VALIDATION_PATH = "../../../input_data/birds_input/validation_results.csv"
PREDICTIONS_PATH = "../../../input_data/birds_input/birdnet_predictions.csv"
OUTPUT_PATH = "../../../output_data/birds_output/birdnet_predictions_labelled.csv"

# -------- Testing class functionality --------


# Test function label_observations with made-up data
# Expected: A (fitted, threshold 0.5) -> 0.4 empty, 0.5 and 0.9 labelled A
#           B (accept_all)            -> both labelled B
#           C (accept_none)           -> both empty
#           D (no threshold row)      -> empty
tmp_predictions = pd.DataFrame({
    "common_name": ["A", "A", "A", "B", "B", "C", "C", "D"],
    "confidence": [0.4, 0.5, 0.9, 0.1, 0.8, 0.2, 0.99, 0.95]
})

tmp_thresholds = pd.DataFrame({
    "commonName": ["A", "B", "C"],
    "method": ["fitted", "accept_all", "accept_none"],
    "threshold": [0.5, None, None]
})

tmp_labelled = Labeller.label_observations(tmp_predictions, tmp_thresholds)
print(tmp_labelled.to_string(index=False))

# Test function count_observations
# Expected: A -> 3 predictions, 2 observations; B -> 2, 2; C -> 2, 0; D -> 1, 0
print(Labeller.count_observations(tmp_labelled).to_string(index=False))

# Read validation and predictions data
validation = pd.read_csv(VALIDATION_PATH)
predictions = pd.read_csv(PREDICTIONS_PATH)

# Find the thresholds, label all predictions and save as csv
thresholds = Calibrator.calibrate(validation)
labelled = Labeller.label_observations(predictions, thresholds)
print(Labeller.count_observations(labelled).to_string(index=False))
labelled.to_csv(OUTPUT_PATH, index=False)
