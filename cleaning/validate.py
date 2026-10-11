"""
cleaning/validate.py  -  Data integrity, exclusion log and derived features.

What this file does
1. Reads the normalized trips   (data/processed/trips_normalized.parquet).
2. Checks every row against the named rules in RULES (one pass, done by DuckDB).
3. Writes the exclusion log     (cleaning/exclusion_log.csv): one line for every dropped or flagged row, with the reason codes.
4. Writes the counts per rule   (cleaning/exclusion_summary.csv).
5. Writes the cleaned rows plus the derived features   (data/processed/trips_cleaned.parquet), which is the handoff to Orla.

Run from the project root:
    python -m cleaning.validate

Key ideas

A rule either DROPS a row (it is removed from the cleaned data) or FLAGS it
  (it stays, with a marker column).

   row can break several rules.  `all_reasons` lists every  (for example
  "R01|R03").  `primary_reason` is the FIRST rule in the RULES list that the row
  breaks, so the primary counts of the drop rules add up to the rows dropped.

  Rows are never edited. Every log line keeps the original trip_id, so each exclusion can be traced back to the exact raw row.

  DuckDB reads the parquet file directly, so the 7.6 million rows never have to
  fit in memory and no row is processed by hand.
  """

from pathlib import Path

import duckdb

# Paths (built from this file's location, so the script works from any folder)
ROOT = Path(__file__).resolve().parent.parent
# input from Sano's pipeline
SRC = ROOT / "data/processed/trips_normalized.parquet"
# output for Orla (not in git)
OUT = ROOT / "data/processed/trips_cleaned.parquet"
# every dropped or flagged row (not in git)
LOG = ROOT / "cleaning/exclusion_log.csv"
# counts per rule (in git)
SUMMARY = ROOT / "cleaning/exclusion_summary.csv"


# Thresholds.  Lock these before Orla loads the database: changing one later
# changes every row count downstream.

MONTH_START = "2019-01-01"      # first day included
# first day NOT included (so 1 Feb 00:00:00 is out of range)
MONTH_END = "2019-02-01"
MAX_SPEED_MPH = 80              # above any legal speed in or around New York City
# 12 hours; the 99.9th percentile of duration is about 24 hours
MAX_DURATION_MIN = 720
MAX_DISTANCE_MILES = 100        # the 99.9th percentile of distance is 26.3 miles
# roughly the fare of a metered 100-mile trip (R07 allows no more)
MAX_FARE_USD = 250
# "Unknown" and "Outside of NYC" in the zone lookup
UNKNOWN_ZONE_IDS = (264, 265)

# The raw data has no trip identifier of its own, so "the same trip" is defined
# by these columns (used by rule R08).

DUPLICATE_KEY = (
    "vendor_id", "pickup_datetime", "dropoff_datetime", "pickup_zone",
    "dropoff_zone", "distance", "fare", "total", "passengers",
)

# Zone IDs written as SQL text, for example "264, 265".

_unknown_zones = ", ".join(str(z) for z in UNKNOWN_ZONE_IDS)
#
# The rules.  Each rule is : (code, name, action, condition, justification)
#

# code short id used in the log and summery
# name readable naem
# action "drop" = remove the row, "flag"= keep it but mark it
#  condition SQL that is TRUE when the row BREAKS the rule (secs = trip duration in seconds, dup = copy number of a duplicate)

# Order matters: the primary reason of a row is the first rule in this list that it breaks. R10 therefore sits above R09, so a row that is both extremely priced and in an unknown zone is lebeled R10(dropped), not R09(only flagged).

#


