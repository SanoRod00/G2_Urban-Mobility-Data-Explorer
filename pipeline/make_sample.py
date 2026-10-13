import pandas as pd
trips = pd.read_parquet("data/processed/trips_normalized.parquet")
trips.sample(200000, random_state=1).to_parquet("data/processed/trips_sample.parquet")
print("sample saved")