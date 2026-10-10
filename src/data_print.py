class Printer:
    """ Includes functions to print data """

    # =========================== Methods to Print Dataframes Data =====================================================

    @staticmethod
    def print_dataframe(df, columns=None):
        """ Prints df dataframe details """

        # If dataframe is empty object
        if df is None:
            print("Dataframe is empty!")
            return

        # If selected columns are defined
        df = df[columns] if columns is not None else df

        # Print dataframe details
        print("\nColumns:", list(df.columns))
        print("\nColumns Types:\n" + str(df.dtypes))
        print("\nShape:", df.shape)
        # print("\nFirst 5 rows:\n", df.head())
        print("\nAll data:\n", str(df))
        


