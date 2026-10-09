import pandas as pd

new_names = {
    "VendorID": "vendor_id",
    "tpep_pickup_datetime": "pickup_datetime",
    "tpep_dropoff_datetime": "dropoff_datetime",
    "passenger_count": "passengers",
    "trip_distance": "distance",
    "RatecodeID": "rate_code",
    "store_and_fwd_flag": "store_and_forward",
    "PULocationID": "pickup_zone",
    "DOLocationID": "dropoff_zone",
    "payment_type": "payment_type",
    "fare_amount": "fare",
    "extra": "extra",
    "mta_tax": "mta_tax",
    "tip_amount": "tip",
    "tolls_amount": "tolls",
    "improvement_surcharge": "improvement_surcharge",
    "total_amount": "total",
    "congestion_surcharge": "congestion_surcharge",

}

number_columns = [
    "passengers",
    "fare",
    "extra",
    "mta_tax",
    "tip",
    "distance",
    "tolls",
    "improvement_surcharge",
    "total",
    "congestion_surcharge",]
id_columns = ["vendor_id", "rate_code", "payment_type", "pickup_zone", "dropoff_zone"]

def normalize(trips):
    trips = trips.rename(columns=new_names)
    trips = trips[[c for c in new_names.values() if c in trips.columns]]

    trips["pickup_datetime"] = pd.to_datetime(trips["pickup_datetime"], errors="coerce")
    trips["dropoff_datetime"] = pd.to_datetime(trips["dropoff_datetime"], errors="coerce")

    for col in number_columns:
        if col in trips.columns:
            trips[col] = pd.to_numeric(trips[col], errors="coerce")
    for col in id_columns:
     if col in trips.columns:
      trips[col] = pd.to_numeric(trips[col], errors="coerce").astype("Int16")

    if "store_and_forward" in trips.columns:
                trips["store_and_forward"] = trips["store_and_forward"].map({"Y": True, "N": False})

    trips["trip_id"] = range(len(trips))
    return trips