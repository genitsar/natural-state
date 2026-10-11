import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.vegetation_src.load_data import Loader
from src.vegetation_src.quality_checks import QUADRAT_DISTANCE_MAX_M

# Number of random plot orders averaged for the species accumulation curve
ACCUMULATION_PERMUTATIONS = 200
RANDOM_SEED = 42

# Colours used in the figures
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
NEUTRAL = "#8a8983"
BLUE = "#2a78d6"
ORANGE = "#eb6834"


class Reporter:
    """ Includes functions to build the tables and figures of the data quality report """

    # =========================== Methods to Count Flags ===============================================================

    @staticmethod
    def count_flags(flags, by):
        """ Counts errors and warnings per plot or per survey """


        counted = flags[flags["severity"].isin(["error", "warning"])]
        counts = counted.groupby([by, "severity"]).size().unstack(fill_value=0)
        counts = counts.reindex(columns=["error", "warning"], fill_value=0)

        return counts.rename(columns={"error": "errors", "warning": "warnings"}).reset_index()

    # =========================== Methods to Summarise Surveys and Plots ===============================================

    @staticmethod
    def summarise_species(species_records, by):
        """ Counts species records, distinct species and the share that is unidentified, per group """

        summary = species_records.groupby(by).agg(
            species_records=("record_key", "size"),
            species_richness=("taxon", "nunique"),
            unidentified_pct=("is_unidentified", "mean"),
        )
        summary["unidentified_pct"] = (summary["unidentified_pct"] * 100).round(1)

        return summary.reset_index()

    @staticmethod
    def survey_summary(data, flags):
        """ One row per survey submission, rejected ones included """

        surveys = data["surveys"]
        quadrats = data["quadrats"]

        summary = surveys[["survey_key", "plot_name", "start_time", "recorder", "submitter",
                           "duration_min", "review_state"]].copy()
        summary["survey_date"] = summary["start_time"].dt.date
        summary["duration_min"] = summary["duration_min"].round().astype(int)
        summary["review_state"] = summary["review_state"].fillna("not reviewed")

        quadrat_counts = quadrats.groupby("survey_key").agg(
            quadrats=("quadrat_key", "size"),
            quadrats_with_herbs=("herbs_present", lambda values: (values == "yes").sum()),
        ).reset_index()

        summary = summary.merge(quadrat_counts, on="survey_key", how="left")
        summary = summary.merge(Reporter.summarise_species(data["species_records"], "survey_key"),
                                on="survey_key", how="left")
        summary = summary.merge(Reporter.count_flags(flags, "survey_key"), on="survey_key", how="left")
        summary[["errors", "warnings"]] = summary[["errors", "warnings"]].fillna(0).astype(int)

        columns = ["plot_name", "survey_date", "recorder", "submitter", "duration_min", "review_state",
                   "quadrats", "quadrats_with_herbs", "species_records", "species_richness",
                   "unidentified_pct", "errors", "warnings", "survey_key"]

        return summary.sort_values("start_time")[columns]

    @staticmethod
    def plot_summary(data, flags):
        """ One row per registered plot, using accepted surveys only """

        accepted_surveys = data["surveys"][~data["surveys"]["is_rejected"]]
        accepted_quadrats = data["quadrats"][~data["quadrats"]["is_rejected"]]
        accepted_records = data["species_records"][~data["species_records"]["is_rejected"]]

        summary = data["plots"][["plot_name", "sample_status", "stratum", "ecosystem_type", "is_viable",
                                 "transect_length_m", "midpoint_offset_m"]].copy()
        summary[["transect_length_m", "midpoint_offset_m"]] = summary[["transect_length_m",
                                                                       "midpoint_offset_m"]].round(1)

        survey_counts = accepted_surveys.groupby("plot_name").size().rename("accepted_surveys").reset_index()
        quadrat_counts = accepted_quadrats.groupby("plot_name").size().rename("quadrats").reset_index()

        # Mean number of species per quadrat, counting quadrats without herbs as zero
        per_quadrat = accepted_records.groupby("quadrat_key")["taxon"].nunique()
        accepted_quadrats = accepted_quadrats.assign(
            species_in_quadrat=accepted_quadrats["quadrat_key"].map(per_quadrat).fillna(0))
        mean_per_quadrat = (accepted_quadrats.groupby("plot_name")["species_in_quadrat"].mean().round(1)
                            .rename("mean_species_per_quadrat").reset_index())

        for table in [survey_counts, quadrat_counts,
                      Reporter.summarise_species(accepted_records, "plot_name"),
                      mean_per_quadrat, Reporter.count_flags(flags, "plot_name")]:
            summary = summary.merge(table, on="plot_name", how="left")

        count_columns = ["accepted_surveys", "quadrats", "species_records", "species_richness", "errors", "warnings"]
        summary[count_columns] = summary[count_columns].fillna(0).astype(int)

        return summary.sort_values("plot_name")

    # =========================== Methods to Assess Sampling Effort ====================================================

    @staticmethod
    def location_status(data):
        """ One row per prescribed location with how far it got: surveyed, not viable or not registered """

        plots = data["plots"]
        surveyed = data["surveys"].loc[~data["surveys"]["is_rejected"], "plot_name"]

        frame = data["frame"].copy()
        frame["registered"] = frame["plot_name"].isin(plots["plot_name"])
        frame["viable"] = frame["plot_name"].isin(plots.loc[plots["is_viable"] == "yes", "plot_name"])
        frame["surveyed"] = frame["plot_name"].isin(surveyed)

        frame["status"] = "Not registered"
        frame.loc[frame["registered"] & ~frame["viable"], "status"] = "Not viable"
        frame.loc[frame["registered"] & frame["viable"] & ~frame["surveyed"], "status"] = "Registered, not surveyed"
        frame.loc[frame["surveyed"], "status"] = "Surveyed"

        return frame

    @staticmethod
    def effort_by_stratum(data):
        """ Counts planned, registered, viable and surveyed locations per stratum and sample status """

        status = Reporter.location_status(data)

        effort = status.groupby(["stratum", "sample_status"]).agg(
            planned=("plot_name", "size"),
            registered=("registered", "sum"),
            viable=("viable", "sum"),
            surveyed=("surveyed", "sum"),
        ).reset_index()

        return effort

    @staticmethod
    def species_accumulation(species_records):
        """ Mean number of species found as plots are added one by one, over many random plot orders """

        # For each plot, the set of species found in it
        species_per_plot = species_records.dropna(subset=["taxon"]).groupby("plot_name")["taxon"].agg(set)
        plot_sets = list(species_per_plot)

        random = np.random.default_rng(RANDOM_SEED)
        curves = []
        for _ in range(ACCUMULATION_PERMUTATIONS):
            found = set()
            curve = []
            for index in random.permutation(len(plot_sets)):
                found = found | plot_sets[index]
                curve.append(len(found))
            curves.append(curve)

        curves = np.array(curves)

        return pd.DataFrame({
            "plots": np.arange(1, len(plot_sets) + 1),
            "mean_species": curves.mean(axis=0),
            "sd_species": curves.std(axis=0),
        })

    @staticmethod
    def richness_estimate(species_records):
        """ Observed species and the Chao2 estimate of how many are present, using plots as samples """

        records = species_records.dropna(subset=["taxon"])
        plots_per_species = records.drop_duplicates(["plot_name", "taxon"]).groupby("taxon").size()

        n_plots = records["plot_name"].nunique()
        observed = len(plots_per_species)
        in_one_plot = int((plots_per_species == 1).sum())
        in_two_plots = int((plots_per_species == 2).sum())

        # Chao2 (bias-corrected form): species seen in one or two plots tell us how many were missed
        chao2 = observed + ((n_plots - 1) / n_plots) * in_one_plot * (in_one_plot - 1) / (2 * (in_two_plots + 1))

        return {
            "plots": n_plots,
            "observed_species": observed,
            "species_in_one_plot": in_one_plot,
            "species_in_two_plots": in_two_plots,
            "chao2_estimate": round(chao2, 1),
            "completeness_pct": round(100 * observed / chao2, 1),
        }

    @staticmethod
    def sampling_effort(data):
        """ Accumulation curves and richness estimates, for all species and for identified species only """

        accepted = data["species_records"][~data["species_records"]["is_rejected"]]
        groups = {"All recorded species": accepted,
                  "Identified species only": accepted[~accepted["is_unidentified"]]}

        curves = pd.concat([Reporter.species_accumulation(records).assign(series=name)
                            for name, records in groups.items()], ignore_index=True)
        estimates = pd.DataFrame([{"series": name, **Reporter.richness_estimate(records)}
                                  for name, records in groups.items()])

        return curves, estimates

    # =========================== Methods to Draw Figures ==============================================================

    @staticmethod
    def style_axes(axes):
        """ Applies the common look: light surface, quiet grid, no box around the plot """

        axes.set_facecolor(SURFACE)
        axes.grid(color=GRID, linewidth=0.8)
        axes.set_axisbelow(True)
        axes.tick_params(colors=TEXT_SECONDARY, length=0, labelsize=9)
        for side in ["top", "right", "left", "bottom"]:
            axes.spines[side].set_visible(False)

    @staticmethod
    def draw_accumulation(curves, path):
        """ Draws the species accumulation curves and saves the figure """

        figure, axes = plt.subplots(figsize=(8, 4.8), facecolor=SURFACE)
        Reporter.style_axes(axes)

        colours = {"All recorded species": BLUE, "Identified species only": ORANGE}
        for name, curve in curves.groupby("series", sort=False):
            colour = colours[name]
            axes.fill_between(curve["plots"], curve["mean_species"] - curve["sd_species"],
                              curve["mean_species"] + curve["sd_species"], color=colour, alpha=0.15, linewidth=0)
            axes.plot(curve["plots"], curve["mean_species"], color=colour, linewidth=2, label=name)

            # Label the end of each line with its final value
            last = curve.iloc[-1]
            axes.annotate(f"{last['mean_species']:.0f}", (last["plots"], last["mean_species"]),
                          xytext=(6, 0), textcoords="offset points", va="center", color=TEXT, fontsize=10)

        axes.set_xlim(1, curves["plots"].max() + 1.5)
        axes.set_ylim(0, None)
        axes.set_xlabel("Number of plots surveyed", color=TEXT_SECONDARY, fontsize=10)
        axes.set_ylabel("Species found", color=TEXT_SECONDARY, fontsize=10)
        axes.set_title("Species are still being added with every new plot", loc="left", color=TEXT,
                       fontsize=12, fontweight="bold")
        axes.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=TEXT)

        figure.text(0.125, 0.01, f"Mean of {ACCUMULATION_PERMUTATIONS} random plot orders; "
                    "the band is one standard deviation. Accepted surveys only.",
                    color=TEXT_SECONDARY, fontsize=8)
        figure.tight_layout(rect=(0, 0.03, 1, 1))
        figure.savefig(path, dpi=150, facecolor=SURFACE)
        plt.close(figure)

    @staticmethod
    def draw_location_map(data, path):
        """ Draws all prescribed locations, marked by how far each one got, and saves the figure """

        status = Reporter.location_status(data)

        # Colour and filling show the status; the marker shape shows the stratum
        looks = {
            "Surveyed": {"color": BLUE, "filled": True},
            "Registered, not surveyed": {"color": ORANGE, "filled": True},
            "Not viable": {"color": TEXT, "filled": True},
            "Not registered": {"color": ORANGE, "filled": False},
        }
        shapes = {"savanna": "o", "shrubland": "^"}

        figure, axes = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
        Reporter.style_axes(axes)

        # Draw the groups in the order of the looks above, so the legend reads from surveyed to not registered
        status["status"] = pd.Categorical(status["status"], categories=list(looks), ordered=True)
        groups = status.groupby(["status", "sample_status", "stratum"], observed=True)

        for (state, sample, stratum), group in groups:
            look = looks[state]
            colour = NEUTRAL if (state == "Not registered" and sample == "backup") else look["color"]
            axes.scatter(group["lon"], group["lat"], s=70, marker=shapes.get(stratum, "s"),
                         facecolors=colour if look["filled"] else SURFACE, edgecolors=colour, linewidths=1.6,
                         label=f"{state}: {sample} {stratum} ({len(group)})", zorder=3)

        # Plot number next to each location
        for _, row in status.iterrows():
            axes.annotate(row["plot_name"].split("_")[-1], (row["lon"], row["lat"]), xytext=(6, 5),
                          textcoords="offset points", fontsize=7, color=TEXT_SECONDARY)

        # Keep distances true to scale at this latitude
        axes.set_aspect(1 / np.cos(np.radians(status["lat"].mean())))
        axes.set_xlabel("Longitude", color=TEXT_SECONDARY, fontsize=10)
        axes.set_ylabel("Latitude", color=TEXT_SECONDARY, fontsize=10)
        axes.set_title("Transect locations: what was planned and what was surveyed", loc="left", color=TEXT,
                       fontsize=12, fontweight="bold")
        axes.legend(frameon=False, fontsize=8, labelcolor=TEXT, loc="center left", bbox_to_anchor=(1.01, 0.5))

        figure.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
        plt.close(figure)

    @staticmethod
    def draw_transects(data, path, columns=6, window_m=45):
        """ Draws each surveyed transect with its quadrats, one small panel per plot, and saves the figure """

        quadrats = data["quadrats"][~data["quadrats"]["is_rejected"]]
        plots = data["plots"][data["plots"]["plot_name"].isin(quadrats["plot_name"])].sort_values("plot_name")

        rows = int(np.ceil(len(plots) / columns))
        figure, grid = plt.subplots(rows, columns, figsize=(columns * 2.1, rows * 2.25), facecolor=SURFACE)
        grid = np.atleast_1d(grid).ravel()

        for axes, (_, plot) in zip(grid, plots.iterrows()):
            # Metres east and north of the registered midpoint
            origin = (plot["mid_lat"], plot["mid_lon"])
            ax, ay = Loader.to_local_metres(plot["a_lat"], plot["a_lon"], *origin)
            bx, by = Loader.to_local_metres(plot["b_lat"], plot["b_lon"], *origin)
            own = quadrats[quadrats["plot_name"] == plot["plot_name"]]
            qx, qy = Loader.to_local_metres(own["lat"], own["lon"], *origin)
            far = (own["distance_to_transect_m"] > QUADRAT_DISTANCE_MAX_M).to_numpy()

            axes.plot([ax, 0, bx], [ay, 0, by], color=TEXT, linewidth=2, zorder=2)
            axes.scatter([0], [0], s=18, color=TEXT, zorder=3)
            axes.scatter(qx[~far], qy[~far], s=14, color=BLUE, edgecolors=SURFACE, linewidths=0.5, zorder=4)
            axes.scatter(qx[far], qy[far], s=22, marker="D", color=ORANGE, edgecolors=SURFACE,
                         linewidths=0.5, zorder=5)
            axes.text(ax, ay, " A", fontsize=7, color=TEXT_SECONDARY, va="bottom")
            axes.text(bx, by, " B", fontsize=7, color=TEXT_SECONDARY, va="bottom")

            axes.set_xlim(-window_m, window_m)
            axes.set_ylim(-window_m, window_m)
            axes.set_aspect("equal")
            axes.set_facecolor(SURFACE)
            axes.set_xticks([])
            axes.set_yticks([])
            for side in axes.spines.values():
                side.set_color(GRID)
            axes.set_title(f"Plot {plot['plot_name'].split('_')[-1]}: {plot['transect_length_m']:.0f} m, "
                           f"{int(far.sum())} far", fontsize=8, color=TEXT, loc="left")

        for axes in grid[len(plots):]:
            axes.set_visible(False)

        handles = [
            plt.Line2D([], [], color=TEXT, linewidth=2, label="Registered transect (A, midpoint, B)"),
            plt.Line2D([], [], marker="o", color=BLUE, linestyle="", markersize=5, label="Quadrat"),
            plt.Line2D([], [], marker="D", color=ORANGE, linestyle="", markersize=5,
                       label=f"Quadrat more than {QUADRAT_DISTANCE_MAX_M} m from the transect"),
        ]
        figure.legend(handles=handles, frameon=False, fontsize=9, labelcolor=TEXT, loc="lower center", ncol=3)
        figure.suptitle(f"Registered transects and recorded quadrat locations (each panel is {2 * window_m} m wide, "
                        "north is up)", x=0.01, ha="left", fontsize=12, fontweight="bold", color=TEXT)
        figure.tight_layout(rect=(0, 0.04, 1, 0.96))
        figure.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
        plt.close(figure)
