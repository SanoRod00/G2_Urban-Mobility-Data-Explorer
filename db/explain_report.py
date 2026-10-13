import sqlite3 
import sys 
import time 
from pathlib import Path 

from create_indexes import DB, create_indexes, drop_indexes 

OUT = Path (__file__).resolve().parent / "explain_report.md"
RUNS = 5 

QUERIES = {
    "Trips in one day (pickup time)": ("SELECT COUNT(*) FROM trips WHERE pickup_datetime >= ? AND pickup_datetime < ?",
                                        ("2019-01-15 00:00:00", "2019-01-16 00:00:00")),
    "Trips from one pickup zone": ("SELECT COUNT(*), AVG(fare_amount) FROM trips WHERE pickup_zone = ?", (236,)),
    "Fare range filter": ("SELECT COUNT(*) FROM trips WHERE fare_amount BETWEEN ? AND ?", (50, 60)), 
    "Distance range filter": ("SELECT COUNT(*) FROM trips WHERE trip_distance BETWEEN ? AND ?", (1, 4)), 
    "Best Spot: zone + weekday + hour": ("SELECT pickup_zone, SUM(total_amount - tolls), SUM(trip_duration), COUNT(*)" 
                                         "FROM trips WHERE pickup_weekday = ? AND pickup_hour = ? GROUP By pickup_zone", (2, 8)), 
    "Flat fare: JFK metered trips":("SELECT pickup_hour, COUNT(*), AVG(fare_amount) FROM trips " 
                                    "WHERE rate_codes_id = 1 AND pickup_zone = ? GROUP BY pickup_hour", (132,)), 

}

def plan(con, sql, params):
    rows = con.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return [r[3] for r in rows]

def timed(con, sql, params):
    best = float("inf")
    for _ in range(RUNS):
        t = time.perf_counter()
        con.execute(sql, params). fetchall()
        best = min(best, time.perf_counter() - t)
    return best * 1000

def measure(con):
    return {name: (plan(con, sql, p), timed(con, sql, p))
            for name, (sql, p) in QUERIES.items()}

def main():
    if not DB.exists():
        sys.exit(f"Database not found: {DB}. Run db/load_data.py first.")
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]

    drop_indexes(con)
    before = measure(con)
    create_indexes(con)
    after = measure(con)
    con.close()

    md = [f"# EXPLAIN QUERY PLAN: before vs after indexes\n", f"Database: `{DB.name}`, {rows:,} trips. Timing =best of {RUNS} runs.\n",
           "| Query | Before (ms) | After (ms) | Speed-up | Plan after |", "|---|---:|---:|---:|---|"]
    for name in QUERIES:
        b, a = before[name][1], after[name][1]
        used = "index" if any("USING" in d and "INDEX"  in d for d in after[name][0]) else "full scan"
        md.append(f"| {name} | {b:.1f} | {a:.1f} | {b / a:.1f}x | {used} |")
    md.append("\n## Full plans\n")
    for name in QUERIES:
        md.append(f"### {name}\n```sql\n{QUERIES[name][0]}\n```")
        md.append("Before:\n```\n" + "\n".join(before[name][0]) + "\n```")
        md.append("After:\n```\n" + "\n".join(after[name][0]) + "\n```\n")
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {OUT}")
    print("\n".join(md[:4 + len(QUERIES)]))


if __name__ == "__main__":
    main() 
