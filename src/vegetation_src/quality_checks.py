import difflib

import pandas as pd

# ---- Rules taken from the SOPs and the ODK forms ----
EXPECTED_QUADRATS = 20              # quadrats per survey
GPS_ACCURACY_MAX_M = 5              # required location accuracy
TRANSECT_LENGTH_M = 50              # length of the belt transect
MIDPOINT_OFFSET_MAX_M = 25          # how far the midpoint may be moved from the prescribed location

# ---- Tolerances chosen for this analysis (not in the SOPs) ----
TRANSECT_LENGTH_TOLERANCE_M = 10    # two endpoint fixes, each accurate to about 5 m
MIDPOINT_IMBALANCE_MAX_M = 10       # difference between the A-to-midpoint and midpoint-to-B distances
NORTH_SOUTH_TOLERANCE_DEG = 45      # a transect further than this from north-south is flagged
QUADRAT_DISTANCE_MAX_M = 15         # 2.5 m belt + about 5 m error on the quadrat and on the transect
MIN_DURATION_MIN = 30               # a survey of 20 quadrats faster than this is suspicious
MAX_DURATION_MIN = 180              # a survey slower than this was probably paused or left open
MIN_COMMENT_LETTERS = 3             # a comment with fewer letters carries no information
GENUS_SIMILARITY = 0.8              # how close a typed genus must be to a known one to suggest a typo

FLAG_COLUMNS = ["level", "check", "severity", "plot_name", "survey_key", "record_key", "detail"]


