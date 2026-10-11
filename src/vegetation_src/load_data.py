import numpy as np
import pandas as pd

# Columns kept from each raw table, with the short names used in the rest of the code
SURVEY_COLUMNS = {
    "KEY": "survey_key",
    "plot_selection-selected_plot_uuid": "plot_entity_id",
    "plot_selection-plot_name": "plot_name",
    "plot_selection-get_plot_status": "plot_status",
    "field_team_specifics-recorder_label": "recorder",
    "SubmitterName": "submitter",
    "DeviceID": "device",
    "survey_begin-start_time": "start_time",
    "survey_end-end_time": "end_time",
    "SubmissionDate": "submitted_at",
    "ReviewState": "review_state",
    "observations-quadrat_repeat_count": "quadrats_declared",
    "survey_end-quadrats_with_species": "quadrats_with_species",
    "survey_end-background_geopoint-Latitude": "end_lat",
    "survey_end-background_geopoint-Longitude": "end_lon",
    "AttachmentsPresent": "attachments_present",
    "AttachmentsExpected": "attachments_expected",
}

POINTS = "plot_metadata-collect_points-"
PLOT_COLUMNS = {
    "KEY": "registration_key",
    "plot_selection-plot_name": "plot_name",
    "plot_selection-sample_status": "sample_status",
    "plot_selection-stratum_label": "stratum",
    "plot_selection-geohash": "geohash",
    "plot_selection-is_plot_viable": "is_viable",
    "plot_selection-plot_establishment_notes": "non_viable_reason",
    "plot_metadata-ecosystem_type_name": "ecosystem_type",
    "field_team_specifics-recorder_label": "recorder",
    "survey_begin-start_time": "registered_at",
    POINTS + "endpoint_a-location_endpoint_a-Latitude": "a_lat",
    POINTS + "endpoint_a-location_endpoint_a-Longitude": "a_lon",
    POINTS + "endpoint_a-location_endpoint_a-Accuracy": "a_accuracy",
    POINTS + "midpoint-location_midpoint-Latitude": "mid_lat",
    POINTS + "midpoint-location_midpoint-Longitude": "mid_lon",
    POINTS + "midpoint-location_midpoint-Accuracy": "mid_accuracy",
    POINTS + "endpoint_b-location_endpoint_b-Latitude": "b_lat",
    POINTS + "endpoint_b-location_endpoint_b-Longitude": "b_lon",
    POINTS + "endpoint_b-location_endpoint_b-Accuracy": "b_accuracy",
}

QUADRAT_COLUMNS = {
    "KEY": "quadrat_key",
    "PARENT_KEY": "survey_key",
    "quadrat_number": "quadrat_number",
    "herbs_present": "herbs_present",
    "herb_species-selected_herb_species_uuids": "listed_species_ids",
    "additional_species_present": "additional_species_present",
    "quadrat_image": "photo",
    "location_quadrat-Latitude": "lat",
    "location_quadrat-Longitude": "lon",
    "location_quadrat-Accuracy": "accuracy",
    "quadrat_comment": "comment",
}

# Metres per degree, used to turn small differences in coordinates into metres
METRES_PER_DEGREE_LAT = 110540
METRES_PER_DEGREE_LON = 111320


