# NYC Taxi Data Explorer

This is a plain HTML, CSS, and JavaScript dashboard for the January 2019 taxi trip API. It uses the existing Flask API response fields and has a local mock mode for a quick visual review.

## Open the dashboard

From the repository root, start the static file server:

```text
python -m http.server 8000 --directory frontend
```

Open `http://127.0.0.1:8000` in a browser. Keep the API running separately with `python -m api.app` from the repository root.

The page defaults to `http://127.0.0.1:5000`. In Codespaces, copy the API's forwarded URL from the Ports panel and add it as the `api` query parameter. For example, encode the full API URL as the parameter value:

```text
http://127.0.0.1:8000/?api=https%3A%2F%2Fyour-codespace-5000.app.github.dev
```

For trip and statistics routes in Codespaces, make the API port private and set `TRIP_DATA_API_ENABLED=1` in the API process only after checking the port visibility.

## Review modes

- `?mock=1` uses the small fixtures in `mock.js`. It does not need the API and returns the same response shapes for the dashboard views.
- `?check=1` calls each API endpoint once and lists whether the response keys match the frontend contract. It uses the API unless `?mock=1` is also present.
- These parameters can be combined with `api`, for example `?mock=1&check=1`.

## Screenshot guide

Use live API data where available. For each view below, leave global date, fare, distance, payment, pickup-zone, and dropoff-zone filters blank unless the view says otherwise. Blank dates show all available January 2019 records.

1. **Best Spot to Wait:** leave global filters blank; choose Tuesday and 08:00. Capture the ranked bars and table. The chart measures revenue per minute, not waiting time.
2. **Flat fare:** leave global filters blank; choose “From airport.” Capture both fare groups, sample counts, and the note that this is historical JFK data.
3. **Taxi equity:** leave global filters blank. Capture pickup share, taxi-zone share, trips per active zone, and the limitation note.
4. **Hourly demand:** leave global filters blank; choose “All weekdays.” Capture the 24 hourly buckets and chart caption.
5. **Map:** leave global filters blank; choose Pickup and Trips with no weekday or hour filter. Capture the legend and the note for zones 264 and 265.

The mock mode is suitable for layout screenshots, but label those images as mock data.
