""" Runs the vegetation QA/QC analysis from start to finish.

Run this file from the project root so that imports from src and
paths under input_data and output_data resolve correctly.
"""

from src.vegetation_src.load_data import Loader
from src.vegetation_src.quality_checks import Checker
from src.vegetation_src.report import Reporter

INPUT_DIR = "input_data/vegetation_input"
OUTPUT_DIR = "output_data/vegetation_output/"


def main():

    # Step 1: Read and join the ODK exports and entity lists
    data = Loader.load(INPUT_DIR)

    # Step 2: Run the quality checks and save the flags (the data itself is not changed)
    flags = Checker.run_all(data)
    print(flags.groupby(["level", "severity"]).size().to_string())
    flags.to_csv(OUTPUT_DIR + "flags.csv", index=False)

    # Step 3a: Survey-level and plot-level summaries
    survey_summary = Reporter.survey_summary(data, flags)
    plot_summary = Reporter.plot_summary(data, flags)
    survey_summary.to_csv(OUTPUT_DIR + "survey_summary.csv", index=False)
    plot_summary.to_csv(OUTPUT_DIR + "plot_summary.csv", index=False)

    # Step 3b: Assessment of sampling effort
    effort = Reporter.effort_by_stratum(data)
    curves, estimates = Reporter.sampling_effort(data)
    print(effort.to_string(index=False))
    print(estimates.to_string(index=False))
    effort.to_csv(OUTPUT_DIR + "effort_by_stratum.csv", index=False)
    estimates.to_csv(OUTPUT_DIR + "richness_estimates.csv", index=False)
    curves.to_csv(OUTPUT_DIR + "species_accumulation.csv", index=False)

    # Step 3c: Figures, including the map of transect locations
    Reporter.draw_accumulation(curves, OUTPUT_DIR + "figures/species_accumulation.png")
    Reporter.draw_location_map(data, OUTPUT_DIR + "figures/transect_locations.png")
    Reporter.draw_transects(data, OUTPUT_DIR + "figures/transects_and_quadrats.png")


if __name__ == "__main__":
    main()
