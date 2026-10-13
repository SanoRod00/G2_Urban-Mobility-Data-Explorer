// Provide small fixtures with the same response shapes as the API.
window.DashboardMock = (() => {
  const boroughs = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"];
  const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const zones = Array.from({ length: 20 }, (_, index) => ({
    zone_id: index + 1,
    zone: `Sample Zone ${String(index + 1).padStart(2, "0")}`,
    borough: boroughs[index % boroughs.length],
    service_zone: index % 2 ? "Boro Zone" : "Yellow Zone",
    has_polygon: true,
    map_zone_id: index + 1
  }));
  const geojson = {
    type: "FeatureCollection",
    name: "sample_zones",
    crs: { type: "name", properties: { name: "EPSG:4326" } },
    features: zones.map((zone, index) => ({
      type: "Feature",
      properties: { LocationID: zone.zone_id, zone: zone.zone, borough: zone.borough },
      geometry: { type: "Polygon", coordinates: [[
        [-74.1 + index * 0.01, 40.65], [-74.09 + index * 0.01, 40.65],
        [-74.09 + index * 0.01, 40.66], [-74.1 + index * 0.01, 40.66],
        [-74.1 + index * 0.01, 40.65]
      ]] }
    }))
  };
  const zoneStats = zones.map((zone, index) => ({
    ...zone,
    trips: 900 - index * 31,
    average_fare: 12 + index * 0.7,
    average_distance: 2 + index * 0.2
  }));
  const trips = Array.from({ length: 20 }, (_, index) => ({
    trip_id: 2019000 + index,
    pickup_datetime: `2019-01-${String(index % 28 + 1).padStart(2, "0")}T08:00:00`,
    dropoff_datetime: `2019-01-${String(index % 28 + 1).padStart(2, "0")}T08:18:00`,
    pickup_zone: index % 20 + 1,
    dropoff_zone: (index + 4) % 20 + 1,
    passengers: index % 4 + 1,
    distance: 1.5 + index * 0.3,
    fare: 8 + index * 0.8,
    tip: index % 3,
    tolls: 0,
    total: 9 + index,
    payment_type: index % 2 + 1,
    rate_code: 1
  }));
  const detail = {
    ...trips[0], extra: 0.5, mta_tax: 0.5, improvement_surcharge: 0.3,
    congestion_surcharge: 0, vendor_id: 1, store_and_forward: false
  };

  const handlers = {
    "/api/health": () => ({ status: "ok" }),
    "/api/zones": () => ({ count: zones.length, results: zones }),
    "/api/zones/geojson": () => geojson,
    "/api/stats/summary": () => summary(),
    "/api/stats/hourly": (params) => ({ results: hourly(params.weekday) }),
    "/api/stats/by-zone": (params) => ({ zone_type: params.zone_type || "pickup", count: zoneStats.length, results: zoneStats }),
    "/api/trips": (params) => tripPage(params),
    "/api/stats/best-spots": (params) => bestSpots(params),
    "/api/stats/flat-fare": (params) => flatFare(params),
    "/api/stats/equity": () => equity(),
    "/api/stats/data-quality": () => quality()
  };

  // Return one mock response for a real API path.
  function get(path, params = {}) {
    if (path.startsWith("/api/trips/")) return detail;
    if (!handlers[path]) throw new Error("No mock fixture exists for " + path);
    return handlers[path](params);
  }

  // Make a summary response with the API's summary keys.
  function summary() {
    return { total_trips: 18420, average_fare: 14.82, average_distance: 2.71, average_duration_minutes: 16.4,
      total_amount: 302144.18, total_tips: 28641.22, busiest_hour: 8, busiest_hour_trips: 1320 };
  }

  // Make mock ranked pickup results.
  function bestSpots(params) {
    const limit = Number(params.k || 5);
    return { weekday: Number(params.weekday), weekday_name: weekdays[Number(params.weekday) - 1], hour: Number(params.hour), k: limit, min_trips: 30,
      results: zoneStats.slice(0, limit).map((zone, index) => ({ rank: index + 1, zone_id: zone.zone_id,
        map_zone_id: zone.map_zone_id, zone: zone.zone, borough: zone.borough,
        revenue_per_minute: 0.48 - index * 0.04, trips: zone.trips })) };
  }

  // Make the observed JFK fare comparison response.
  function flatFare(params) {
    return { airport: "JFK Airport", airport_zone: 132, direction: params.direction || "from_airport",
      comparison: "Observed mock means for JFK trips; not a per-trip counterfactual.", flat_fare_trips: 126,
      metered_trips: 54, flat_fare_mean: 52.0, metered_fare_mean: 48.4,
      mean_difference_flat_minus_meter: 3.6, flat_fare_mean_below_meter_mean: false };
  }

  // Make borough examples using the real equity response shape.
  function equity() {
    return { measure: "pickup activity and fares grouped by taxi-zone borough",
      limitation: "Mock borough counts do not describe rider demographics.",
      results: boroughs.map((borough, index) => ({ borough, trips: 4000 - index * 550, zones: 4,
        average_fare: 13 + index, average_distance: 2.4 + index * 0.3 })) };
  }

  // Make a data-quality fixture with the API's nested fields.
  function quality() {
    return { source: "mock normalized trip Parquet", rows: 18420,
      nulls: { pickup_datetime: 0, dropoff_datetime: 2, fare: 1, pickup_zone: 3, dropoff_zone: 4 },
      unmatched_zone_ids: { pickup: 8, dropoff: 5 }, unparseable_values: null,
      unparseable_values_note: "The normalized artifact does not retain a separate count of parse failures versus source nulls." };
  }

  // Make 24 hourly buckets for the chart.
  function hourly(weekday) {
    return Array.from({ length: 24 }, (_, hour) => ({
      hour, trips: Math.max(0, 80 + Math.round(65 * Math.sin((hour - 6) / 24 * Math.PI * 2))),
      average_fare: 12.5 + hour * 0.2,
      average_duration_minutes: weekday ? 15.5 : 16.2
    }));
  }

  // Return mock trips using the API pagination shape.
  function tripPage(params) {
    const page = Number(params.page || 1);
    const perPage = Number(params.per_page || 50);
    const offset = (page - 1) * perPage;
    return { page, per_page: perPage, total: trips.length, results: trips.slice(offset, offset + perPage) };
  }

  return { get };
})();
