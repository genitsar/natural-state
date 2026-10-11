# Vegetation Challenge: Tech Hand-off

How to run the herbaceous vegetation QA/QC automatically on NS Analytics and show the results on a project dashboard.

This document assumes the ODK tables have already reached the platform. It covers everything after that. A working reference implementation is in this repository, and its results on the sample data are in `docs/vegetation_report.md`.

## 1. What to build

A job that reads the raw ODK tables for one project, produces a table of quality flags and a few summary tables, and a dashboard that reads those tables.

```
raw ODK tables  ->  load and join  ->  run checks  ->  flags table
(never modified)                   ->  summarise   ->  summary tables  ->  dashboard
```

Three principles shape the design:

1. **Raw data is never changed.** The job only reads the ODK tables and writes to its own tables. Corrections are made by the project team in ODK, and the next run picks them up.
2. **Every check produces the same kind of row.** One flag is one record that failed one rule. This is what lets the dashboard, the filters and any future check share one table.
3. **Rules are configuration, not code.** Thresholds such as "20 quadrats" belong to a protocol version and should be stored, not hard-coded.

## 2. When it runs

Run the job for a project whenever one of these changes:

- a submission to `herbaceous_veg_survey` or `register_vegetation_plots` arrives, is edited, or has its review state changed
- one of the entity lists it reads is updated (`centroids`, `species`)

Recompute the whole project and survey replicate each time, and replace the previous results. The data is small (hundreds of rows per project), a full run takes a few seconds, and several checks compare records with each other (duplicate surveys, species registered twice), so incremental updates would add complexity for no benefit.

## 3. Inputs

| Raw table | One row is | Key | Links to |
|---|---|---|---|
| `register_vegetation_plots` | A plot registration | `KEY` | Sampling location, by plot name |
| `herbaceous_veg_survey` | A survey submission | `KEY` | Plot, by plot name |
| `herbaceous_veg_survey-quadrat_repeat` | A quadrat | `KEY` | Survey, by `PARENT_KEY` |
| `herbaceous_veg_survey-additional_species_repeat` | An additional species in a quadrat | `KEY` | Quadrat, by `PARENT_KEY` |
| `centroids` (entity list) | A prescribed sampling location | `choice_name` | |
| `species` (entity list) | A species on the approved list | `__id` | |

The columns used from each, and the short names the code gives them, are the three dictionaries at the top of `src/vegetation_src/load_data.py`.

### Things that will trip you up

- **Column names carry their form group.** `survey_begin-start_time`, `plot_metadata-collect_points-endpoint_a-location_endpoint_a-Latitude`. If the form's groups are renamed, the column names change. Map them in one place.
- **Listed species are packed into one cell.** `herb_species-selected_herb_species_uuids` holds species ids separated by spaces. Additional species are one row each in the repeat table. Both have to be combined to get all species in a quadrat.
- **The species id for an additional species is in one of three columns,** depending on how it was entered: `target_extra_name` (new), `select_reuse_unknown` or `select_reuse_missing` (reused). Take the first that is filled.
- **Count species by id, never by name.** The displayed name of the same entity changes between submissions (`Sida chrysantha`, `herb_063`, `herb_063 (Sida chrysantha)`). On the sample data, names give 181 species and ids give 132.
- **Coordinates in entity lists are text:** `"latitude longitude altitude accuracy"` in one field.
- **The plot id in the survey is not the plot id in the registration.** `plot_selection-selected_plot_uuid` in the survey is the `vegplots` entity id, while the same column name in the registration is the `centroids` entity id. Plot name is the reliable link between the two forms.
- **Timestamps carry a UTC offset.** Convert to UTC before subtracting.
- **An empty `ReviewState` means not yet reviewed,** not approved.
- **Photo file names are timestamps in milliseconds.** This is the only per-quadrat time available.

## 4. Processing steps

| Step | What it does | Reference |
|---|---|---|
| 1. Load | Select and rename columns, parse times and coordinates | `Loader.build_*` |
| 2. Join | Quadrat to survey to plot to prescribed location; build one species record per species per quadrat | `Loader.build_quadrats`, `Loader.build_species_records` |
| 3. Derive | Transect length, midpoint distances, bearing, quadrat distance to transect, survey duration | `Loader.build_plots`, `Loader.build_quadrats` |
| 4. Check | Run every rule, collect flags | `Checker.run_all` |
| 5. Summarise | Per survey, per plot, per stratum; accumulation curve and richness estimate | `Reporter.*` |

Distances are computed with a flat-earth approximation (metres per degree, corrected for latitude). It is accurate to centimetres over the tens of metres involved. If PostGIS is available, `ST_Distance` on geography types is an equally good choice.

## 5. Outputs to store

### `veg_qc_flag`: one row per failed check

