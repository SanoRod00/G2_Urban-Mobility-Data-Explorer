
import sqlite3 
from pathlib import Path

ROOT = Path(__file__).resolve.parent.parent
JFK = 132

ZONE_WEEKDAY_HOUR = """
INSERT INTO agg_zone_weekday_hour (pickup_zone, weekday, hour, trip_count, total_revenue, total_minutes)
SELECT pickup_zone, pickup_weekday, pickup_hour,
       COUNT(*)
       SUM(total_amount - COALESCE(tolls, 0)),
       SUM(trip_duration)
FROM trips
GROUP BY pickup_zone, pickup_weekday, pickup_hour
"""

FLATFARE_HOURLY = """
INSERT INTO agg_flatfare_hourly (manhattan_zone, hour, dist_band, metered_trips, metered_fare_sum, metered_over_flat)
SELECT z.zone_id, t.pickup_hour, CAST(t.trip_distance AS INTEGER),
       COUNT(*), 
       SUM(t.fare_amount + COALESCE(t.extra, 0) + COALESCE(t.mta_tax, 0)),
       SUM(CASE WHEN t.fare_amount + COALESCE(t.extra, 0) + COALESCE(t.mta_tax, 0) > 52 THEN 1 ELSE 0 END)
FROM trips t 
JOIN zones z ON z.zone_id = CASE WHEN t.pickup_zone = ? THEN t.dropoff_zone ELSE t.pickup_zone END
WHERE t.rate_codes_id = 1
  AND (t.pickup_zone = ? OR t.dropoff_zone = ?)
  AND z.borough = 'Manhattan'
  AND t.trip_distance > 0
GROUP BY z.zone_id, t.pickup_hour, CAST(t.trip_distance AS INTEGER)
"""

def main():
    con = sqlite3.connect(ROOT / "data/processed/taxi.db")
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("DELETE FROM agg_zone_weekday_hour")
    con.execute(ZONE_WEEKDAY_HOUR)
    con.execute("DELETE FROM agg_flatfare_hourly")
    con.execute(FLATFARE_HOURLY, (JFK, JFK, JFK))
    con.commit()
    for t in ("agg_zone_weekday_hour", "agg_flatfare_hourly"):
        print(t, con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    con.close

if __name__== "__main__":
    main()
