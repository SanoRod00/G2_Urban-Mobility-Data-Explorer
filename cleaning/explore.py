from pathlib import Path
import duckdb

con = duckdb.connect()
src = "data/processed/trips_normalized.parquet"


def show(title, sql):
    print(f"\n--- {title} ---")
    print(con.sql(sql).df().to_string(index=False))


show("total rows", f"SELECT COUNT(*) AS n FROM '{src}'")

show("null timestamps", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE pickup_datetime is NULL OR dropoff_datetime is NULL"""
     )

show("pickup outside Jan 2019", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE pickup_datetime < '2019-01-01'
       OR pickup_datetime >= '2019-02-01'""")

show("dropoff <= pickup", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE dropoff_datetime <= pickup_datetime""")

show("fare or total <= 0", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE fare <= 0 OR total <= 0""")

show("zero distance, different zones", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE distance = 0 AND pickup_zone <> dropoff_zone""")

show("speed above 80 mph", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE dropoff_datetime > pickup_datetime
      AND distance / (date_diff('second', pickup_datetime, dropoff_datetime) /3600.0) > 80""")

show("duration over 12 hours", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE date_DIFF('minute', pickup_datetime, dropoff_datetime) > 720""")


show("distance above 100 miles", f"SELECT COUNT(*) AS n FROM '{src}' WHERE distance > 100")

show("rows failing at least one rule", f"""
    SELECT COUNT(*) AS n FROM '{src}'
    WHERE pickup_datetime < '2019-01-01' OR pickup_datetime >= '2019-02-01'
    OR dropoff_datetime <= pickup_datetime
    OR fare <= 0 OR total <= 0
    OR (distance =0 and pickup_zone <> dropoff_zone)
    OR distance >100
    OR date_diff('minute', pickup_datetime, dropoff_datetime) > 720
    OR (dropoff_datetime > pickup_datetime AND
        distance / (date_diff('second', pickup_datetime, dropoff_datetime) / 3600.0) > 80)""")

show("out-of-range pickups: earliest and latest", f"""
    SELECT MIN(pickup_datetime) AS first, MAX(pickup_datetime) AS last
    FROM '{src}'
    WHERE pickup_datetime < '2019-01-01' OR  pickup_datetime >= '2019-02-01'""")

show("fare or total <= 0, by payment type", f"""
    SELECT payment_type, COUNT(*) AS n FROM '{src}'
    WHERE fare <= 0 OR total <= 0
    GROUP BY payment_type ORDER BY n DESC""")

show("distribution of valid trips", f"""
    SELECT quantile_cont(distance, 0.5)    AS dist_p50,
           quantile_cont(distance, 0.99)   AS dist_p99,
           quantile_cont(distance, 0.999)  AS dist_p999,
           quantile_cont(fare, 0.5)        AS fare_p50,
           quantile_cont(fare, 0.99)       AS fare_p99,
           quantile_cont(fare, 0.999)      As fare_p999
    FROM '{src}' WHERE distance > 0 AND fare > 0""")

show("duration percentiles in minutes (positive durations)", f"""
    SELECT quantile_cont(m, 0.5)    AS p50,
           quantile_cont(m, 0.99)   AS p99,
           quantile_cont(m, 0.999)  AS p999
    FROM (SELECT date_diff('minute', pickup_datetime, dropoff_datetime) AS m
          FROM '{src}' WHERE dropoff_datetime > pickup_datetime)""")

show("zones 264 /265", f"""
    SELECT 'pickup' AS side, pickup_zone AS zone, COUNT(*) AS n FROM '{src}'
    WHERE pickup_zone IN (264, 265) GROUP BY pickup_zone
    UNION ALL 
    SELECT 'dropoff', dropoff_zone, COUNT(*) FROM '{src}'
    WHERE dropoff_zone IN (264, 265) GROUP BY dropoff_zone""")

show("duplicate rows (extra copies)", f"""
     SELECT  SUM(c - 1) AS extra_copies FROM (
         SELECT COUNT(*) AS c FROM '{src}'
         GROUP BY vendor_id, pickup_datetime, dropoff_datetime,
                  pickup_zone, dropoff_zone, distance, fare, total, passengers
         HAVING COUNT(*) > 1)""")