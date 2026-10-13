# G2 Urban Mobility Data Explorer

This project explores New York City yellow taxi trips from January 2019 and the city's taxi zones.
Python scripts normalize and clean trip records, which are stored as Parquet files.
The Flask API serves trip and zone data; a static HTML dashboard is in `frontend/`.

## Requirements

Python 3.11 or newer is required by the pinned Pandas and GeoPandas versions.

Install dependencies from the project root with:

```text
python -m pip install -r requirements.txt
```

This install command was not run during this review because package installation was prohibited. A no-download dry run confirmed the requirements file parses and all listed versions are already installed in the current virtual environment.

## Data files

The scripts use paths relative to the project root. The raw inputs belong in `data/raw/`:

- `yellow_tripdata_2019-01.csv` — January 2019 yellow taxi trips.
- `taxi_zone_lookup.csv` — taxi zone IDs, names, and boroughs.
- `taxi_zones.shp` — taxi zone shapes. Keep its companion files alongside it: `taxi_zones.dbf`, `taxi_zones.shx`, and `taxi_zones.prj`.
- `taxi_zones.geojson` — produced by the zone conversion step and read by the API.

The pipeline creates `data/processed/trips_normalized.parquet` and `data/processed/zones.csv`. Cleaning creates `data/processed/trips_cleaned.parquet` and refreshes `cleaning/exclusion_log.csv` and `cleaning/exclusion_summary.csv`.

All paths under `data/` are ignored by Git. A clone therefore needs the raw input files supplied separately and the processed files generated locally.

The API defaults to `data/processed/trips_cleaned.parquet`. Set `TRIPS_PARQUET` to a different Parquet file to change its trip query source. The file must have the cleaned schema, including fields such as `pickup_hour`, `pickup_weekday`, `trip_duration_min`, and `revenue_per_minute`. The current `pipeline/make_sample.py` samples the normalized file, so its `data/processed/trips_sample.parquet` output does not have all fields required by the statistics routes.

## Run order

1. Convert the taxi zone shapefile to GeoJSON with `pipeline/convert_zones.py`. A verified command for this step is **not available**; running the script writes a data file.
2. Load and normalize the trip CSV with `pipeline/load_data.py`. A verified command for this step is **not available**; running the script writes data files.
3. Clean normalized trips with `cleaning/validate.py`. The script has no run command verified in this review; running it writes data and cleaning reports.
4. Database load: **NOT AVAILABLE YET (owner: Orla)**.
5. Start the API from the project root with `python -m api.app`. This command was verified to start the local Flask server.
6. Dashboard opening command: **not found**. The static page is `frontend/index.html`; no dashboard server or launch script is provided.

In Codespaces, `/api/trips` and `/api/stats/*` are disabled by default. Set the API port visibility to **Private** before setting `TRIP_DATA_API_ENABLED=1` in the API process environment. Outside Codespaces, those routes are enabled by default.