class Checker:
    """ Includes functions to flag data quality issues. The data itself is never changed """

    # =========================== Method to Build Flags ================================================================

    @staticmethod
    def make_flags(rows, level, check, severity, key_column, detail):
        """ Turns the rows that fail a check into flags with a common set of columns """


        flags = pd.DataFrame({
            "level": level,
            "check": check,
            "severity": severity,
            "plot_name": rows.get("plot_name"),
            "survey_key": rows.get("survey_key"),
            "record_key": rows[key_column],
            "detail": detail,
        }, index=rows.index)

        return flags[FLAG_COLUMNS]

    # =========================== Methods to Check Surveys =============================================================

    @staticmethod
    def check_surveys(surveys, plots, quadrats):
        """ Flags issues at the level of a survey submission """

        flags = []

        # More than one survey for the same plot
        repeated = surveys[surveys.duplicated("plot_name", keep=False)]
        flags.append(Checker.make_flags(
            repeated, "survey", "plot_surveyed_more_than_once", "error", "survey_key",
            "Plot has " + repeated.groupby("plot_name")["survey_key"].transform("size").astype(str) + " surveys"))

        # Survey already rejected by a reviewer in ODK
        rejected = surveys[surveys["is_rejected"]]
        flags.append(Checker.make_flags(
            rejected, "survey", "survey_rejected_in_review", "info", "survey_key",
            "Review state is rejected; excluded from the summaries"))

        # Survey of a plot that is not registered or not viable
        viable_plots = plots.loc[plots["is_viable"] == "yes", "plot_name"]
        not_viable = surveys[~surveys["plot_name"].isin(viable_plots)]
        flags.append(Checker.make_flags(
            not_viable, "survey", "survey_on_unregistered_or_non_viable_plot", "error", "survey_key",
            "Plot is not registered as viable"))

        # Survey of a backup plot
        backup = surveys[surveys["plot_status"] == "backup"]
        flags.append(Checker.make_flags(
            backup, "survey", "backup_plot_surveyed", "info", "survey_key",
            "Backup plot used; check that it replaces a non-viable primary plot"))

        # Wrong number of quadrats
        counts = quadrats.groupby("survey_key").size()
        surveys = surveys.assign(quadrat_count=surveys["survey_key"].map(counts).fillna(0).astype(int))
        wrong_count = surveys[surveys["quadrat_count"] != EXPECTED_QUADRATS]
        flags.append(Checker.make_flags(
            wrong_count, "survey", "wrong_number_of_quadrats", "error", "survey_key",
            wrong_count["quadrat_count"].astype(str) + " quadrats, expected " + str(EXPECTED_QUADRATS)))

        # Quadrat numbers that are repeated within a survey
        repeated_numbers = quadrats[quadrats.duplicated(["survey_key", "quadrat_number"], keep=False)]
        flags.append(Checker.make_flags(
            repeated_numbers, "survey", "repeated_quadrat_number", "error", "quadrat_key",
            "Quadrat number " + repeated_numbers["quadrat_number"].astype(str) + " appears more than once"))

        # Photos or other attachments missing from the submission
        missing_files = surveys[surveys["attachments_present"] < surveys["attachments_expected"]]
        flags.append(Checker.make_flags(
            missing_files, "survey", "attachments_missing", "error", "survey_key",
            missing_files["attachments_present"].astype(str) + " of "
            + missing_files["attachments_expected"].astype(str) + " attachments received"))

        # Survey duration outside the plausible range
        too_fast = surveys[surveys["duration_min"] < MIN_DURATION_MIN]
        flags.append(Checker.make_flags(
            too_fast, "survey", "survey_too_fast", "warning", "survey_key",
            "Took " + too_fast["duration_min"].round().astype(int).astype(str) + " minutes"))

        too_slow = surveys[surveys["duration_min"] > MAX_DURATION_MIN]
        flags.append(Checker.make_flags(
            too_slow, "survey", "survey_too_slow", "info", "survey_key",
            "Took " + too_slow["duration_min"].round().astype(int).astype(str) + " minutes"))

        # Location at the end of the survey was not captured
        no_location = surveys[surveys["end_lat"].isna()]
        flags.append(Checker.make_flags(
            no_location, "survey", "end_location_missing", "warning", "survey_key",
            "Background location at submission is empty"))

        return pd.concat(flags, ignore_index=True)

    # =========================== Methods to Check Plots ===============================================================

    @staticmethod
    def check_plots(plots, surveys):
        """ Flags issues at the level of a registered plot """

        flags = []
        viable = plots[plots["is_viable"] == "yes"]

        # Plot registered as not viable
        not_viable = plots[plots["is_viable"] != "yes"]
        flags.append(Checker.make_flags(
            not_viable, "plot", "plot_not_viable", "info", "registration_key",
            "Reason given: " + not_viable["non_viable_reason"].fillna("none")))

        # Viable plot without transect coordinates
        no_geometry = viable[viable[["a_lat", "mid_lat", "b_lat"]].isna().any(axis=1)]
        flags.append(Checker.make_flags(
            no_geometry, "plot", "transect_coordinates_missing", "error", "registration_key",
            "An endpoint or the midpoint has no location"))

        # Viable plot that has no accepted survey
        surveyed = surveys.loc[~surveys["is_rejected"], "plot_name"]
        not_surveyed = viable[~viable["plot_name"].isin(surveyed)]
        flags.append(Checker.make_flags(
            not_surveyed, "plot", "viable_plot_not_surveyed", "error", "registration_key",
            "No accepted herbaceous survey for this plot"))

        # Location accuracy worse than required at any of the three points
        worst_accuracy = viable[["a_accuracy", "mid_accuracy", "b_accuracy"]].max(axis=1)
        inaccurate = viable[worst_accuracy > GPS_ACCURACY_MAX_M]
        flags.append(Checker.make_flags(
            inaccurate, "plot", "transect_gps_accuracy_poor", "warning", "registration_key",
            "Worst accuracy " + worst_accuracy[inaccurate.index].round(1).astype(str) + " m"))

        # Transect length far from 50 m
        length_error = (viable["transect_length_m"] - TRANSECT_LENGTH_M).abs()
        wrong_length = viable[length_error > TRANSECT_LENGTH_TOLERANCE_M]
        flags.append(Checker.make_flags(
            wrong_length, "plot", "transect_length_off", "warning", "registration_key",
            "Endpoints are " + wrong_length["transect_length_m"].round(1).astype(str) + " m apart, expected 50"))

        # Midpoint not midway between the endpoints
        imbalance = (viable["a_to_mid_m"] - viable["mid_to_b_m"]).abs()
        off_centre = viable[imbalance > MIDPOINT_IMBALANCE_MAX_M]
        flags.append(Checker.make_flags(
            off_centre, "plot", "midpoint_not_central", "warning", "registration_key",
            "A to midpoint " + off_centre["a_to_mid_m"].round(1).astype(str)
            + " m, midpoint to B " + off_centre["mid_to_b_m"].round(1).astype(str) + " m"))

        # Midpoint moved too far from the prescribed location
        moved = viable[viable["midpoint_offset_m"] > MIDPOINT_OFFSET_MAX_M]
        flags.append(Checker.make_flags(
            moved, "plot", "midpoint_too_far_from_prescribed", "error", "registration_key",
            "Midpoint is " + moved["midpoint_offset_m"].round(1).astype(str) + " m from the prescribed location"))

        # Transect not laid out north-south
        from_north = viable["bearing_deg"].where(viable["bearing_deg"] <= 90, 180 - viable["bearing_deg"])
        not_north_south = viable[from_north > NORTH_SOUTH_TOLERANCE_DEG]
        flags.append(Checker.make_flags(
            not_north_south, "plot", "transect_not_north_south", "info", "registration_key",
            "Transect runs " + from_north[not_north_south.index].round().astype(int).astype(str)
            + " degrees away from north-south"))

        # Geohash recorded at registration differs from the prescribed one
        other_geohash = plots[plots["geohash"] != plots["prescribed_geohash"]]
        flags.append(Checker.make_flags(
            other_geohash, "plot", "geohash_mismatch", "warning", "registration_key",
            "Registered " + other_geohash["geohash"].astype(str)
            + ", prescribed " + other_geohash["prescribed_geohash"].astype(str)))

        return pd.concat(flags, ignore_index=True)

    # =========================== Methods to Check Quadrats ============================================================

    @staticmethod
    def check_quadrats(quadrats, species_records):
        """ Flags issues at the level of a quadrat """

        flags = []

        # Location accuracy worse than required
        inaccurate = quadrats[quadrats["accuracy"] > GPS_ACCURACY_MAX_M]
        flags.append(Checker.make_flags(
            inaccurate, "quadrat", "quadrat_gps_accuracy_poor", "warning", "quadrat_key",
            "Accuracy " + inaccurate["accuracy"].round(1).astype(str) + " m"))

        # Quadrat recorded far from the registered transect
        far = quadrats[quadrats["distance_to_transect_m"] > QUADRAT_DISTANCE_MAX_M]
        flags.append(Checker.make_flags(
            far, "quadrat", "quadrat_far_from_transect", "warning", "quadrat_key",
            "Quadrat " + far["quadrat_number"].astype(str) + " is "
            + far["distance_to_transect_m"].round(1).astype(str) + " m from the registered transect"))

        # Two quadrats with exactly the same coordinates
        same_place = quadrats[quadrats.duplicated(["lat", "lon"], keep=False)]
        flags.append(Checker.make_flags(
            same_place, "quadrat", "quadrat_location_repeated", "warning", "quadrat_key",
            "Quadrat " + same_place["quadrat_number"].astype(str) + " shares its coordinates with another quadrat"))

        # Photo taken earlier than the photo of the previous quadrat
        ordered = quadrats.sort_values(["survey_key", "quadrat_number"])
        gap = ordered.groupby("survey_key")["photo_time"].diff().dt.total_seconds()
        out_of_order = ordered[gap < 0]
        flags.append(Checker.make_flags(
            out_of_order, "quadrat", "quadrat_photo_out_of_order", "warning", "quadrat_key",
            "Quadrat " + out_of_order["quadrat_number"].astype(str) + " was photographed before the previous one"))

        # No herbaceous species present
        empty = quadrats[quadrats["herbs_present"] == "no"]
        flags.append(Checker.make_flags(
            empty, "quadrat", "no_herbs_recorded", "info", "quadrat_key",
            "Quadrat " + empty["quadrat_number"].astype(str) + " has no herbaceous species; confirm it is bare"))

        # Additional species declared but none entered
        with_additional = species_records.loc[species_records["source"] != "listed", "quadrat_key"]
        declared = quadrats[(quadrats["additional_species_present"] == "yes")
                            & ~quadrats["quadrat_key"].isin(with_additional)]
        flags.append(Checker.make_flags(
            declared, "quadrat", "additional_species_declared_but_missing", "error", "quadrat_key",
            "Quadrat " + declared["quadrat_number"].astype(str)
            + " says additional species are present but none were entered"))

        # Comment with no usable content
        letters = quadrats["comment"].fillna("").str.count(r"[A-Za-z]")
        junk = quadrats[quadrats["comment"].notna() & (letters < MIN_COMMENT_LETTERS)]
        flags.append(Checker.make_flags(
            junk, "quadrat", "comment_not_informative", "info", "quadrat_key",
            "Comment is " + junk["comment"].map(repr)))

        return pd.concat(flags, ignore_index=True)

    # =========================== Methods to Check Species Records =====================================================

    @staticmethod
    def find_possible_genus_typos(typed_names, known_genera):
        """ For each typed name, returns the known genus it is close to but does not match, else None """

        def closest_genus(name):
            genus = name.strip().split(" ")[0]
            if genus in known_genera:
                return None
            matches = difflib.get_close_matches(genus, known_genera, n=1, cutoff=GENUS_SIMILARITY)
            return matches[0] if matches else None

        return typed_names.map(closest_genus)

    @staticmethod
    def check_species(species_records, species_list):
        """ Flags issues at the level of a species record """

        flags = []
        typed = species_records[species_records["source"] == "new_missing"]

        # Record without a species name
        unnamed = species_records[species_records["species_name"].isna()]
        flags.append(Checker.make_flags(
            unnamed, "species", "species_name_missing", "error", "record_key",
            "Entry mode " + unnamed["source"] + " but no species was chosen"))

        # Same species entered twice in one quadrat
        twice = species_records[species_records["taxon"].notna()
                                & species_records.duplicated(["quadrat_key", "taxon"], keep=False)]
        flags.append(Checker.make_flags(
            twice, "species", "species_repeated_in_quadrat", "warning", "record_key",
            twice["species_name"].astype(str) + " is recorded more than once in the quadrat"))

        # Typed name with spaces at the start or the end
        padded = typed[typed["typed_name"] != typed["typed_name"].str.strip()]
        flags.append(Checker.make_flags(
            padded, "species", "typed_name_has_extra_spaces", "warning", "record_key",
            "Typed as " + padded["typed_name"].map(repr)))

        # Typed name not in the Genus_species format the SOP asks for
        not_canonical = typed[~typed["typed_name"].str.strip().str.fullmatch(r"[A-Z][a-z-]+_[a-z-]+")]
        flags.append(Checker.make_flags(
            not_canonical, "species", "typed_name_not_in_sop_format", "info", "record_key",
            "Typed as " + not_canonical["typed_name"].map(repr) + ", SOP format is Genus_species"))

        # Typed as missing although the species is on the approved list
        on_list = typed[typed["typed_name"].str.strip().isin(species_list["label"])]
        flags.append(Checker.make_flags(
            on_list, "species", "typed_species_already_on_list", "warning", "record_key",
            on_list["typed_name"].astype(str) + " is on the approved species list"))

        # Typed genus that looks like a misspelling of a known genus
        known_genera = sorted(set(species_list["genus"]) | set(species_list["label"].str.split(" ").str[0]))
        suggestion = Checker.find_possible_genus_typos(typed["typed_name"], known_genera)
        misspelled = typed[suggestion.notna()]
        flags.append(Checker.make_flags(
            misspelled, "species", "typed_genus_possibly_misspelled", "warning", "record_key",
            "Typed " + misspelled["typed_name"].map(repr) + ", close to genus " + suggestion[misspelled.index]))

        # Same typed name registered as a new species more than once, giving it two ids
        accepted = typed[~typed["is_rejected"]]
        name_key = accepted["typed_name"].str.strip().str.lower()
        ids_per_name = accepted.groupby(name_key)["species_id"].transform("nunique")
        two_ids = accepted[ids_per_name > 1]
        flags.append(Checker.make_flags(
            two_ids, "species", "typed_species_registered_twice", "warning", "record_key",
            two_ids["typed_name"].astype(str) + " was added as a new species in more than one survey"))

        return pd.concat(flags, ignore_index=True)

    # =========================== Method to Run All Checks =============================================================

    @staticmethod
    def run_all(data):
        """ Runs every check and returns all flags in one table """

        flags = pd.concat([
            Checker.check_surveys(data["surveys"], data["plots"], data["quadrats"]),
            Checker.check_plots(data["plots"], data["surveys"]),
            Checker.check_quadrats(data["quadrats"], data["species_records"]),
            Checker.check_species(data["species_records"], data["species_list"]),
        ], ignore_index=True)

        return flags
