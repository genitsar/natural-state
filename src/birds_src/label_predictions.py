class Labeller:
    """ Includes functions to label predictions as observations using the species thresholds """

    # =========================== Methods to Label Predictions =========================================================

    @staticmethod
    def label_observations(predictions, thresholds):
        """ Adds the observation column: the species name if the clip is an observation, else empty """

        # Bring the method and the threshold of its species next to each prediction
        # (the species column is common_name in predictions and commonName in thresholds)
        merged = predictions.merge(
            thresholds[["commonName", "method", "threshold"]],
            left_on="common_name",
            right_on="commonName",
            how="left",
        )

        # A clip is an observation if its species accepts all predictions,
        # or if its species has a fitted threshold and the confidence reaches it
        accepted = merged["method"] == "accept_all"
        above_threshold = (merged["method"] == "fitted") & (merged["confidence"] >= merged["threshold"])
        is_observation = (accepted | above_threshold).to_numpy()

        # Keep the original columns unchanged and add the new one
        labelled = predictions.copy()
        labelled["observation"] = labelled["common_name"].where(is_observation)

        return labelled

    @staticmethod
    def count_observations(labelled):
        """ Counts predictions and observations per species """

        summary = (
            labelled.groupby("common_name")["observation"]
            .agg(predictions="size", observations="count")
            .reset_index()
        )

        return summary
