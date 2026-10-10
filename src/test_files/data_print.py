import pandas as pd

from src.data_print import Printer

# -------- Testing class functionality --------

tmp_dict = {
    "T1": ["A", "B", "C", "D", "E"],
    "T2": [20, 19, 15, 12, 19],
    "T3": [1, 3, 2, 3, 4]
}

tmp_df = pd.DataFrame(tmp_dict)

# Test function print_dataframe
Printer.print_dataframe(tmp_df)
Printer.print_dataframe(tmp_df, ["T1", "T3"])

