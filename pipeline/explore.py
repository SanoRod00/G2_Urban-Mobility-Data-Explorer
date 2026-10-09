import pandas as pd

trips = pd.read_parquet("data/processed/trips_normalized.parquet")

print(trips["congestion_surcharge"].value_counts(dropna=False))

trips["day"] = trips["pickup_datetime"].dt.day
print(trips.groupby("day")["congestion_surcharge"].apply(lambda x: x.notna().mean()).round(2))

print(trips["pickup_datetime"].min(), trips["pickup_datetime"].max())

outside = trips[(trips["pickup_datetime"] < "2019-01-01") | (trips["pickup_datetime"] > "2019-02-01")]
print("trips outside January 2019:", len(outside))

print(outside["pickup_datetime"].dt.year.value_counts())
print(outside["pickup_datetime"].sort_values().head(10))
print(outside["pickup_datetime"].sort_values().tail(10))

print(outside[outside["pickup_datetime"].dt.year == 2018]["pickup_datetime"].agg(["min", "max"]))

old = outside[outside["pickup_datetime"].dt.year == 2018]
print(old["pickup_datetime"].dt.date.value_counts().head(5))
print(old["dropoff_datetime"].agg(["min", "max"]))
print("dropoff in Jan 2019", (old["dropoff_datetime"] >= "2019-01-01").sum(), "of", len(old))
