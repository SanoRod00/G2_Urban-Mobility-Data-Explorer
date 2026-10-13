
import sqlite3
import sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pd 


ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data/processed/taxi.db"
SCHEMA = ROOT / "db/schema.sql"
CLEANED = ROOT /"data/processed/trips_cleaned.parquet"

def connect():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con

def create_schema(con):
    con.executescript(SCHEMA.read_text())

def load_lookup(con, table, column, rows):
    marks = ", ".join("?" for _ in column)
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(column)}) VALUES ({marks})"
    con.executemany(sql, rows)

def load_zones(con):    

    df = pd.read_csv(ROOT / "data/raw/taxi_zone_lookup.csv")

    df = df.rename(columns={
        "LocationID": "zone_id",
        "Zone": "zone_name",
        "Borough": "borough",
    })

    df["longitude"] = None
    df["latitude"] = None

    df = df[["zone_id", "zone_name","borough", "service_zone", "longitude", "latitude"]]

    df = df.astype(object).where(df.notna(), None)

    rows = list(df.itertuples(index=False, name=None))

    con.executemany(
        "INSERT OR IGNORE INTO zones (zone_id, zone_name, borough, service_zone, longitude, latitude) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )

TRIP_COLUMNS = [
    "trip_id", "vendor_id", "pickup_datetime", "dropoff_datetime", "pickup_zone", "dropoff_zone", "payment_type_id", "rate_codes_id", "fare_amount", "trip_duration", "trip_distance", "passenger_count", "tolls", "extra", "mta_tax", "tip", "improvement_surcharge", "congestion_surcharge", "total_amount", "avg_speed_mph", "revenue_per_minute", "fare_per_mile", "tip_percentage",
    "pickup_hour", "pickup_weekday", "time_of_day", "unknown_zone_flag",
]

RENAME = {
    "passengers": "passenger_count",
    "distance": "trip_distance",
    "fare": "fare_amount",
    "total": "total_amount",
    "trip_duration_min": "trip_duration",
    "time_of_day_bucket": "time_of_day",
    "payment_type": "payment_type_id",
}
def load_trips(con, path=CLEANED, batch_size=50_000):
   pf = pd.ParquetFile(path)
   source = {RENAME.get(n, n): n for n in pf.schema_arrow.names}
   missing = set(TRIP_COLUMNS) - set(pf.schema_arrow.names)
   if missing:
       raise ValueError(f"{Path(path).name} is missing columns required by the trips table: {sorted(missing)}")
   expected = pf.metadata.num_rows
   sql = f"INSERT INTO trips ({', '.join(TRIP_COLUMNS)}) VALUES ({', '.join('?' for _ in TRIP_COLUMNS)})"
   try:
       con.execute("DELETE FROM trips")
       done = 0
       for batch in pf.iter_batches(batch_size=batch_size, columns=TRIP_COLUMNS):
           df = batch.to_pandas()
           for col in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
               df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
           df = df.astype(object).where(df.notna(), None)
           con.executemany(sql, df.itertuples(index=False, name=None))
           done += len(df)
           print(f" trips:{done:,} / {expected:,}", end="\r") 
       print()
       loaded = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
       if loaded != expected:
        raise RuntimeError(f"row count mismatch: parquet {expected:,} vs table {loaded:,}")
       con.commit()
   except Exception:
       con.rollback()
       raise 
   return loaded
    

def main():

    DB.parent.mkdir(parents=True, exist_ok=True)
    con = connect()
    create_schema(con)
    load_zones(con)
    load_lookup(con, "payment_type", ["payment_type_id", "description"], 
                [(1, "Credit card"), (2, "Cash"), (3, "No charge"), (4, "Dispute")])
    load_lookup(con, "rate_codes", ["rate_codes_id", "description"], 
                [(1, "Standard rate"), (2, "JFK"), (3, "Newark"), (4, "Nassau or Westchester"), (5, "Negotiated fare"), (6, "Group ride")])
    load_lookup(con, "vendors", ["vendor_id", "vendor_name", "description"], [(1, "CMT", "Creative Mobile Technologies"), (2, "VeriFone", "VeriFone")])
    
    con.commit()
    for t in ("zones", "payment_type", "rate_codes", "vendors"):
        print(t, con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    con.close()

if __name__ == "__main__":
    main()    
