
import sqlite3
import sys 
from pathlib import Path
import pandas as pd 


ROOT = Path(__file__). resolve().parent.parent
DB = ROOT / "data/processed/taxi.db"

INDEXES = {
    "idx_trips_pickup_datetime": ("trips", "pickup_datetime"), 
    "idx_trips_pickup_zone": ("trips", "pickup_zone"),
    "idx_trips_dropoff_zone": ("trips", "dropoff_zone"),
    "idx_trips_fare": ("trips", "fare_amount"), 
    "idx_trips_distance": ("trips", "trips_distance"),
    "idx_trips_zone_wd_hour": ("trips", "pickpu_zone, pickup_weekday, pickup_hour"), 
    "idx_trips_rate_pu_do": ("trips", "rate_codes_id, pickup_zone, dropoff_zone") 
}

def create_indexes(con):
    for name, (table, cols) in INDEXES.items():
        con.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")
    con.execute("ANALYZE")
    con.commit()

def drop_indexes(con):
    for name in INDEXES:
        con.execute(f"DROP INDEX IF EXISTS {name}")
    if _has_stats(con):
        con.execute("DELETE FROM sqlite_stat1")
    con.commit()


def _has_stats(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE  name='sqlite_stat1'").fetchone() is not None


def main():
    if not DB.exists():
        sys.exit(f"Database not found: {DB}. Run db/load_data.py first.")
    con = sqlite3.connect(DB)
    if "--drop" in sys.argv:
        drop_indexes(con)
        print("dropped", len(INDEXES), "indexes")

    else:
        create_indexes(con)
        print("created", len(INDEXES), "indexes")
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='trips' "
                                "AND name NOT LIKE 'sqlite_%'"):
        print(" -", name)
    con.close()


if __name__ == "__main__":
    main()