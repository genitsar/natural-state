import pandas as pd

from src.birds_src.class_balance import Balancer


VALIDATION_PATH = "../../../input_data/birds_input/validation_results.csv"
OUTPUT_PATH = "../../../output_data/birds_output/class_balance.csv"

# -------- Testing class functionality --------


# Read validation data
validation = pd.read_csv(VALIDATION_PATH)

# Create summary info for each species on true and false class counts and save as csv
summary = Balancer.compute_class_balance(validation)
print(summary.to_string(index=False))
summary.to_csv(OUTPUT_PATH, index=False)
summary

# Replace 1 in the validation set with 0.9999, the maximum number before 1 in the prediction set

