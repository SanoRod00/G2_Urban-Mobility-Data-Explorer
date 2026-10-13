"""Clean trips, log exclusions, add features. run python -m cleaning.validate"""

from pathlib import Path
import duckdb

ROOT =Path(__file__).resolve().parent.parent
SRC = ROOT / "data/processed/trips_normalized.parquet"
OUT = ROOT / "data/processed/trips_cleaned.parquet"
LOG = ROOT / "cleaning/exclusion_log.csv"
SUMMARY = ROOT / "cleaning/exclusion_summary.csv"

# code, name, action, condition(secs = trip seconds, dup = copy number)
RULES =[
    ("R00", "MISSING_VALUE", "drop", "pickup_datetime IS NULL OR dropoff_datetime IS NULL OR distance IS NULL OR fare IS NULL OR total IS NULL OR pickup_zone IS NULL OR dropoff_zone IS NULL"),
    ("R01", "PICKUP_OUT_OF_RANGE", "drop", "pickup_datetime < TIMESTAMP '2019-01-01' OR pickup_datetime >= TIMESTAMP '2019-02-01'"),
    ("R02", "NON_POSITIVE_DURATION", "drop", "secs <= 0"),
    ("R03", "NON_POSITIVE_FARE", "drop", "fare <= 0 OR total <= 0"),
    ("R04", "ZERO_DIST_DIFF_ZONES", "drop", "distance = 0 AND pickup_zone <> dropoff_zone"),
    ("R05", "IMPLAUSIBLE_SPEED", "drop", "secs > 0 AND distance / (secs / 3600.0) > 80"),
    ("R06", "EXCESSIVE_DURATION", "drop", "secs > 43200"),
    ("R07", "EXCESSIVE_DISTANCE", "drop", "distance > 100"),
    ("R08", "DUPLICATE", "drop", "dup > 1"),
    ("R10", "EXTREME_FARE", "drop", "fare > 250"),
    ("R09", "UNKNOWN_ZONE", "flag", "pickup_zone IN (264, 265) OR dropoff_zone IN (264, 265)"),
    
]
def run(src=SRC, out=OUT, log=LOG, summary=SUMMARY):
    src, out, log, summary = Path(src), Path(out), Path(log), Path(summary)
    for p in (out, log, summary):
        p.parent.mkdir(parents=True, exist_ok=True)
    T = f"read_parquet('{src.as_posix()}')"
    con = duckdb.connect()

    hits = ", ".join(f"COALESCE(({c}), FALSE) AS {k.lower()}" for k, _, _, c in RULES) 
    order = " ".join(f"WHEN {k.lower()} THEN '{k}'" for k, *_ in RULES)
    every = ", ".join(f"CASE WHEN {k.lower()} THEN '{k}' END" for k, *_ in RULES)
    any_drop = " OR ".join(k.lower() for k, _, a, _ in RULES if a == "drop")

    # One pass: which rules does each ro break?
    con.execute(f"""CREATE TEMP TABLE w AS
       WITH b AS (SELECT trip_id, pickup_datetime, dropoff_datetime, distance, fare, total,
       pickup_zone, dropoff_zone,
       date_diff('second', pickup_datetime, dropoff_datetime) AS secs,
       ROW_NUMBER() OVER (PARTITION BY vendor_id, pickup_datetime, dropoff_datetime, pickup_zone, dropoff_zone, distance, fare, total, passengers
                              ORDER BY trip_id) AS dup 
                   FROM {T}),
        h AS (SELECT trip_id, {hits} FROM b)
        SELECT *, CASE {order} END AS primary_reason,
               NULLIF(concat_ws('|', {every}), '') AS all_reasons,
               CASE WHEN {any_drop} THEN 'drop' WHEN r09 THEN 'flag' ELSE 'keep' END AS action
        FROM h""")

  # Exclusion log: every dropped or flagged row
    con.execute(f"""COPY (SELECT w.trip_id, w.action, w.primary_reason, w.all_reasons,
            t.pickup_datetime, t.dropoff_datetime, t.distance, t.fare, t.total,
            t.pickup_zone, t.dropoff_zone, t.payment_type, t.rate_code
        FROM w JOIN {T} t ON t.trip_id = w.trip_id WHERE w.action <> 'keep' ORDER BY w.trip_id
        ) TO '{log.as_posix()}' (HEADER)""")

    # Counts per rule
    q = " UNION ALL ".join(
        f"SELECT '{k}' AS code, '{n}' AS rule, '{a}' AS action, SUM({k.lower()}::INT) AS triggered, "

         f"COUNT(*) FILTER (WHERE primary_reason = '{k}') AS primary_rows FROM w" for k, n, a, _ in RULES)

    con.execute(f"COPY ({q}) TO '{summary.as_posix()}' (HEADER)")
    print(con.sql(q).df().to_string(index=False))

    # Clean rows +derived features
    con.execute(f"""COPY (SELECT * EXCLUDE (m), ROUND(m, 2) AS trip_duration_min,
     CASE WHEN distance > 0 THEN ROUND(distance / (m / 60.0), 2) END AS avg_speed_mph,
     ROUND((total - COALESCE(tolls, 0)) / m, 4) AS revenue_per_minute,
     CASE WHEN distance > 0 THEN ROUND(fare / distance, 4) END AS fare_per_mile,
     CASE WHEN payment_type = 1 AND fare > 0 THEN ROUND(tip / fare * 100, 2) END AS tip_percentage,

     hour(pickup_datetime) AS pickup_hour,
     isodow(pickup_datetime) AS pickup_weekday,
     CASE WHEN hour(pickup_datetime) < 6 THEN 'night'
          WHEN hour(pickup_datetime) < 10 THEN 'morning_rush'
          WHEN hour(pickup_datetime) < 16 THEN 'midday'
          WHEN hour(pickup_datetime) < 20 THEN 'evening_rush'
          ELSE 'evening' END AS time_of_day_bucket
    FROM (SELECT t.*, date_diff('second', t.pickup_datetime, t.dropoff_datetime) / 60.0 AS m,
           w.r09 AS unknown_zone_flag
         FROM {T} t JOIN w ON t.trip_id = w.trip_id WHERE w.action <> 'drop')
    ORDER BY trip_id) TO '{out.as_posix()}' (FORMAT PARQUET)""")

    counts = dict(con.execute("SELECT action, COUNT(*) FROM w GROUP BY action").fetchall())
    print(counts)
    return counts

if __name__ =="__main__":
    run()