| Column | Type | Notes |
|---|---|---|
| `project_id`, `replicate` | text | Scope of the run |
| `level` | text | `survey`, `plot`, `quadrat` or `species` |
| `check` | text | Stable identifier, see section 6 |
| `severity` | text | `error`, `warning` or `info` |
| `plot_name` | text | Always filled |
| `survey_key` | text | Empty for plot-level flags |
| `record_key` | text | ODK key of the exact record that failed |
| `detail` | text | Human-readable sentence with the values involved |
| `rule_version` | text | Version of the rule set that produced it |
| `run_at` | timestamp | |

A flag is identified by `check` + `record_key`. Keeping that identity stable across runs is what allows a reviewer's status to survive a re-run (section 8).

### Summary tables

| Table | One row is | Used by |
|---|---|---|
| `veg_qc_survey_summary` | A survey | Survey-level view |
| `veg_qc_plot_summary` | A registered plot | Plot-level view and map |
| `veg_qc_location_status` | A prescribed location, with its status | Map and coverage table |
| `veg_qc_effort` | A stratum and sample status | Sampling effort view |
| `veg_qc_accumulation` | A point on the accumulation curve | Sampling effort chart |
| `veg_qc_richness` | A richness estimate | Sampling effort view |

Their columns are those of the CSV files in `output_data/vegetation_output/`, which the reference code writes. The exception is the location status, which is not saved as a file; `Reporter.location_status` returns it.

## 6. Check catalogue

Severity: **error** breaks a written rule or makes the record unusable, **warning** needs a person to look, **info** is worth knowing and may be correct.

| Level | Check id | Severity | Rule |
|---|---|---|---|
| Survey | `plot_surveyed_more_than_once` | error | More than one survey for a plot |
| Survey | `survey_on_unregistered_or_non_viable_plot` | error | Plot is not registered as viable |
| Survey | `wrong_number_of_quadrats` | error | Quadrat count differs from the expected number |
| Survey | `repeated_quadrat_number` | error | A quadrat number occurs twice in a survey |
| Survey | `attachments_missing` | error | Fewer attachments received than expected |
| Survey | `survey_too_fast` | warning | Duration below the minimum |
| Survey | `end_location_missing` | warning | No background location at submission |
| Survey | `survey_too_slow` | info | Duration above the maximum |
| Survey | `survey_rejected_in_review` | info | Review state is rejected |
| Survey | `backup_plot_surveyed` | info | Plot status is backup |
| Plot | `transect_coordinates_missing` | error | A viable plot lacks an endpoint or midpoint |
| Plot | `viable_plot_not_surveyed` | error | A viable plot has no accepted survey |
| Plot | `midpoint_too_far_from_prescribed` | error | Midpoint further than the limit from the prescribed location |
| Plot | `transect_gps_accuracy_poor` | warning | Accuracy of any transect point worse than the limit |
| Plot | `transect_length_off` | warning | Endpoint distance outside the tolerance |
| Plot | `midpoint_not_central` | warning | The two halves of the transect differ by more than the limit |
| Plot | `geohash_mismatch` | warning | Registered geohash differs from the prescribed one |
| Plot | `transect_not_north_south` | info | Bearing further than the tolerance from north-south |
| Plot | `plot_not_viable` | info | Plot registered as not viable |
| Quadrat | `additional_species_declared_but_missing` | error | "Additional species present" is yes, but none were entered |
| Quadrat | `quadrat_gps_accuracy_poor` | warning | Accuracy worse than the limit |
| Quadrat | `quadrat_far_from_transect` | warning | Further than the limit from the registered transect |
| Quadrat | `quadrat_location_repeated` | warning | Identical coordinates to another quadrat |
| Quadrat | `quadrat_photo_out_of_order` | warning | Photo taken before the previous quadrat's photo |
| Quadrat | `no_herbs_recorded` | info | No herbaceous species present |
| Quadrat | `comment_not_informative` | info | Comment has fewer than the minimum number of letters |
| Species | `species_name_missing` | error | Record has no species |
| Species | `species_repeated_in_quadrat` | warning | Same species id twice in a quadrat |
| Species | `typed_name_has_extra_spaces` | warning | Typed name starts or ends with a space |
| Species | `typed_species_already_on_list` | warning | Typed name matches a species on the approved list |
| Species | `typed_genus_possibly_misspelled` | warning | Typed genus is not known but resembles a known genus |
| Species | `typed_species_registered_twice` | warning | Same typed name created as a new species in more than one survey |
| Species | `typed_name_not_in_sop_format` | info | Typed name is not `Genus_species` |

Adding a check means adding one function that returns rows in the flag format. Nothing else changes.

## 7. Configuration

Store these per protocol version, with the project able to override them. The defaults are the values used on the sample data.

