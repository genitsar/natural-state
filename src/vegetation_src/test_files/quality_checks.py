import pandas as pd

from src.vegetation_src.load_data import Loader
from src.vegetation_src.quality_checks import Checker


INPUT_DIR = "../../../input_data/vegetation_input"
OUTPUT_PATH = "../../../output_data/vegetation_output/flags.csv"

# -------- Testing class functionality --------


# Test function make_flags with made-up data
# Expected: one flag per row, with the common columns and the detail text of each row
tmp_rows = pd.DataFrame({
    "plot_name": ["P1", "P2"],
    "survey_key": ["S1", "S2"],
    "duration_min": [12, 20],
})
print(Checker.make_flags(tmp_rows, "survey", "survey_too_fast", "warning", "survey_key",
                         "Took " + tmp_rows["duration_min"].astype(str) + " minutes").to_string(index=False))

# Test function find_possible_genus_typos
# Expected: "Ipomea" is close to Ipomoea, "Sida" is known so empty, "Zzzz" has no close match so empty
tmp_names = pd.Series(["Ipomea sinensis", "Sida cordifolia", "Zzzz alba"])
print(Checker.find_possible_genus_typos(tmp_names, ["Ipomoea", "Sida"]).tolist())

# Read the real data, run every check and save the flags as csv
data = Loader.load(INPUT_DIR)
flags = Checker.run_all(data)
print(flags.groupby(["level", "check", "severity"]).size().to_string())
print("Total flags:", len(flags))
flags.to_csv(OUTPUT_PATH, index=False)
