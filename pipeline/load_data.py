import pandas as pd
from normalize import normalize

trips = pd.read_csv("data/raw/yellow_tripdata_2019-01.csv")
zones = pd.read_csv("data/raw/taxi_zone_lookup.csv")

trips = normalize(trips)

known_zones = set(zones["LocationID"])
trips["pickup_zone_ok"] = trips["pickup_zone"].isin(known_zones)
trips["dropoff_zone_ok"] = trips["dropoff_zone"].isin(known_zones)

print("rows:", len(trips))
print("bad pickup zones:", (~trips["pickup_zone_ok"]).sum())
print("bad dropoff zones:", (~trips["dropoff_zone_ok"]).sum())
print("missing values per column:")
print(trips.isna().sum())

trips.to_parquet("data/processed/trips_normalized.parquet")
zones.to_csv("data/processed/zones.csv", index=False)
print("saved")
