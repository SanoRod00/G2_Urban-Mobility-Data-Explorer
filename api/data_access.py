"""Shared DuckDB access to the cleaned trip Parquet dataset."""

from __future__ import annotations

import os
import math
from datetime import date, datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRIPS_PATH = ROOT / "data" / "processed" / "trips_cleaned.parquet"
NORMALIZED_TRIPS_PATH = ROOT / "data" / "processed" / "trips_normalized.parquet"


class DataUnavailable(Exception):
    """Raised when the configured trip dataset is not available."""


class QueryError(ValueError):
    """Raised when an API query parameter is invalid."""


class QueryResult:
    """Small materialized query result detached from its DuckDB connection."""

    def __init__(self, description, rows):
        self.description = description
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _records(cursor):
    names = [column[0] for column in cursor.description]
    return [
        {name: _json_value(value) for name, value in zip(names, row)}
        for row in cursor.fetchall()
    ]


def _as_int(args, name, default=None, minimum=None, maximum=None):
    raw = args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise QueryError(f"{name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise QueryError(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise QueryError(f"{name} must be at most {maximum}")
    return value


def _as_float(args, name, default=None, minimum=None):
    raw = args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise QueryError(f"{name} must be numeric") from exc
    if not math.isfinite(value):
        raise QueryError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise QueryError(f"{name} must be at least {minimum}")
    return value


def _date_value(args, name):
    raw = args.get(name)
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise QueryError(f"{name} must use YYYY-MM-DD format") from exc


def _filters(args, *, pickup_zone=True, dropoff_zone=True):
    clauses, params = [], []
    date_from = _date_value(args, "date_from")
    date_to = _date_value(args, "date_to")
    if date_from and date_to and date_from > date_to:
        raise QueryError("date_from must be on or before date_to")
    if date_from:
        clauses.append("pickup_datetime >= ?")
        params.append(datetime.combine(date_from, datetime.min.time()))
    if date_to:
        clauses.append("pickup_datetime < ? + INTERVAL 1 DAY")
        params.append(datetime.combine(date_to, datetime.min.time()))

    if pickup_zone:
        value = _as_int(args, "pickup_zone", minimum=1)
        if value is not None:
            clauses.append("pickup_zone = ?")
            params.append(value)
    if dropoff_zone:
        value = _as_int(args, "dropoff_zone", minimum=1)
        if value is not None:
            clauses.append("dropoff_zone = ?")
            params.append(value)

    for name, column in (("fare_min", "fare"), ("fare_max", "fare"),
                         ("distance_min", "distance"), ("distance_max", "distance")):
        value = _as_float(args, name, minimum=0)
        if value is not None:
            operator = ">=" if name.endswith("_min") else "<="
            clauses.append(f"{column} {operator} ?")
            params.append(value)
    if args.get("fare_min") and args.get("fare_max"):
        if float(args["fare_min"]) > float(args["fare_max"]):
            raise QueryError("fare_min must be no greater than fare_max")
    if args.get("distance_min") and args.get("distance_max"):
        if float(args["distance_min"]) > float(args["distance_max"]):
            raise QueryError("distance_min must be no greater than distance_max")

    payment_type = _as_int(args, "payment_type", minimum=1, maximum=6)
    if payment_type is not None:
        clauses.append("payment_type = ?")
        params.append(payment_type)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


class TripData:
    """Runs bounded, parameterized analytical queries over Parquet."""

    def __init__(self, trips_path=None, normalized_path=None):
        self.trips_path = Path(trips_path or os.getenv("TRIPS_PARQUET", DEFAULT_TRIPS_PATH))
        self.normalized_path = Path(normalized_path or NORMALIZED_TRIPS_PATH)

    def _run(self, sql, params=(), *, normalized=False):
        path = self.normalized_path if normalized else self.trips_path
        if not path.is_file():
            raise DataUnavailable(
                f"Trip data is unavailable at {path}. Run the cleaning pipeline first."
            )
        # The file path is server configuration, never a request parameter.
        parquet = path.resolve().as_posix().replace("'", "''")
        sql = sql.replace("__TRIPS__", f"read_parquet('{parquet}')")
        # A fresh connection per query avoids sharing DuckDB's global connection
        # between Flask request threads. Keep internal query parallelism bounded.
        with duckdb.connect(":memory:", config={"threads": "2"}) as con:
            cursor = con.execute(sql, list(params))
            return QueryResult(cursor.description, cursor.fetchall())

    def hourly(self, args):
        where, params = _filters(args)
        weekday = _as_int(args, "weekday", minimum=1, maximum=7)
        if weekday is not None:
            where += (" AND " if where else " WHERE ") + "pickup_weekday = ?"
            params.append(weekday)
        hour_rows = self._run(
            "SELECT pickup_hour AS hour, COUNT(*) AS trips, "
            "AVG(fare) AS average_fare, AVG(trip_duration_min) AS average_duration_minutes "
            "FROM __TRIPS__" + where + " GROUP BY pickup_hour ORDER BY pickup_hour",
            params,
        ).fetchall()
        by_hour = {int(row[0]): row for row in hour_rows}
        results = []
        for hour in range(24):
            row = by_hour.get(hour)
            results.append({
                "hour": hour,
                "trips": int(row[1]) if row else 0,
                "average_fare": round(float(row[2]), 2) if row and row[2] is not None else None,
                "average_duration_minutes": round(float(row[3]), 2) if row and row[3] is not None else None,
            })
        return results

    def by_zone(self, args):
        zone_type = args.get("zone_type", "pickup")
        if zone_type not in {"pickup", "dropoff"}:
            raise QueryError("zone_type must be pickup or dropoff")
        where, params = _filters(args)
        weekday = _as_int(args, "weekday", minimum=1, maximum=7)
        if weekday is not None:
            where += (" AND " if where else " WHERE ") + "pickup_weekday = ?"
            params.append(weekday)
        hour = _as_int(args, "hour", minimum=0, maximum=23)
        if hour is not None:
            where += (" AND " if where else " WHERE ") + "pickup_hour = ?"
            params.append(hour)
        sort_columns = {
            "trips": "trips", "average_fare": "average_fare",
            "average_distance": "average_distance", "zone_id": "zone_id",
        }
        sort_by = args.get("sort_by", "trips")
        if sort_by not in sort_columns:
            raise QueryError("sort_by must be trips, average_fare, average_distance, or zone_id")
        order = args.get("order", "desc").lower()
        if order not in {"asc", "desc"}:
            raise QueryError("order must be asc or desc")
        limit = _as_int(args, "limit", default=265, minimum=1, maximum=265)
        zone_column = "pickup_zone" if zone_type == "pickup" else "dropoff_zone"
        return self._run(
            f"SELECT {zone_column} AS zone_id, COUNT(*) AS trips, "
            "AVG(fare) AS average_fare, AVG(distance) AS average_distance "
            f"FROM __TRIPS__{where} GROUP BY {zone_column} "
            f"ORDER BY {sort_columns[sort_by]} {order.upper()}, zone_id ASC LIMIT ?",
            [*params, limit],
        ).fetchall()

    def trips(self, args):
        where, params = _filters(args)
        page = _as_int(args, "page", default=1, minimum=1)
        page_size = _as_int(args, "per_page", default=50, minimum=1, maximum=100)
        sort_columns = {
            "trip_id": "trip_id", "pickup_datetime": "pickup_datetime",
            "fare": "fare", "distance": "distance", "total": "total",
        }
        sort_by = args.get("sort_by", "pickup_datetime")
        if sort_by not in sort_columns:
            raise QueryError("sort_by must be trip_id, pickup_datetime, fare, distance, or total")
        order = args.get("order", "desc").lower()
        if order not in {"asc", "desc"}:
            raise QueryError("order must be asc or desc")
        offset = (page - 1) * page_size
        rows = self._run(
            "SELECT trip_id, pickup_datetime, dropoff_datetime, pickup_zone, dropoff_zone, "
            "passengers, distance, fare, tip, tolls, total, payment_type, rate_code, "
            "COUNT(*) OVER() AS total_count FROM __TRIPS__" + where +
            f" ORDER BY {sort_columns[sort_by]} {order.upper()}, trip_id ASC LIMIT ? OFFSET ?",
            [*params, page_size, offset],
        )
        records = _records(rows)
        if records:
            total = int(records[0]["total_count"])
            for record in records:
                record.pop("total_count", None)
        else:
            total = int(self._run("SELECT COUNT(*) FROM __TRIPS__" + where, params).fetchone()[0])
        return {"page": page, "per_page": page_size, "total": total, "results": records}

    def trip(self, trip_id):
        rows = self._run(
            "SELECT trip_id, pickup_datetime, dropoff_datetime, pickup_zone, dropoff_zone, "
            "passengers, distance, fare, extra, mta_tax, tip, tolls, improvement_surcharge, "
            "congestion_surcharge, total, payment_type, rate_code, vendor_id, store_and_forward "
            "FROM __TRIPS__ WHERE trip_id = ? LIMIT 1", [trip_id]
        )
        records = _records(rows)
        return records[0] if records else None

    def summary(self, args):
        where, params = _filters(args)
        totals = self._run(
            "SELECT COUNT(*), AVG(fare), AVG(distance), AVG(trip_duration_min), "
            "SUM(total), SUM(tip) FROM __TRIPS__" + where, params
        ).fetchone()
        busiest = self._run(
            "SELECT pickup_hour, COUNT(*) AS trips FROM __TRIPS__" + where +
            " GROUP BY pickup_hour ORDER BY trips DESC, pickup_hour ASC LIMIT 1", params
        ).fetchone()
        return {
            "total_trips": int(totals[0]),
            "average_fare": round(float(totals[1]), 2) if totals[1] is not None else None,
            "average_distance": round(float(totals[2]), 2) if totals[2] is not None else None,
            "average_duration_minutes": round(float(totals[3]), 2) if totals[3] is not None else None,
            "total_amount": round(float(totals[4]), 2) if totals[4] is not None else None,
            "total_tips": round(float(totals[5]), 2) if totals[5] is not None else None,
            "busiest_hour": int(busiest[0]) if busiest else None,
            "busiest_hour_trips": int(busiest[1]) if busiest else 0,
        }

    def flat_fare(self, args, manhattan_zone_ids):
        direction = args.get("direction", "from_airport")
        if direction not in {"from_airport", "to_airport"}:
            raise QueryError("direction must be from_airport or to_airport")
        airport = _as_int(args, "airport_zone", default=132, minimum=1)
        if airport != 132:
            raise QueryError("Only JFK Airport (zone 132) is currently supported")
        if direction == "from_airport":
            pickup, dropoff = "pickup_zone", "dropoff_zone"
            fixed_zone, other_zone = airport, manhattan_zone_ids
        else:
            pickup, dropoff = "pickup_zone", "dropoff_zone"
            fixed_zone, other_zone = airport, manhattan_zone_ids
        pair_filter = f"{pickup} = ? AND {dropoff} IN ({','.join('?' for _ in other_zone)})" if direction == "from_airport" else f"{pickup} IN ({','.join('?' for _ in other_zone)}) AND {dropoff} = ?"
        pair_params = [fixed_zone, *other_zone] if direction == "from_airport" else [*other_zone, fixed_zone]
        where, params = _filters(args, pickup_zone=False, dropoff_zone=False)
        where += (" AND " if where else " WHERE ") + pair_filter
        params.extend(pair_params)
        row = self._run(
            "SELECT COUNT(*) FILTER (WHERE rate_code = 2), "
            "AVG(fare) FILTER (WHERE rate_code = 2), "
            "COUNT(*) FILTER (WHERE rate_code = 1), "
            "AVG(fare) FILTER (WHERE rate_code = 1) "
            "FROM __TRIPS__" + where, params
        ).fetchone()
        flat_count, flat_mean, meter_count, meter_mean = row
        flat_mean = float(flat_mean) if flat_mean is not None else None
        meter_mean = float(meter_mean) if meter_mean is not None else None
        return {
            "airport": "JFK Airport", "airport_zone": airport, "direction": direction,
            "comparison": "Observed mean base fare for rate code 2 versus rate code 1; not a per-trip counterfactual.",
            "flat_fare_trips": int(flat_count), "metered_trips": int(meter_count),
            "flat_fare_mean": round(flat_mean, 2) if flat_mean is not None else None,
            "metered_fare_mean": round(meter_mean, 2) if meter_mean is not None else None,
            "mean_difference_flat_minus_meter": round(flat_mean - meter_mean, 2)
                if flat_mean is not None and meter_mean is not None else None,
            "flat_fare_mean_below_meter_mean": flat_mean < meter_mean
                if flat_mean is not None and meter_mean is not None else None,
        }

    def data_quality(self):
        raw = self._run(
            "SELECT COUNT(*), "
            "COUNT(*) FILTER (WHERE pickup_datetime IS NULL), "
            "COUNT(*) FILTER (WHERE dropoff_datetime IS NULL), "
            "COUNT(*) FILTER (WHERE fare IS NULL), "
            "COUNT(*) FILTER (WHERE pickup_zone IS NULL), "
            "COUNT(*) FILTER (WHERE dropoff_zone IS NULL), "
            "COUNT(*) FILTER (WHERE NOT COALESCE(pickup_zone_ok, FALSE)), "
            "COUNT(*) FILTER (WHERE NOT COALESCE(dropoff_zone_ok, FALSE)) "
            "FROM __TRIPS__", normalized=True
        ).fetchone()
        return {
            "source": "normalized trip Parquet",
            "rows": int(raw[0]),
            "nulls": {
                "pickup_datetime": int(raw[1]), "dropoff_datetime": int(raw[2]),
                "fare": int(raw[3]), "pickup_zone": int(raw[4]), "dropoff_zone": int(raw[5]),
            },
            "unmatched_zone_ids": {
                "pickup": int(raw[6]), "dropoff": int(raw[7]),
            },
            "unparseable_values": None,
            "unparseable_values_note": "The normalized artifact does not retain a separate count of parse failures versus source nulls.",
        }

    def by_borough(self, args, zone_borough):
        # Aggregate the bounded zone result in Python, after DuckDB has performed
        # the large scan and grouping. This keeps zone metadata out of the trip file.
        rows = self.by_zone({**args, "zone_type": "pickup", "sort_by": "trips", "order": "desc", "limit": 265})
        boroughs = {}
        for zone_id, trips, avg_fare, avg_distance in rows:
            borough = zone_borough.get(int(zone_id), "Unknown")
            current = boroughs.setdefault(borough, {"borough": borough, "trips": 0, "zones": 0,
                "fare_weighted_sum": 0.0, "distance_weighted_sum": 0.0})
            current["trips"] += int(trips)
            current["zones"] += 1
            if avg_fare is not None:
                current["fare_weighted_sum"] += float(avg_fare) * int(trips)
            if avg_distance is not None:
                current["distance_weighted_sum"] += float(avg_distance) * int(trips)
        results = []
        for item in boroughs.values():
            n = item["trips"]
            results.append({"borough": item["borough"], "trips": n, "zones": item["zones"],
                "average_fare": round(item["fare_weighted_sum"] / n, 2) if n else None,
                "average_distance": round(item["distance_weighted_sum"] / n, 2) if n else None})
        return sorted(results, key=lambda row: (-row["trips"], row["borough"]))

