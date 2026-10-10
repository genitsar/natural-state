import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.birds_src.class_balance import Balancer

# Probability of a correct prediction required for a clip to count as an observation
TARGET_PROBABILITY = 0.99

# Minimum number of true and of false clips a species needs for a curve to be fitted
MIN_CLIPS_PER_CLASS = 10

# Scores are capped here before the logit transform, so that a score of 1 is not infinite
SCORE_CAP = 0.9999


class Calibrator:
    """ Includes functions to calibrate confidence scores and find the threshold per species """

    # =========================== Methods to Transform Scores ==========================================================

    @staticmethod
    def to_logit_scale(probability):
        """ Logit function that transforms back a logistic-scale probability score to the logit-scale """

        # Cap the probability scores between 0.0001 and 0.9999
        capped = np.clip(probability, 1 - SCORE_CAP, SCORE_CAP)

        # Transform back a probability score to the logit-scale where linear model was fit
        return np.log(capped / (1 - capped))

    @staticmethod
    def to_logistic_scale(score):
        """ Logistic/sigmoid function that transforms a score to logistic-scale (0-1) probability score """

        return 1 / (1 + np.exp(-score))

    # =========================== Methods to Calibrate One Species =====================================================

    @staticmethod
    def fit_calibration(validation_results_of_species):
        """ Fits a logistic regression of outcome on the logit score, returns intercept and slope """

        # Get the target (ornithologist ground truth)
        y = validation_results_of_species["outcome"]

        # Get the model predicted probability output
        X = validation_results_of_species["confidence"]

        # Convert probability to logit-scale to use as predictor data
        X = Calibrator.to_logit_scale(X)

        # Adds a column of 1s to the predictor data so that the model estimates also an intercept
        X = sm.add_constant(Calibrator.to_logit_scale(X))

        # Fit logistic regression model
        model = sm.GLM(y, X, family=sm.families.Binomial()).fit()

        # Return intercept and slope
        intercept, slope = model.params

        return intercept, slope

    @staticmethod
    def find_threshold(intercept, slope, target=TARGET_PROBABILITY):
        """ For the target ornithologist probability (0.99) of true class,
            compute the predictor model score and convert it to probability (logistic-scale) """

        # For the target probability compute the predictor model score
        # logit(target) = intercept + slope * logit_score, solved for logit_score
        logit_threshold = (np.log(target / (1 - target)) - intercept) / slope

        # Convert the predictor model score to probability (logistic-scale)
        return Calibrator.to_logistic_scale(logit_threshold)

    # =========================== Methods to Calibrate All Species =====================================================

    @staticmethod
    def calibrate(validation):
        """ Decides the method and the threshold for each species """

        balance = Balancer.compute_class_balance(validation)

        rows = []
        for _, species in balance.iterrows():
            name = species["commonName"]
            intercept, slope, threshold = np.nan, np.nan, np.nan

            if species["true_class"] < MIN_CLIPS_PER_CLASS:
                # Too few correct clips: predictions for this species cannot be trusted
                method = "accept_none"

            elif species["false_class"] < MIN_CLIPS_PER_CLASS:
                # Too few wrong clips to fit a curve: predictions are correct across all scores
                method = "accept_all"

            else:
                method = "fitted"
                species_rows = validation[validation["commonName"] == name]
                intercept, slope = Calibrator.fit_calibration(species_rows)
                threshold = Calibrator.find_threshold(intercept, slope)

            rows.append({
                "commonName": name,
                "total": species["total"],
                "true_class": species["true_class"],
                "false_class": species["false_class"],
                "method": method,
                "intercept": intercept,
                "slope": slope,
                "threshold": threshold,
            })

        return pd.DataFrame(rows)
