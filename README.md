# natural-state

Take-home project for the Senior Data Scientist role at Natural State. It has two challenges, each with a short report and a hand-off note for the Tech team.

| Challenge | Report | Tech hand-off | Run it |
|---|---|---|---|
| Birds | [docs/birds_report.md](docs/birds_report.md) | [docs/birds_tech_handoff.md](docs/birds_tech_handoff.md) | `python run_birds.py` |
| Vegetation | [docs/vegetation_report.md](docs/vegetation_report.md) | [docs/vegetation_tech_handoff.md](docs/vegetation_tech_handoff.md) | `python run_vegetation.py` |

### Bird Analysis

**Question.** BirdNET labels 3-second audio clips with a species and a confidence score. Which of its 29,491 predictions are reliable enough to count as observations?

**Approach.** Following Wood and Kahl (2024), an ornithologist's verdicts on 551 clips are used to calibrate the score for each species: a logistic regression of correct or incorrect on the logit of the confidence score, solved for the score at which a prediction is 99% likely to be correct. A species gets a fitted threshold only if it has at least 10 correct and 10 incorrect validated clips. Otherwise a rule applies.

| Species | Validated correct | Method | Threshold | Predictions | Observations |
|---|---|---|---|---|---|
| Abyssinian Nightjar | 117 of 150 | Fitted curve | 0.667 | 10,187 | 3,147 |
| African Black-headed Oriole | 150 of 150 | Accept all | none | 18,054 | 18,054 |
| Three-banded Plover | 149 of 150 | Accept all | none | 1,015 | 1,015 |
| Red-billed Firefinch | 6 of 101 | Accept none | none | 235 | 0 |

**Code.** `src/birds_src/`: `class_balance.py` counts correct and incorrect clips per species, `calibrate.py` fits the curve and finds the threshold, `label_predictions.py` adds the `observation` column, `plot_calibration.py` draws the calibration figure.

### Vegetation Analysis

**Question.** Field teams recorded herbaceous species in 20 quadrats along each of 30 transects. Can the records be trusted, and is there enough of them?

**Approach.** The ODK exports are joined into five tables, and 33 checks are run at survey, plot, quadrat and species level. Each failing record becomes a flag with a severity. Nothing in the data is changed. The report then summarises surveys and plots, assesses sampling effort and maps the transects.

**Main findings.**

- The savanna stratum is complete: 30 plots surveyed, 20 quadrats each. The shrubland stratum (11 prescribed locations) was not sampled.
- 234 flags were raised: 16 errors, 116 warnings and 102 informational.
- The approved species list fits the site poorly. 57.5% of species records were entered as additional species and 30.1% are unidentified.
- Counting species by name gives 181; counting by entity id gives 132. Richness is provisional until the unknowns are identified.
- The species accumulation curve is still rising at 30 plots.

**Code.** `src/vegetation_src/`: `load_data.py` reads and joins the tables, `quality_checks.py` holds the checks and their thresholds, `report.py` builds the summaries and figures.

### Project structure

```
run_birds.py, run_vegetation.py     run each analysis from start to finish
src/birds_src/                      bird analysis classes
src/vegetation_src/                 vegetation analysis classes
src/*/test_files/                   one test script per class, with expected results in the comments
input_data/                         source data (not in the repository, see below)
output_data/                        tables and figures produced by the code
docs/                               the reports and Tech hand-offs
```

### Running the code

Install the dependencies with `pip install -r requirements.txt`, place the data as described below, and run the two scripts from the project root. The code was written for Python 3.14.

### Data

The source data supplied by Natural State is not included in this repository. To run the code, place the files as follows:

| Files | Folder |
|---|---|
| `birdnet_predictions.csv`, `validation_results.csv` | `input_data/birds_input/` |
| Entity lists (11 CSV files) | `input_data/vegetation_input/entity_lists/` |
| ODK data exports (4 CSV files) | `input_data/vegetation_input/odk_exports/` |
| ODK data collection forms (2 Excel files) | `input_data/vegetation_input/odk_forms/` |
| SOPs (2 PDF files) | `input_data/vegetation_input/sops/` |

The labelled bird predictions (`birdnet_predictions_labelled.csv`) are also kept out of the repository, because the file is a full copy of the source data with one added column. Running `run_birds.py` creates it.

### Use of AI

Claude (Anthropic) was used throughout as a coding and writing assistant, as the brief encourages. I reviewed the code and the reasoning and can explain each part.
