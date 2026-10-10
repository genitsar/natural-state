import pandas as pd

from src.birds_src.calibrate import Calibrator


VALIDATION_PATH = "../../../input_data/birds_input/validation_results.csv"
OUTPUT_PATH = "../../../output_data/birds_output/thresholds.csv"

# -------- Testing class functionality --------


# Test functions to_logit and to_confidence
# Expected: 0.5 -> 0, 0.9 -> 2.197, and 1.0 capped to 0.9999 -> 9.210
scores = pd.Series([0.1, 0.5, 0.9, 1.0])
logits = Calibrator.to_logit(scores)
print(logits.round(3).tolist())
print(Calibrator.to_confidence(logits).round(4).tolist())

# Test function find_threshold
# Expected: with intercept 0 and slope 1 the threshold is the target itself, 0.99
print(round(Calibrator.find_threshold(0, 1), 4))

# Read validation data
validation = pd.read_csv(VALIDATION_PATH)

# Test function fit_calibration on one species
nightjar = validation[validation["commonName"] == "Abyssinian Nightjar"]
print(Calibrator.fit_calibration(nightjar))

# Calibrate all species and save as csv
thresholds = Calibrator.calibrate(validation)
print(thresholds.to_string(index=False))
thresholds.to_csv(OUTPUT_PATH, index=False)
