import pandas as pd

from src.vegetation_src.load_data import Loader


INPUT_DIR = "../../../input_data/vegetation_input"

# -------- Testing class functionality --------


# Test function distance_m
# Expected: 0.001 degrees of latitude is about 110.5 m
print(round(Loader.distance_m(0.0, 37.0, 0.001, 37.0), 1))

# Test function distance_to_segment_m with a transect running 50 m north from A to B
# Expected: a point 10 m east of the middle is 10 m away,
#           a point 20 m north of B is 20 m away (measured to the endpoint, not to the endless line)
a_lat, a_lon = 0.0, 37.0
b_lat, b_lon = 50 / 110540, 37.0
points = pd.DataFrame({
    "lat": [25 / 110540, 70 / 110540],
    "lon": [37.0 + 10 / 111320, 37.0],
})
print(Loader.distance_to_segment_m(points["lat"], points["lon"], a_lat, a_lon, b_lat, b_lon).round(1).tolist())

# Read the real data and build all analysis tables
# Expected rows: frame 51, plots 31, surveys 32, quadrats 640, species_records 2243
data = Loader.load(INPUT_DIR)
for name, table in data.items():
    print(name, table.shape)

# One species can appear under several names, so species are counted by id, not by name
# Expected: 181 distinct names but 132 distinct ids in the accepted surveys
accepted = data["species_records"][~data["species_records"]["is_rejected"]]
print(accepted["species_name"].str.strip().nunique(), accepted["taxon"].nunique())
