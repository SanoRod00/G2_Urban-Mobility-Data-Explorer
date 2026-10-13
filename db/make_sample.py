
import sys
from pathlib import Path
import numpy as np 
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LOOKUP = ROOT / "data/raw/taxi_zone_lookup.csv"
OUR = ROOT / "data/processed/trips_synthetic.parquet"
JFK = 132

def main(n=200_000):
    rng = np.random.default_rng(42)
    zones = pd.read_csv(LOOKUP)
    normal = zones[~zones["LocationID"].isin([264, 265, JFK])]
    manhattan = normal[normal["Borough"] == "Manhattan"]["LocationID"].to_numpy()
    all_ids = normal["LocationID"].to_numpy()
    weights = np.where(np.isin(all_ids, manhattan), 6.0, 1.0)
    weights /= weights.sum()

    pu = rng.choice(all_ids, n, p=weights)
    do = rng.choice(all_ids, n, p=weights)

    jfk = rng.random(n) < 0.03
    to_jfk = rng.random(n) <0.5
    m_zone = rng.choice(manhattan, n)
    pu = np.where(jfk, np.where(to_jfk,m_zone, JFK), pu)
    do = np.where(jfk, np.where(to_jfk, JFK, m_zone), do)
    flat = jfk & (rng.random(n) < 0.5)

    unk = (rng.random(n) <0.015) & ~jfk
    pu = np.where(unk & (rng.random(n) < 0.5), rng.choice([264, 265], n), pu)
    do = np.where(unk & (pu != 264) & (pu !=265), rng.choice([264, 265], n), do)
    unknown_flag = (np.isin(pu, [264, 265]) | np.isin(do, [264, 265])). astype(int)

    start = pd.Timestamp("2019-01-01")
    hour_w = np.array([2,1,1,1,1,2,4,7,8,6,5,5,5,5,5,6,7,8,8,7,6,5,4,3], float)
    hour_w /= hour_w.sum()
    day = rng.integers(0, 31, n)
    hour = rng.choice(24, n, p=hour_w)
    pickup = start + pd.to_timedelta(day, "D") + pd.to_timedelta(hour, "h") + pd.to_timedelta(rng.integers(0, 3600, n), "s")


    dur = np.clip(rng.lognormal(2.4, 0.6, n), 1.0, 300.0)
    dur = np.where(jfk, rng.uniform(25, 75, n), dur)
    speed = np.clip(rng.normal(12, 4, n), 3, 45)
    dist = np.round(speed * dur /60, 2)
    dist = np.where(jfk, np.round(rng.uniform(14, 20, n), 2), dist)
    same = (pu == do) & ~jfk
    dist = np.where(same & (rng.random(n) < 0.3), 0.0, dist)
    dropoff = pickup +pd.to_timedelta(np.round(dur * 60), "s")
    dur_min = np.round((dropoff - pickup).total_seconds().to_numpy() / 60.0, 2)

    pay = rng.choice([1, 2, 3, 4], n, p=[0.70, 0.28, 0.01, 0.01])
    fare = np.round(2.5 + 2.5 * dist + 0.4 * dur_min, 2)
    fare = np.where(flat, 52.0, fare)
    rate = np.where(flat, 2, 1)
    extra = rng.choice([0.0, 0.5, 1.0], n)
    mta = np.full(n, 0.5)
    tip = np.where(pay == 1, np.round(fare * rng.uniform(0, 0.25, n), 2), 0.0)
    tolls = np.where(jfk & (rng.random(n) < 0.6), 5.76, 0.0)
    imp = np.full(n, 0.3)
    total = np.round(fare + extra + mta + tip + tolls + imp, 2)

    ph = pd.Series(pickup).dt.hour.to_numpy()
    bucket = np.select([ph < 6, ph < 10, ph < 16, ph < 20], ["night", "morning_rush", "midday", "evening_rush"], "evening")
    with np.errstate(divide="ignore", invalid="ignore"):
        avg_speed = np.round(dist / (dur_min / 60), 2)
        rev_min = np.round((total - tolls) / dur_min, 4)
        fare_mile = np.where(dist > 0, np.round(fare / dist, 2), np.nan)
        tip_pct = np.where(pay == 1, np.round(tip /fare * 100, 2), np.nan)


    df = pd.DataFrame({
        "vendor_id": rng.choice([1, 2], n, p=[0.4, 0.6]), 
        "pickup_datetime": pickup.strftime("%Y-%m-%d %H:%M:%S"),
        "dropoff_datetime": dropoff.strftime("%Y-%m-%d %H:%M:%S"),
        "pickup_zone": pu.astype(int),
        "dropoff_zone": do.astype(int),
        "payment_type_id": pay, 
        "rate_codes_id": rate,
        "fare_amount": fare,
        "trip_duration": dur_min,
        "trip_distance": dist, 
        "passenger_count": rng.choice([1, 2, 3, 4, 5, 6], n, p=[.70, .14, .05, .03, .05, .03]),
        "tolls": tolls, 
        "extra":extra, 
        "mta_tax": mta, 
        "tip": tip,
        "improvement_surcharge": imp, 
        "congestion_surcharge": np.nan,
        "total_amount": total,
        "avg_speed_mph": avg_speed,
        "revenue_per_minute": rev_min,
        "fare_per_mile":fare_mile,
        "tip_percentage": tip_pct, 
        "pickup_hour": ph,
        "pickup_weekday": pickup.dayofweek.to_numpy() + 1, 
        "time_of_day": bucket,
        "unknown_zone_flag": unknown_flag,
    })

    df = df.sort_values("pickup_datetime", kind="stable").reset_index(drop=True)
    df.insert(0, "trip_id", np.arange(1, len(df) + 1))

    OUR.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUR, index=False)
    print(f"wrote {len(df):,} rows -> {OUR}")
    print("flat_fare trips:", int(flat.sum()), "| unknown-zone trips:", int(unknown_flag.sum()))

if __name__== "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200_000)    

    