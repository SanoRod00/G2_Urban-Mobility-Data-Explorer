"""Run python -m cleaning.test_validate"""
import tempfile
from pathlib import Path
import duckdb
import pandas as pd
from cleaning.validate import run

COLS = ["trip_id", "vendor_id", "pickup_datetime", "dropoff_datetime", "passengers", "distance",
        "rate_code", "pickup_zone", "dropoff_zone", "payment_type", "fare", "tip", "tolls", "total"]

def t(i, pu="2019-01-10 10:00:00", do="2019-01-10 10:10:00", dist=1.0, fare=8.0, zones=(100, 200)):
    return [i, 1, pu, do, 1, dist, 1, *zones, 1, fare, 0.0, 0.0, fare + 1]

def test_all():
    good = ("2019-01-08 08:00:00", "2019-01-08 08:10:00", 2.0, 10.0)   # a Tuesday, 8 am
    rows = [t(0, *good), t(1, pu="2001-01-01 10:00:00", do="2001-01-01 10:10:00"),
            t(2, do="2019-01-10 09:50:00"), t(3, fare=-5.0), t(4, dist=0.0), t(5, dist=50.0),
            t(6, do="2019-01-10 23:00:00"), t(7, do="2019-01-10 13:00:00", dist=150.0),
            t(8, *good), t(9, zones=(264, 200)), t(10, dist=None)]
    df = pd.DataFrame(rows, columns=COLS)
    df["pickup_datetime"] = pd.to_datetime(df["pickup_datetime"])
    df["dropoff_datetime"] = pd.to_datetime(df["dropoff_datetime"])
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        df.to_parquet(d/ "in.parquet")
        counts = run(d /"in.parquet", d / "out.parquet", d / "log.csv", d / "ssum.csv")
        log = dict(duckdb.sql(f"SELECT trip_id, primary_reason FROM read_csv_auto('{(d / 'log.csv').as_posix()}')").fetchall())
        kept =  duckdb.sql(f"SELECT * FROM read_parquet('{(d / 'out.parquet').as_posix()}') ORDER BY trip_id").fetchall()
        names = [c[0] for c in duckdb.sql(f"SELECT * FROM read_parquet('{(d / 'out.parquet').as_posix()}')").description]
    want = {1: "R01", 2: "R02", 3: "R03", 4: "R04", 5: "R05", 6: "R06", 7: "R07", 8: "R08", 9: "R09", 10: "R00"}
    assert log == want, log
    assert counts == {"drop": 9, "flag": 1, "keep": 1}, counts
    assert [r[names.index("trip_id")] for r in kept] == [0, 9]
    r = dict(zip(names, kept[0]))
    assert r["avg_speed_mph"] == 12.0 and r["fare_per_mile"] == 5.0
    assert r["pickup_hour"] == 8 and r["pickup_weekday"] == 2 and r["time_of_day_bucket"] == "morning_rush"
    assert dict(zip(names,kept[1]))["unknown_zone_flag"] is True



if __name__ =="__main__":
    test_all()
    print("All tests passed")