RULES = [
    ("R00", "MISSING_VALUE", "drop",
     "pickup_datetime IS NULL OR dropoff_datetime IS NULL OR distance IS NULL "
     "OR fare IS NULL OR total IS NULL OR pickup_zone IS NULL OR dropoff_zone IS NULL",
     "Every feature and chart needs these fields."
     ),

    ("R01", "PICKUP_OUT_OF_RANGE", "drop",
     f"pickup_datetime < TIMESTAMP '{MONTH_START}' OR pickup_datetime >= TIMESTAMP '{MONTH_END}'",
     "The file is January 2019: dates such as 2001 or 2088 are meter or clock errors."
     ),

    ("R02", "NON_POSITIVE_DURATION", "drop",
     "secs <= 0",
     "A trip cannot end before it starts; duration feeds speed and revenue per minute."),

    ("R03", "NON_POSITIVE_FARE", "drop",
     "fare <= 0 OR total <= 0",
     "Not usable for fare economics (most are no-charge or disputed trips)."),

    ("R04", "ZERO_DIST_DIFF_ZONES", "drop",
     "distance = 0 AND pickup_zone <> dropoff_zone",
     "The meter says no movement while the zones differ, so the record contradicts itself."),

    ("R05", "IMPLAUSIBLE_SPEED", "drop",
        f"secs > 0 AND distance / (secs / 3600.0) > {MAX_SPEED_MPH}",
        "Faster than any legal speed in or around the city."),

    ("R06", "EXCESSIVE_DURATION", "drop",
     f"secs > {MAX_DURATION_MIN * 60}",
     "Probably a meter left running."),

    ("R07", "EXCESSIVE_DISTANCE", "drop",
     f"distance > {MAX_DISTANCE_MILES}",
     "Far beyond the 99.9th percentile, so a meter error."),

    ("R08", "DUPLICATE", "drop",
     "dup > 1",
     "Extra  copies would double count a trip; the first copy (lowest trip_id) is kept."),

    ("R10", "EXTREME_FARE", "drop",

     f"fare > {MAX_FARE_USD}",
     "Fares such as $623,259.86 for 2.4 miles passed every other rule; they are keying errors."),

    ("R09", "UNKNOWN_ZONE", "flag",
     f"pickup_zone IN ({_unknown_zones}) OR dropoff_zone IN ({_unknown_zones})",
     "Real trips with an unknown location: kept for city totals, left out of location views."),


]


def _col(code):
    """Name of the true/false column that holds one rule's result (R04 -> r04)."""
    return code.lower()


def _evaluate_rules(con, T):
    """Pass 1: check every row against every rule.

    Creates a temporary table 'w' with one row per trip:
    trip_id, one true/false column per rule (r00, r01, ...),

    Primary_reason, all_reasons and action ('drop', 'flag' or 'keep').

    """
    hit_columns = ", ".join(
        f"COALESCE(({cond}), FALSE) AS {_col(code)}" for code, _, _, cond, _ in RULES)

    primary_cases = " ".join(
        f"WHEN {_col(code)} THEN '{code}'" for code, *_ in RULES)

    all_cases = ", ".join(
        f"CASE WHEN {_col(code)} THEN '{code}' END" for code, *_ in RULES)

    any_drop = " OR ".join(_col(code)
                           for code, _, action, _, _ in RULES if action == "drop")

    con.execute(f"""
    CREATE TEMP TABLE w AS WITH base AS (
        -- the columns the rules need, plus trip duration and the duplicate counter
        SELECT trip_id, pickup_datetime, dropoff_datetime, distance, fare, total, pickup_zone, dropoff_zone,
        date_diff('second', pickup_datetime, dropoff_datetime) AS secs,
        -- 1 for the first copy of a trip, 2 for the second copy, and so on
              ROW_NUMBER() OVER (
                  PARTITION BY {", ".join(DUPLICATE_KEY)}
                  ORDER BY trip_id)  AS dup
    FROM {T}
    ),
    hits AS (
       -- one true/false column per rule
       SELECT trip_id, {hit_columns} FROM base
    )
    SELECT *,
           CASE {primary_cases} END AS primary_reason,
           NULLIF(concat_ws('|', {all_cases}), '') AS all_reasons,

           CASE WHEN {any_drop} THEN 'drop'
                WHEN r09 THEN 'flag'   --only the flag rule was broken: keep the row

    ELSE 'keep' END AS action

    FROM hits"""
    )


def _write_exclusion_log(con, T, log):
    """Pass 2a: one line for every dropped or flagged row, with the values that matter."""

    con.execute(f"""

    COPY (
        SELECT w.trip_id, w.action, w.primary_reason, w.all_reasons,
             t.pickup_datetime, t.dropoff_datetime, t.distance, t.fare, t.total,
             t.pickup_zone, t.dropoff_zone, t.payment_type, t.rate_code

        FROM w JOIN {T} t ON t.trip_id = w.trip_id
        WHERE  w.action <> 'keep'        -- good rows are not logged
        ORDER BY w.trip_id)
         TO '{log.as_posix()}'  (HEADER)""")


