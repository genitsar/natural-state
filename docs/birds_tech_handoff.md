# Bird Challenge: Tech Hand-off

How to turn BirdNET predictions into observations automatically on NS Analytics, once the predictions have been recorded.

This document assumes the upload and the BirdNET run already work. It covers what comes after. A reference implementation is in this repository, and the reasoning behind each decision is in `docs/birds_report.md`.

## 1. What to build

Two jobs and one table between them.

```
validated clips  ->  CALIBRATE  ->  thresholds table
                                         |
new predictions  ->  LABEL  <------------+   ->  predictions with an observation field
```

- **Calibrate** learns, for each species, the confidence score above which a prediction is at least 99% likely to be correct. It runs rarely, when validated clips change.
- **Label** applies the stored thresholds to predictions. It runs after every BirdNET run. It is a join and a comparison, with no statistics involved.

Keeping the two apart matters. Labelling must be fast and must give the same answer every time for the same threshold. Calibration is slow-changing, needs human input, and should be reviewed before its results are used.

## 2. How observations are derived from predictions

BirdNET's confidence score is not a probability, and the same score means different things for different species. So the score is calibrated per species against clips an ornithologist has checked, following Wood and Kahl (2024).

For one species:

1. Take its validated clips: the confidence score and the verdict (1 correct, 0 incorrect).
2. Cap the score to the range 0.0001 to 0.9999, then transform it: `logit = ln(score / (1 - score))`.
3. Fit a logistic regression of the verdict on the logit score. This gives an intercept and a slope.
4. Solve for the score at which the fitted probability equals the target:

   ```
   logit_threshold = (ln(target / (1 - target)) - intercept) / slope
   threshold       = 1 / (1 + exp(-logit_threshold))
   ```

5. A prediction is an observation when `confidence >= threshold`.

**What the threshold means.** The threshold is the confidence score at which a prediction's probability of being correct reaches 99%. Predictions above it are more likely still to be correct, so this implies a positive predictive value (precision) of at least 99% for the observations, to the extent that the fitted curve is right. It is a statement about how trustworthy the kept predictions are. It says nothing about recall, the share of correct predictions that are kept.

Step 3 only works when the validated clips contain enough of both verdicts. When they do not, a rule replaces the curve:

| Validated clips for the species | Method | Effect on its predictions |
|---|---|---|
| At least 10 correct and 10 incorrect | `fitted` | Observation when the score reaches the threshold |
| Fewer than 10 incorrect | `accept_all` | All are observations |
| Fewer than 10 correct | `accept_none` | None are observations |
| No validated clips at all | no row in the table | None are observations |

The order of the rows matters: test for too few correct clips first, so a species with almost no validated clips of either kind falls to `accept_none`.

On the sample data this gives one fitted species (Abyssinian Nightjar, threshold 0.667), two accepted in full (African Black-headed Oriole, Three-banded Plover) and one rejected in full (Red-billed Firefinch).

## 3. Decisions made, and why

| Decision | Choice | Why |
|---|---|---|
| Regress on the logit of the score | Yes | High scores are compressed near 1; the paper recommends it |
| Cap for scores of exactly 0 or 1 | 0.0001 and 0.9999 | The logit of 0 or 1 is infinite. Scores are stored to four decimals |
| BirdNET sensitivity | Assumed 1.0 | Not recorded with the predictions. If a different sensitivity is used, divide the logit by it |
| Minimum clips of each verdict to fit | 10 | Below this a single clip can move the threshold a long way. On the sample data, one incorrect Plover clip produced thresholds from 0.26 to 0.82 depending on the fitting method |
| Too few incorrect clips | Accept all | The validated sample shows correct predictions across the score range |
| Too few correct clips | Accept none | The validated sample shows the predictions cannot be trusted |
| Value of `observation` | Species name, or empty | Reads as what was observed in the clip |

Two of these are judgement calls that the Biometrics team should confirm: the minimum of 10, and accepting all predictions when incorrect clips are scarce. The second does not prove 99% precision. With 150 validated clips and no errors, the evidence supports about 98%.

## 4. Scope of a threshold

A threshold is valid only for the conditions its validated clips came from. Scores change with the recorder model, the sample rate, the BirdNET version and the place.

Key each threshold by:

- species
- BirdNET model version (and sensitivity, once recorded)
- project, and the recorder hardware or recording settings if these vary within a project

A prediction should only be labelled with a threshold whose key matches. If none matches, it gets no observation. Do not fall back to another project's threshold for the same species.

## 5. Data model

### `bird_validation`: input to calibration

One row per validated clip. Today this arrives as a file; it should become a table that validators add to.

| Column | Notes |
|---|---|
| `prediction_id` | Link to the prediction that was validated. The sample file has no such link; add one |
| `species_code` | Use the eBird code, not the common name. The sample files spell the name column differently (`commonName` and `common_name`) |
| `confidence` | At full precision. The sample validation file is rounded to three decimals |
| `outcome` | 1 correct, 0 incorrect |
| `validated_by`, `validated_at` | For audit, and for second opinions |
| `model_version` | BirdNET version |

### `bird_threshold`: output of calibration, input to labelling

One row per species and scope, per calibration run.

| Column | Notes |
|---|---|
| `threshold_version` | Identifies the calibration run |
| scope columns | Project, model version, recorder set-up |
| `species_code` | |
| `validated_total`, `validated_correct`, `validated_incorrect` | The evidence behind the row |
| `method` | `fitted`, `accept_all` or `accept_none` |
| `intercept`, `slope` | Filled when `method` is `fitted` |
| `threshold` | Filled when `method` is `fitted` |
| `target_probability` | 0.99 |
| `status` | `draft` or `approved` (see section 6) |
| `created_at` | |

