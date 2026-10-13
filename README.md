# NYC Taxi Data Explorer

This project explores New York City yellow taxi trips from January 2019.
The Flask API serves trip, zone, and summary data to a browser dashboard.
The dashboard is plain HTML, CSS, and JavaScript in `frontend/`.

## Requirements

- Python 3.11 or newer
- The raw January 2019 trip and taxi-zone files listed below

From the repository root, install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## Data files

The data files are not included in Git. Put the supplied source files in `data/raw/`:

- `yellow_tripdata_2019-01.csv`
- `taxi_zone_lookup.csv`
- `taxi_zones.shp`
- `taxi_zones.dbf`
- `taxi_zones.shx`
- `taxi_zones.prj`

The shapefile companion files must sit beside `taxi_zones.shp`. The zone conversion step creates `data/raw/taxi_zones.geojson`. The pipeline and cleaning steps create `data/processed/trips_normalized.parquet`, `data/processed/zones.csv`, and `data/processed/trips_cleaned.parquet`.

## Run the project

Run these commands from the repository root, in order, after placing the source files:

1. Convert the taxi-zone shapefile to GeoJSON:

   ```bash
   python pipeline/convert_zones.py
   ```

2. Load and normalize the trip CSV:

   ```bash
   python pipeline/load_data.py
   ```

3. Clean the normalized trips and create the cleaned Parquet file:

   ```bash
   python -m cleaning.validate
   ```

4. Database load: **NOT AVAILABLE YET (owner: Orla)**

5. Start the API in one terminal:

   ```bash
   python -m api.app
   ```

6. Start the dashboard's static web server in a second terminal:

   ```bash
   python -m http.server 8000 --directory frontend
   ```

7. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. The dashboard connects to the API at `http://127.0.0.1:5000` by default.

The API reads `data/processed/trips_cleaned.parquet` by default. Set `TRIPS_PARQUET` in the API process to use a different cleaned-schema Parquet file.

### Codespaces access

The API disables trip and statistics routes by default in Codespaces. First set the forwarded API port to **Private** in the Ports panel. Then start the API with `TRIP_DATA_API_ENABLED=1` in its environment. For a Bash terminal:

```bash
TRIP_DATA_API_ENABLED=1 python -m api.app
```

Use the API's forwarded URL for the dashboard by adding it as the `api` query parameter. See [`frontend/README.md`](frontend/README.md) for the URL format and mock/contract-check modes.

## Dashboard screenshots

Screenshots can be stored in `docs/images/` and embedded here. The images shown in chat are not currently available as files in this repository, so they are not embedded yet. Please add or upload the screenshot files into `docs/images/` to include them in the README.
