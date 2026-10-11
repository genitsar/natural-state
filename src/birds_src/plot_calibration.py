import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed

import matplotlib.pyplot as plt
import numpy as np

from src.birds_src.calibrate import Calibrator, TARGET_PROBABILITY

# Confidence scores shown as tick labels on the logit axis
TICK_SCORES = [0.1, 0.3, 0.5, 0.7, 0.9, 0.99, 0.999]

# Colours used in the figure
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"
ORANGE = "#eb6834"

METHOD_NOTES = {
    "fitted": "Fitted curve",
    "accept_all": "No curve: too few wrong clips.\nAll predictions accepted.",
    "accept_none": "No curve: too few correct clips.\nNo predictions accepted.",
}


class CalibrationPlotter:
    """ Includes functions to draw the validated clips and the fitted calibration curve per species """

    # =========================== Methods to Draw Calibration ==========================================================

    @staticmethod
    def draw_species(axes, species_rows, species):
        """ Draws one species: its validated clips, and its fitted curve and threshold if it has one """

        logit_score = Calibrator.to_logit_scale(species_rows["confidence"])
        correct = species_rows["outcome"] == 1

        # Spread the points a little around 0 and 1 so that clips with similar scores stay visible
        random = np.random.default_rng(0)
        height = species_rows["outcome"] + random.uniform(-0.04, 0.04, len(species_rows))

        axes.scatter(logit_score[correct], height[correct], s=16, color=BLUE, alpha=0.6, linewidths=0,
                     label="Correct prediction")
        axes.scatter(logit_score[~correct], height[~correct], s=20, marker="D", color=ORANGE, alpha=0.7,
                     linewidths=0, label="Wrong prediction")

        if species["method"] == "fitted":
            # The fitted probability of a correct prediction across the whole score range
            grid = np.linspace(Calibrator.to_logit_scale(0.1), Calibrator.to_logit_scale(1.0), 200)
            probability = Calibrator.to_logistic_scale(species["intercept"] + species["slope"] * grid)
            axes.plot(grid, probability, color=TEXT, linewidth=2, label="Fitted probability")

            # The threshold: where the curve reaches the target probability
            threshold = Calibrator.to_logit_scale(species["threshold"])
            axes.axhline(TARGET_PROBABILITY, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
            axes.axvline(threshold, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
            axes.annotate(f"Threshold {species['threshold']:.3f}", (threshold, 0.5), xytext=(6, 0),
                          textcoords="offset points", color=TEXT, fontsize=9, va="center")
        else:
            axes.text(0.97, 0.5, METHOD_NOTES[species["method"]], transform=axes.transAxes, ha="right",
                      va="center", color=TEXT, fontsize=9)

        axes.set_title(f"{species['commonName']}: {species['true_class']} correct, "
                       f"{species['false_class']} wrong", loc="left", color=TEXT, fontsize=10, fontweight="bold")

        # Logit positions on the axis, labelled with the confidence scores they correspond to
        axes.set_xticks(Calibrator.to_logit_scale(np.array(TICK_SCORES)))
        axes.set_xticklabels([str(score) for score in TICK_SCORES])
        axes.set_xlim(Calibrator.to_logit_scale(0.08), Calibrator.to_logit_scale(1.0) + 0.3)
        axes.set_ylim(-0.1, 1.1)
        axes.set_yticks([0, 0.25, 0.5, 0.75, 1])

        axes.set_facecolor(SURFACE)
        axes.grid(color=GRID, linewidth=0.8)
        axes.set_axisbelow(True)
        axes.tick_params(colors=TEXT_SECONDARY, length=0, labelsize=8)
        for side in axes.spines.values():
            side.set_visible(False)

    @staticmethod
    def draw_calibration(validation, thresholds, path):
        """ Draws one panel per species and saves the figure """

        figure, grid = plt.subplots(2, 2, figsize=(11, 7), facecolor=SURFACE, sharey=True)

        for axes, (_, species) in zip(grid.ravel(), thresholds.iterrows()):
            species_rows = validation[validation["commonName"] == species["commonName"]]
            CalibrationPlotter.draw_species(axes, species_rows, species)

        for axes in grid[:, 0]:
            axes.set_ylabel("Probability the prediction is correct", color=TEXT_SECONDARY, fontsize=9)
        for axes in grid[-1, :]:
            axes.set_xlabel("BirdNET confidence score (logit scale)", color=TEXT_SECONDARY, fontsize=9)

        # One legend for the whole figure, taken from the panel that has all three elements
        fitted_panels = [axes for axes in grid.ravel() if len(axes.get_legend_handles_labels()[0]) == 3]
        handles, labels = (fitted_panels[0] if fitted_panels else grid.ravel()[0]).get_legend_handles_labels()
        figure.legend(handles, labels, frameon=False, fontsize=9, labelcolor=TEXT, loc="lower center", ncol=3)

        figure.suptitle("Validated clips and fitted calibration curve, by species", x=0.01, ha="left",
                        fontsize=12, fontweight="bold", color=TEXT)
        figure.tight_layout(rect=(0, 0.04, 1, 0.96))
        figure.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
        plt.close(figure)
