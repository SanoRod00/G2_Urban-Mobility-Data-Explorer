import json
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

zones = pd.read_csv("data/raw/taxi_zone_lookup.csv", keep_default_na=False)

with open("data/raw/taxi_zones.geojson") as f:
    geojson = json.load(f)
polygon_ids = {int(x["properties"]["LocationID"]) for x in geojson["features"]}

twins = {57: 56, 104: 103, 105: 103}
day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status

def zone_info(zone_id):
    row = zones[zones["LocationID"] == zone_id].iloc[0]
    has_polygon = zone_id in polygon_ids
    map_id = zone_id if has_polygon else twins.get(zone_id)
    return {
        "zone_id": zone_id,
        "zone": row["Zone"],
        "borough": row["Borough"],
        "service_zone": row["service_zone"],
        "has_polygon": has_polygon,
        "map_zone_id": map_id,
    }
    
def make_spot(rank, row):
    zone_id, money, trips = row
    info = zone_info(zone_id)
    return {
            "rank": rank,
            "zone_id": zone_id,
            "zone": info["zone"],
            "map_zone_id": info["map_zone_id"],
            "borough": info["borough"],
            "revenue_per_minute": money,
            "trips": trips,
        }
@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/zones")
def get_zones():
    results = [zone_info(int(i)) for i in zones["LocationID"]]
    return jsonify({"count": len(results), "results": results})

@app.route("/api/zones/geojson")
def get_geojson():
    return jsonify(geojson)

@app.route("/api/stats/best-spots")
def best_spots():
    weekday = request.args.get("weekday", type=int)
    hour = request.args.get("hour", type=int)
    k = request.args.get("k", default=5, type=int)
    min_trips = request.args.get("min_trips", default=30, type=int)
    
    if weekday is None or not 1 <= weekday <= 7:
        return error("bad_request", "Weekday must be between 1 and 7", 400)
    if hour is None or not 0 <= hour <= 23:
        return error("bad_request", "hour must be between 0 and 23", 400)
    if not 1 <= k <= 20:
        return error("bad_request", "k must be between 1 and 20", 400)
    
    fake = [(132, 2.10, 640), (138, 2.05, 610), (140, 1.95, 580), (141, 1.90, 560), (142, 1.85, 540)]
    results = []
    for rank, row in enumerate(fake[:k], start=1):
        results.append(make_spot(rank, row))
    
    return jsonify({
        "weekday": weekday,
        "weekday_name": day_names[weekday - 1],
        "hour": hour,
        "k": k,
        "min_trips": min_trips,
        "results": results
    })
        
@app.errorhandler(404)
def not_found(e):
        return error("not_found", "The requested resource was not found", 404)
        
if __name__ == "__main__":
    app.run(debug=True)