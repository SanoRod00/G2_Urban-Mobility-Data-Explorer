"""HTTP API for the NYC taxi data explorer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from algorithms.top_k import top_k
from api.data_access import DataUnavailable, QueryError, TripData, _as_int, _filters


ROOT = Path(__file__).resolve().parents[1]
app = Flask(__name__)
CORS(app)
trip_data = TripData()

zones = pd.read_csv(ROOT / "data/raw/taxi_zone_lookup.csv", keep_default_na=False)
zone_rows = {int(row["LocationID"]): row for _, row in zones.iterrows()}
with (ROOT / "data/raw/taxi_zones.geojson").open(encoding="utf-8") as geojson_file:
    geojson = json.load(geojson_file)
polygon_ids = {int(feature["properties"]["LocationID"]) for feature in geojson["features"]}

twins = {57: 56, 104: 103, 105: 103}
day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
manhattan_zone_ids = [
    zone_id for zone_id, row in zone_rows.items()
    if str(row["Borough"]).casefold() == "manhattan"
]
zone_borough = {zone_id: str(row["Borough"]) for zone_id, row in zone_rows.items()}


def error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


@app.before_request
def keep_trip_data_disabled_until_enabled():
    """Fail closed until the operator intentionally enables trip-backed routes."""
    if request.endpoint and request.path.startswith(("/api/trips", "/api/stats/")):
        is_codespaces = os.getenv("CODESPACES", "").strip().casefold() in {"1", "true", "yes"}
        default_enabled = "0" if is_codespaces else "1"
        enabled = os.getenv("TRIP_DATA_API_ENABLED", default_enabled).strip().casefold()
        if enabled not in {"1", "true", "yes"}:
            return error(
                "trip_data_api_disabled",
                "Trip-backed API routes are disabled. Enable them only after confirming the service is private.",
                503,
            )


def zone_info(zone_id):
    row = zone_rows[int(zone_id)]
    has_polygon = int(zone_id) in polygon_ids
    return {
        "zone_id": int(zone_id),
        "zone": row["Zone"],
        "borough": row["Borough"],
        "service_zone": row["service_zone"],
        "has_polygon": has_polygon,
        "map_zone_id": int(zone_id) if has_polygon else twins.get(int(zone_id)),
    }


def make_spot(rank, row):
    zone_id, revenue_per_minute, trips = row
    info = zone_info(zone_id)
    return {
        "rank": rank,
        "zone_id": int(zone_id),
        "zone": info["zone"],
        "map_zone_id": info["map_zone_id"],
        "borough": info["borough"],
        "revenue_per_minute": round(float(revenue_per_minute), 4),
        "trips": int(trips),
    }


def _with_zone_info(rows):
    results = []
    for zone_id, trips, average_fare, average_distance in rows:
        info = zone_info(zone_id)
        results.append({
            **info,
            "trips": int(trips),
            "average_fare": round(float(average_fare), 2) if average_fare is not None else None,
            "average_distance": round(float(average_distance), 2) if average_distance is not None else None,
        })
    return results


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/zones")
def get_zones():
    results = [zone_info(zone_id) for zone_id in zones["LocationID"]]
    return jsonify({"count": len(results), "results": results})


@app.route("/api/zones/geojson")
def get_geojson():
    return jsonify(geojson)


@app.route("/api/stats/hourly")
def hourly_stats():
    return jsonify({"results": trip_data.hourly(request.args)})


@app.route("/api/stats/by-zone")
def by_zone_stats():
    rows = trip_data.by_zone(request.args)
    return jsonify({
        "zone_type": request.args.get("zone_type", "pickup"),
        "count": len(rows),
        "results": _with_zone_info(rows),
    })


@app.route("/api/trips")
def get_trips():
    return jsonify(trip_data.trips(request.args))


@app.route("/api/trips/<int:trip_id>")
def get_trip(trip_id):
    result = trip_data.trip(trip_id)
    if result is None:
        return error("not_found", f"Trip {trip_id} was not found", 404)
    return jsonify(result)


@app.route("/api/stats/summary")
def summary_stats():
    return jsonify(trip_data.summary(request.args))


@app.route("/api/stats/best-spots")
def best_spots():
    weekday = _as_int(request.args, "weekday", minimum=1, maximum=7)
    hour = _as_int(request.args, "hour", minimum=0, maximum=23)
    if weekday is None:
        raise QueryError("weekday is required and must be between 1 and 7")
    if hour is None:
        raise QueryError("hour is required and must be between 0 and 23")
    k = _as_int(request.args, "k", default=5, minimum=1, maximum=20)
    min_trips = _as_int(request.args, "min_trips", default=30, minimum=1)
    where, params = _filters(request.args)
    where += (" AND " if where else " WHERE ") + "pickup_weekday = ? AND pickup_hour = ?"
    params.extend([weekday, hour])
    rows = trip_data._run(
        "SELECT pickup_zone, AVG(revenue_per_minute) AS revenue_per_minute, COUNT(*) AS trips "
        "FROM __TRIPS__" + where +
        " GROUP BY pickup_zone HAVING COUNT(*) >= ?",
        [*params, min_trips],
    ).fetchall()
    ranked = top_k(rows, k, key=lambda row: row[1])
    results = [make_spot(rank, row) for rank, row in enumerate(ranked, start=1)]
    return jsonify({
        "weekday": weekday,
        "weekday_name": day_names[weekday - 1],
        "hour": hour,
        "k": k,
        "min_trips": min_trips,
        "results": results,
    })


@app.route("/api/stats/flat-fare")
def flat_fare_stats():
    return jsonify(trip_data.flat_fare(request.args, manhattan_zone_ids))


@app.route("/api/stats/equity")
def equity_stats():
    return jsonify({
        "measure": "pickup activity and fares grouped by taxi-zone borough",
        "limitation": "Borough is a geographic proxy; this dataset does not contain rider demographic attributes.",
        "results": trip_data.by_borough(request.args, zone_borough),
    })


@app.route("/api/stats/data-quality")
def data_quality_stats():
    return jsonify(trip_data.data_quality())


@app.errorhandler(QueryError)
def invalid_query(exc):
    return error("bad_request", str(exc), 400)


@app.errorhandler(DataUnavailable)
def unavailable_data(exc):
    return error("data_unavailable", str(exc), 503)


@app.errorhandler(404)
def not_found(_exc):
    return error("not_found", "The requested resource was not found", 404)


if __name__ == "__main__":
    app.run(debug=False)