### Additions to the predictions table

| Column | Notes |
|---|---|
| `observation` | Species name when the clip is an observation, otherwise empty |
| `threshold_version` | Which thresholds produced the label |
| `probability_correct` | Optional but recommended: for fitted species, `1 / (1 + exp(-(intercept + slope * logit(confidence))))`. Lets a different target be applied later without refitting |

A clip is identified by audio file, offset within the file and species. The `selection` number in the BirdNET output restarts in every file and is not an identifier.

## 6. When each job runs

### Calibrate

- **Trigger:** validated clips are added or changed for a project.
- **Scope:** refit every species in that project and scope. It takes a moment.
- **Output:** a new `threshold_version`, written as `draft`.
- **Approval:** a person on the Biometrics team reviews the draft and approves it. Until then, labelling keeps using the last approved version. A threshold decides what counts as an observation for every future upload, so it should not change without someone looking at it.

Show the reviewer, for each species: the counts of correct and incorrect clips, the method chosen, the threshold, how it compares with the previous version, and the calibration plot (`CalibrationPlotter.draw_calibration` in the reference code).

### Label

- **Trigger:** a BirdNET run finishes for an upload.
- **Action:** join the new predictions to the approved thresholds for their scope and set `observation`.
- **Also trigger:** when a new threshold version is approved, relabel all existing predictions in that scope. Record the version on each row so the history is traceable.

Labelling is idempotent: the same predictions and the same threshold version always give the same labels.

## 7. Which clips to validate

The method depends on the validated sample, so the platform should help choose it. For each species in a project:

- **Sample across the whole score range,** not only the top. The curve is defined by where incorrect clips give way to correct ones.
- **Aim for at least 150 clips per species,** and continue until there are at least 10 of each verdict or it is clear there will not be.
- **Add low-scoring clips for species with no errors so far.** That is where an error is most likely, and about 300 clips with no errors are needed to support 99%.
- **Re-validate when conditions change:** new recorder hardware, a new site, a new season, or a new BirdNET version.

A species in `accept_all` or `accept_none` should be listed as "needs more validation" so it does not stay on a rule indefinitely.

## 8. Monitoring

Small checks that catch most problems:

| Check | Why |
|---|---|
| Predictions for a species with no threshold | New species detected; nobody has validated it yet |
| Share of predictions labelled as observations, per species and upload | A sudden change suggests the recordings or the model changed |
| Distribution of confidence scores per species over time | Drift means the thresholds may no longer apply |
| Scores outside 0 to 1, or missing | Upstream problem |
| Threshold version used by each upload | Confirms relabelling happened after an approval |

## 9. Acceptance test

Running both jobs on the sample files must reproduce these figures.

| Species | Method | Threshold |
|---|---|---|
| Abyssinian Nightjar | `fitted` | 0.6666 |
| African Black-headed Oriole | `accept_all` | none |
| Three-banded Plover | `accept_all` | none |
| Red-billed Firefinch | `accept_none` | none |

Nightjar intercept 3.1590 and slope 2.0723.

The labelled results:

| Species | Predictions | Labelled as observation | Left empty |
|---|---|---|---|
| African Black-headed Oriole | 18,054 | 18,054 | 0 |
| Three-banded Plover | 1,015 | 1,015 | 0 |
| Abyssinian Nightjar | 10,187 | 3,147 | 7,040 |
| Red-billed Firefinch | 235 | 0 | 235 |
| Total | 29,491 | 22,216 | 7,275 |

An empty `observation` means the prediction is not certain enough to count. It does not mean the species is absent, and the interface should not present it that way.

Edge cases the reference tests cover, in `src/birds_src/test_files/`:

- a score exactly at the threshold is an observation
- a score of exactly 1.0 does not produce an infinite value
- a species with no threshold row gets no observations

## 10. Open questions

1. **Where do validated clips come from in production?** The design assumes a validation workflow that writes to a table. Today it is a file.
2. **Is the unit of a threshold the project, the deployment or the recorder model?** Section 4 proposes project plus recorder set-up. The Biometrics team should decide.
3. **Should the Plover-type case use the fitted threshold after all?** One incorrect clip in 150 gives a fitted threshold of 0.259. The rule here ignores it. See the report for both sides.
4. **Is a single clip the right unit of observation?** Wood and Kahl suggest also requiring detections on two or more days before treating a species as present at a site. That would be a further step after labelling.
5. **Should uncertainty be stored?** The Nightjar threshold has a bootstrap interval of 0.45 to 0.82. A conservative option is to use the upper end.
6. **Python or R for calibration?** It is a few lines in either. The paper's code is R (`glm` with a binomial family), and the reference here uses `statsmodels` in Python. Both fit the same model.

## 11. Where the reference code is

| File | Contents |
|---|---|
| `run_birds.py` | Runs every step and writes the outputs |
| `src/birds_src/class_balance.py` | `Balancer`: counts of correct and incorrect clips per species |
| `src/birds_src/calibrate.py` | `Calibrator`: transforms, the fit, the threshold and the choice of method |
| `src/birds_src/label_predictions.py` | `Labeller`: the `observation` field and counts per species |
| `src/birds_src/plot_calibration.py` | `CalibrationPlotter`: the figure for reviewing a calibration |
| `output_data/birds_output/` | Class balance, thresholds and the figure from the sample data |