| Parameter | Default | Source |
|---|---|---|
| `expected_quadrats` | 20 | SOP |
| `gps_accuracy_max_m` | 5 | SOP |
| `transect_length_m` | 50 | SOP |
| `midpoint_offset_max_m` | 25 | SOP |
| `transect_length_tolerance_m` | 10 | Analyst's choice |
| `midpoint_imbalance_max_m` | 10 | Analyst's choice |
| `north_south_tolerance_deg` | 45 | Analyst's choice |
| `quadrat_distance_max_m` | 15 | Analyst's choice |
| `min_duration_min`, `max_duration_min` | 30, 180 | Analyst's choice |
| `min_comment_letters` | 3 | Analyst's choice |
| `genus_similarity` | 0.8 | Analyst's choice |
| `accumulation_permutations`, `random_seed` | 200, 42 | Analyst's choice |

The values marked as the analyst's choice should be agreed with the Biometrics team before going live. Record the configuration version on every flag so that a change in a threshold can be told apart from a change in the data.

## 8. Dashboard

One page per project, with a filter for survey replicate.

### Header

Five figures: surveys accepted out of submitted, plots surveyed out of planned, open errors, open warnings, and the share of species records that are unidentified.

### Survey-level view

A table with one row per survey: plot, date, recorder, submitting team, duration, review state, quadrats, species records, distinct species, unidentified share, errors, warnings. Sortable, with rejected surveys visibly marked. Selecting a row lists that survey's flags.

### Plot-level view

A table with one row per registered plot: status, viability, stratum, transect length, midpoint offset, accepted surveys, distinct species, mean species per quadrat, errors, warnings. Selecting a row shows a small plan of the transect with its quadrats, the same view as the panels in `transects_and_quadrats.png`.

### Sampling effort

- Coverage table: planned, registered, viable and surveyed locations, by stratum and sample status.
- Species accumulation curve, with a second line for identified species only.
- Richness figures: observed, estimated (Chao2) and the share observed.
- Species list fit: listed species used, typed species, unknown species.

### Map

All prescribed locations on a base map, with marker colour for status (surveyed, registered but not surveyed, not viable, not registered) and marker shape for stratum. At high zoom, draw the transect line from endpoint A through the midpoint to endpoint B, and the quadrat points. Selecting a plot opens its row in the plot-level view.

### Flags

A table of all flags, filterable by severity, level, check, plot and recorder, with the `detail` sentence shown in full and a link to the record in ODK Central. This is the working list for whoever is cleaning the data.

### Flag status

Reviewers need to be able to mark a flag as **open**, **accepted as is** (looked at, data is correct) or **resolved** (data corrected in ODK). Store the status against `check` + `record_key` in a separate table, so a re-run does not reset it. A flag that no longer appears after a re-run is resolved automatically. This is the one piece of state the job does not own, and it should not be overwritten.

## 9. How the results are used downstream

- **Rejected surveys** are flagged but excluded from the plot summary and richness figures.
- **Errors should block** a plot's data from feeding credit calculations until they are resolved or accepted. Warnings and info should not block.
- **Richness figures are provisional** while unknown species remain unidentified. The dashboard should say so next to the numbers.

## 10. Acceptance test

Running the job on the sample data must reproduce these figures. They make a good regression test.

| Figure | Expected |
|---|---|
| Surveys, plots registered, quadrats, species records | 32, 31, 640, 2,243 |
| Flags in total | 234 |
| Errors, warnings, info | 16, 116, 102 |
| Checks that raise at least one flag | 25 of 33 |
| Distinct species in accepted surveys, by id | 132 |
| Distinct species names in accepted surveys | 181 |
| Chao2 estimate, all species | 190.7 |
| Locations surveyed, of 51 planned | 30 |

The reference code also has a small test per class in `src/vegetation_src/test_files/`, with made-up data and the expected result written beside each case.

## 11. Open questions

For the Tech and Biometrics teams to settle before this goes live:

1. **Who owns the thresholds,** and where are they edited?
2. **Should the estimators live in Python or in R?** Chao2 and the accumulation curve are a few lines here, but the Biometrics team works in R and may prefer to own them, for instance with the `vegan` or `iNEXT` packages.
3. **How are unknown species resolved?** `species_extra_ids` already maps some unknown labels to species names and marks duplicates. Once that mapping is maintained, richness should be computed after applying it, and the dashboard should show both the raw and the resolved figure.
4. **Should photos be checked?** Missing attachments are caught. Whether a photo actually shows a quadrat is not.
5. **Does the same job serve the woody vegetation survey?** The plot checks would be shared. The quadrat and species checks are specific to this form.

## 12. Where the reference code is

| File | Contents |
|---|---|
| `run_vegetation.py` | Runs every step and writes the outputs |
| `src/vegetation_src/load_data.py` | `Loader`: reading, joining, derived columns |
| `src/vegetation_src/quality_checks.py` | `Checker`: all checks and the thresholds |
| `src/vegetation_src/report.py` | `Reporter`: summaries, sampling effort, figures |
| `output_data/vegetation_output/` | Flags, summaries and figures from the sample data |
