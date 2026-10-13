# API contract

The Flask API is implemented in `api/app.py`. Trip analytics use DuckDB to query
`data/processed/trips_cleaned.parquet` directly. Set `TRIPS_PARQUET_PATH` to use a
different cleaned Parquet file. The data-quality endpoint reads the normalized
Parquet artifact because its purpose is to describe input quality.

## Enable trip-backed routes safely

In Codespaces, all `/api/trips` and `/api/stats/*` routes, including best-spots,
return HTTP 503 by default. Confirm the API port is **Private**, then set
`TRIP_DATA_API_ENABLED` to `1`, `true`, or `yes` in the API process environment
to enable them. Outside Codespaces, the routes are enabled by default. Health
and zone metadata routes remain available while trip routes are disabled.

Create or refresh the cleaned dataset by running `python -m cleaning.validate`
from the project root. Start the API with `python -m api.app`. Set
In Codespaces, set `TRIP_DATA_API_ENABLED=1` in the API process environment only
after the port's visibility has been confirmed.

## Existing routes

- `GET /api/health` → `{ "status": "ok" }`
- `GET /api/zones` → `{ "count": number, "results": [zone, ...] }`
- `GET /api/zones/geojson` → GeoJSON feature collection

Existing zone fields are preserved: `zone_id`, `zone`, `borough`,
`service_zone`, `has_polygon`, and `map_zone_id`.

## Trip routes

### `GET /api/trips`

Supported filters: `date_from`, `date_to` (`YYYY-MM-DD`, inclusive),
`pickup_zone`, `dropoff_zone`, `fare_min`, `fare_max`, `distance_min`,
`distance_max`, and `payment_type`.

Pagination: `page` (default 1), `per_page` (default 50, maximum 100). Sorting:
`sort_by=trip_id|pickup_datetime|fare|distance|total` and `order=asc|desc`.

Response: `{ "page", "per_page", "total", "results": [...] }`. Each result
contains trip ID, pickup/drop-off timestamps and zones, passengers, distance,
fare, tip, tolls, total, payment type, and rate code. The default order is newest
pickup time first, then ascending trip ID for ties.

### `GET /api/trips/<id>`

Returns one trip with its available normalized fare components and source fields.
An unknown ID returns HTTP 404.

## Statistics routes

The common trip filters are `date_from`, `date_to`, `pickup_zone`,
`dropoff_zone`, fare and distance bounds, and `payment_type`. Date filters apply
to pickup time.

- `GET /api/stats/hourly`: optional common filters and `weekday` (ISO 1–7).
  Returns 24 buckets with `hour`, `trips`, `average_fare`, and
  `average_duration_minutes`. The hour is the pickup hour; empty buckets have
  zero trips and null averages.
- `GET /api/stats/by-zone`: common filters plus `zone_type=pickup|dropoff`,
  optional `weekday` (1–7), `hour` (0–23), `sort_by=trips|average_fare|
  average_distance|zone_id`, `order=asc|desc`, and `limit` (default 265,
  maximum 265). Results include the existing zone metadata and trip count,
  average fare, and average distance.
- `GET /api/stats/summary`: common filters. Returns trip count, average fare,
  average distance and duration, total amount, total tips, and busiest pickup
  hour.
- `GET /api/stats/best-spots`: requires `weekday` (1–7) and `hour` (0–23);
  accepts `k` (default 5, maximum 20) and `min_trips` (default 30). Results use
  average revenue per minute and the project's `top_k` algorithm.
- `GET /api/stats/flat-fare`: supports `direction=from_airport|to_airport`
  (default `from_airport`) and `airport_zone=132` (JFK only), plus common date
  filters. It compares observed mean base fares for rate code 2 and rate code 1
  on JFK–Manhattan trips, and reports each group's sample count. This is a
  comparison of observed groups, not a per-trip meter-fare counterfactual.
- `GET /api/stats/equity`: common filters plus optional `weekday` and `hour`.
  Groups pickup activity and fares by taxi-zone borough. The response states
  that borough is only a geographic proxy; the data has no rider demographics.
- `GET /api/stats/data-quality`: reports normalized input row count, selected
  null counts, unmatched pickup/drop-off zone counts, and explicitly indicates
  that parse failures cannot be separated from original nulls in the normalized
  artifact.

Invalid query parameters return HTTP 400 with
`{ "error": { "code": "bad_request", "message": "..." } }`. Missing trips
return 404; missing dataset artifacts return 503 with `data_unavailable`.
