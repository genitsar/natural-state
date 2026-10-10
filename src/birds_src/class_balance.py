import pandas as pd

VALIDATION_PATH = "input_data/birds_input/validation_results.csv"
OUTPUT_PATH = "output_data/birds_output/class_balance.csv"


class Balancer:
    """ Includes functions to compute the class balance of the validation data """

    # =========================== Methods to Compute Class Balance =====================================================

    @staticmethod
    def compute_class_balance(validation):
        """ Counts validated, correct and wrong clips per species """

        # outcome is 1 for a correct prediction and 0 for a wrong one,
        # so its count is the number of clips and its sum the number correct
        summary = (
            validation.groupby("commonName")["outcome"]
            .agg(total="count", correct="sum")
            .assign(false_class=lambda t: t["total"] - t["correct"])
            .rename(columns={"correct": "true_class"})
            .reset_index()
        )

        return summary


