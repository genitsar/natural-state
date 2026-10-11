import pandas as pd

from src.vegetation_src.load_data import Loader
from src.vegetation_src.quality_checks import Checker
from src.vegetation_src.report import Reporter


INPUT_DIR = "../../../input_data/vegetation_input"
OUTPUT_DIR = "../../../output_data/vegetation_output/"

# -------- Testing class functionality --------


# Test functions richness_estimate and species_accumulation with made-up data
# Three plots: P1 has species a and b, P2 has a and c, P3 has only a
# Expected: 3 observed species, 2 found in one plot only, 0 found in two plots,
#           Chao2 = 3 + (2/3) * 2 * 1 / 2 = 3.7, and the curve ends at 3 species after 3 plots
tmp_records = pd.DataFrame({
    "plot_name": ["P1", "P1", "P2", "P2", "P3"],
    "taxon": ["a", "b", "a", "c", "a"],
})
print(Reporter.richness_estimate(tmp_records))
print(Reporter.species_accumulation(tmp_records).round(2).to_string(index=False))

# Read the real data and run the checks
data = Loader.load(INPUT_DIR)
flags = Checker.run_all(data)

# Survey-level and plot-level summaries
survey_summary = Reporter.survey_summary(data, flags)
plot_summary = Reporter.plot_summary(data, flags)
print(survey_summary.drop(columns="survey_key").to_string(index=False))
print(plot_summary.to_string(index=False))
survey_summary.to_csv(OUTPUT_DIR + "survey_summary.csv", index=False)
plot_summary.to_csv(OUTPUT_DIR + "plot_summary.csv", index=False)

# Sampling effort
effort = Reporter.effort_by_stratum(data)
curves, estimates = Reporter.sampling_effort(data)
print(effort.to_string(index=False))
print(estimates.to_string(index=False))
effort.to_csv(OUTPUT_DIR + "effort_by_stratum.csv", index=False)
estimates.to_csv(OUTPUT_DIR + "richness_estimates.csv", index=False)
curves.to_csv(OUTPUT_DIR + "species_accumulation.csv", index=False)

# Figures
Reporter.draw_accumulation(curves, OUTPUT_DIR + "figures/species_accumulation.png")
Reporter.draw_location_map(data, OUTPUT_DIR + "figures/transect_locations.png")
Reporter.draw_transects(data, OUTPUT_DIR + "figures/transects_and_quadrats.png")