class Loader:
    """ Includes functions to read the raw vegetation tables and join them into analysis tables """

    # =========================== Methods to Read Raw Tables ===========================================================

    @staticmethod
    def read_tables(input_dir):
        """ Reads the ODK exports and entity lists into a dictionary of dataframes """

        exports = input_dir + "/odk_exports/"
        entities = input_dir + "/entity_lists/"

        tables = {
            "surveys": pd.read_csv(exports + "herbaceous_veg_survey.csv"),
            "quadrats": pd.read_csv(exports + "herbaceous_veg_survey-quadrat_repeat.csv"),
            "additional_species": pd.read_csv(exports + "herbaceous_veg_survey-additional_species_repeat.csv"),
            "registrations": pd.read_csv(exports + "register_vegetation_plots.csv"),
            "centroids": pd.read_csv(entities + "centroids.csv"),
            "species": pd.read_csv(entities + "species.csv"),
        }

        return tables

    # =========================== Methods to Measure Distances =========================================================

    @staticmethod
    def to_local_metres(lat, lon, origin_lat, origin_lon):
        """ Converts coordinates to metres east (x) and north (y) of an origin point """

        x = (lon - origin_lon) * METRES_PER_DEGREE_LON * np.cos(np.radians(origin_lat))
        y = (lat - origin_lat) * METRES_PER_DEGREE_LAT

        return x, y

    @staticmethod
    def distance_m(lat1, lon1, lat2, lon2):
        """ Distance in metres between two points """

        x, y = Loader.to_local_metres(lat2, lon2, lat1, lon1)

        return np.hypot(x, y)

    @staticmethod
    def distance_to_segment_m(lat, lon, a_lat, a_lon, b_lat, b_lon):
        """ Shortest distance in metres from a point to the line segment between A and B """

        # Work in metres, with endpoint A as the origin
        px, py = Loader.to_local_metres(lat, lon, a_lat, a_lon)
        bx, by = Loader.to_local_metres(b_lat, b_lon, a_lat, a_lon)

        # Position of the closest point along the segment: 0 is A, 1 is B
        position = ((px * bx + py * by) / (bx ** 2 + by ** 2)).clip(0, 1)

        return np.hypot(px - position * bx, py - position * by)

    # =========================== Methods to Build Analysis Tables =====================================================

    @staticmethod
    def build_sampling_frame(tables):
        """ One row per prescribed sampling location, with its coordinates """

        frame = tables["centroids"][["choice_name", "sample_status", "stratum_label", "geohash", "geometry"]]
        frame = frame.rename(columns={"choice_name": "plot_name", "stratum_label": "stratum"})

        # geometry is a text of the form "latitude longitude latitude accuracy"
        coordinates = frame["geometry"].str.split(expand=True).astype(float)
        frame = frame.assign(lat=coordinates[0], lon=coordinates[1]).drop(columns="geometry")

        return frame

    @staticmethod
    def build_plots(tables, frame):
        """ One row per registered plot, with the transect geometry and the prescribed location """

        plots = tables["registrations"][list(PLOT_COLUMNS)].rename(columns=PLOT_COLUMNS)
        plots["registered_at"] = pd.to_datetime(plots["registered_at"], utc=True)

        # Bring in the prescribed location of each plot
        prescribed = frame.rename(columns={"lat": "prescribed_lat", "lon": "prescribed_lon",
                                           "geohash": "prescribed_geohash"})
        plots = plots.merge(prescribed[["plot_name", "prescribed_lat", "prescribed_lon", "prescribed_geohash"]],
                            on="plot_name", how="left")

        # Transect geometry, in metres
        plots["transect_length_m"] = Loader.distance_m(plots["a_lat"], plots["a_lon"], plots["b_lat"], plots["b_lon"])
        plots["a_to_mid_m"] = Loader.distance_m(plots["a_lat"], plots["a_lon"], plots["mid_lat"], plots["mid_lon"])
        plots["mid_to_b_m"] = Loader.distance_m(plots["mid_lat"], plots["mid_lon"], plots["b_lat"], plots["b_lon"])
        plots["midpoint_offset_m"] = Loader.distance_m(plots["mid_lat"], plots["mid_lon"],
                                                       plots["prescribed_lat"], plots["prescribed_lon"])

        # Direction of the transect: 0 is north-south, 90 is east-west
        east, north = Loader.to_local_metres(plots["b_lat"], plots["b_lon"], plots["a_lat"], plots["a_lon"])
        plots["bearing_deg"] = np.degrees(np.arctan2(east, north)) % 180


        return plots

    @staticmethod
    def build_surveys(tables):
        """ One row per survey submission """

        surveys = tables["surveys"][list(SURVEY_COLUMNS)].rename(columns=SURVEY_COLUMNS)

        for column in ["start_time", "end_time", "submitted_at"]:
            surveys[column] = pd.to_datetime(surveys[column], utc=True)

        surveys["duration_min"] = (surveys["end_time"] - surveys["start_time"]).dt.total_seconds() / 60
        surveys["is_rejected"] = surveys["review_state"] == "rejected"

        return surveys

    @staticmethod
    def build_quadrats(tables, surveys, plots):
        """ One row per quadrat, with its survey, its plot and its distance to the registered transect """

        quadrats = tables["quadrats"][list(QUADRAT_COLUMNS)].rename(columns=QUADRAT_COLUMNS)

        quadrats = quadrats.merge(surveys[["survey_key", "plot_name", "is_rejected"]], on="survey_key", how="left")
        quadrats = quadrats.merge(plots[["plot_name", "a_lat", "a_lon", "b_lat", "b_lon"]], on="plot_name", how="left")

        quadrats["distance_to_transect_m"] = Loader.distance_to_segment_m(
            quadrats["lat"], quadrats["lon"],
            quadrats["a_lat"], quadrats["a_lon"], quadrats["b_lat"], quadrats["b_lon"])

        # The photo file name is the time it was taken, in milliseconds
        photo_ms = pd.to_numeric(quadrats["photo"].str.replace(".jpg", "", regex=False), errors="coerce")
        quadrats["photo_time"] = pd.to_datetime(photo_ms, unit="ms", utc=True)

        return quadrats

    @staticmethod
    def build_species_records(tables, quadrats):
        """ One row per species recorded in a quadrat, from the species list and from the additional entries """

        quadrat_info = quadrats[["quadrat_key", "survey_key", "plot_name", "quadrat_number", "is_rejected"]]

        # Species picked from the approved list: one id per species, separated by spaces
        listed = quadrats[["quadrat_key", "listed_species_ids"]].dropna()
        listed = listed.assign(species_id=listed["listed_species_ids"].str.split()).explode("species_id")
        names = tables["species"][["__id", "label"]].rename(columns={"__id": "species_id", "label": "species_name"})
        listed = listed.merge(names, on="species_id", how="left")
        listed = listed.assign(source="listed", typed_name=None,
                               record_key=listed["quadrat_key"] + "/" + listed["species_id"])

        # Additional species: unknowns and species missing from the list
        additional = tables["additional_species"].rename(columns={
            "PARENT_KEY": "quadrat_key", "KEY": "record_key",
            "validated_name": "species_name", "species_entry_mode": "source",
            "new_missing_canonical": "typed_name"})

        # The species_extra entity each additional entry points to, whether new or reused
        additional["species_id"] = (additional["target_extra_name"]
                                    .fillna(additional["select_reuse_unknown"])
                                    .fillna(additional["select_reuse_missing"]))

        columns = ["quadrat_key", "record_key", "species_id", "species_name", "typed_name", "source"]
        records = pd.concat([listed[columns], additional[columns]], ignore_index=True)
        records = quadrat_info.merge(records, on="quadrat_key", how="inner")

        # Derived columns for counting species; the recorded name itself is left untouched.
        # The id is the key for counting, because one species can appear under several names
        # (for example "Sida chrysantha" and "herb_063 (Sida chrysantha)" share one id)
        records["taxon"] = records["species_id"]
        records["is_unidentified"] = records["source"].isin(["new_unknown", "reuse_unknown"])

        return records

    @staticmethod
    def load(input_dir):
        """ Reads the raw tables and returns all analysis tables in a dictionary """

        tables = Loader.read_tables(input_dir)

        frame = Loader.build_sampling_frame(tables)
        plots = Loader.build_plots(tables, frame)
        surveys = Loader.build_surveys(tables)
        quadrats = Loader.build_quadrats(tables, surveys, plots)
        species_records = Loader.build_species_records(tables, quadrats)

        return {
            "frame": frame,
            "plots": plots,
            "surveys": surveys,
            "quadrats": quadrats,
            "species_records": species_records,
            "species_list": tables["species"],
        }