def _write_summary(con, summary):
    """Counts per rule. Prints the table and saves it for the reportc.

    triggered = rows that break the rule (a row can break several rules)
    primary_rows = rows whose FIRST broken rule is this one (each dropped row counted once)"""

    query = " UNION ALL ".join(
        f"SELECT '{code}' AS code, '{name}' AS rule, '{action}' AS action,"
        f"SUM({_col(code)}::INT) AS triggered, "
        f"COUNT(*) FILTER (WHERE primary_reason = '{code}') AS primary_rows FROM w"

        for code, name, action, _, *_ in RULES)
    con.execute(f"COPY ({query}) TO '{summary.as_posix()}' (HEADER)")

    print(con.sql(query).df().to_string(index=False))


def _write_clean_data(con, T, out):
    """Pass 2b: keep the rows that were not dropped and add the derived features."""
    con.execute(f"""
        COPY (
               
                 -- m = trip minutes, used below, not kept as is))
                 SELECT * EXCLUDE (m),
                 -- trip_duration_min: (dropoff - pickup) in minutes 
                 ROUND(m, 2) AS trip_duration_min,
                 -- avg_speed_mph: distance / duration in hours (NULL when distance is 0)
                 CASE WHEN distance > 0 THEN ROUND(distance / (m/ 60.0), 2) END AS avg_speed_mph,

                 -- revenue_per_minute: what the driver earns per minute; tolls go to the
                 -- bridge or tunnel, so they are removed. Never average this column:
                 -- divide summed revenue by summed minutes instead.
                 ROUND((total - COALESCE(tolls, 0)) / m, 4) AS revenue_per_minute,

                 -- fare_per_mile: fare / distance (NULL when distance is 0)
                 CASE WHEN distance > 0 THEN ROUND(fare / distance, 4) END AS fare_per_mile,

                -- tip_percentage: only card trips (payment_type = 1), because cash tips
                -- are recorded as 0
                CASE WHEN payment_type = 1 AND fare > 0
                    THEN ROUND(tip / fare * 100, 2 ) END AS tip_percentage,
                -- time columns for grouping
                   hour(pickup_datetime) AS pickup_hour,
                -- Monday = 1 ... Sunday = 7
                isodow(pickup_datetime) AS pickup_weekday,
                CASE WHEN hour(pickup_datetime) < 6  THEN 'night'
                     WHEN hour(pickup_datetime) < 10 THEN 'morning_rush'
                     WHEN hour(pickup_datetime) < 16 THEN 'midday'
                     WHEN hour(pickup_datetime) < 20 THEN 'evening_rush'
                     ELSE 'evening' END AS time_of_day_bucket

            FROM (
                SELECT t.*,
                       date_diff('second', t.pickup_datetime, t.dropoff_datetime) / 60.0 AS m,
                       -- TRUE for trips in zones 264 / 265
                       w.r09 AS unknown_zone_flag          
                FROM {T} t JOIN w ON t.trip_id = w.trip_id
                WHERE w.action <> 'drop'               
                
    )
            ORDER BY trip_id 
        ) TO '{out.as_posix()}' (FORMAT PARQUET)
    """)
                


def run(src=SRC, out=OUT, log=LOG, summary=SUMMARY):
    """Run the whole cleaning step and return the row counts per action."""

    src, out, log, summary = Path(src), Path(out), Path(log), Path(summary)

    if not src.exists():
        raise FileNotFoundError(f"Input not found: {src}. ")

# MAke sure the output folders exist.
    for path in (out, log, summary):
        path.parent.mkdir(parents=True, exist_ok=True)

    # DuckDB reads the parquet file directly
    T = f"read_parquet('{src.as_posix()}')"

    con = duckdb.connect()

    _evaluate_rules(con, T)

    _write_exclusion_log(con, T, log)

    _write_summary(con, summary)

    _write_clean_data(con, T, out)

    counts = dict(con.execute(
        "SELECT action, COUNT(*) FROM w GROUP BY action").fetchall())

    print(counts)
    con.close()
    return counts


if __name__ == "__main__":
    run()
