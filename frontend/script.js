const state = {
  controllers: {}, zones: [], geojson: null, mapRows: [], bestSpots: [], filters: {},
  page: 1, perPage: 50, sortBy: "pickup_datetime", order: "desc",
  direction: "from_airport", selectedZone: null, selectedTrip: null, timer: null
};

// Read and validate the shared filter form.
function filterValues() {
  const form = document.getElementById("filters-form");
  if (!form.reportValidity()) return null;
  const values = Object.fromEntries(new FormData(form).entries());
  if (values.date_from && values.date_to && values.date_from > values.date_to) return filterError("Start date must be on or before end date.");
  if (!januaryDate(values.date_from) || !januaryDate(values.date_to)) return filterError("Dates must be within January 2019.");
  if (!validRange(values.fare_min, values.fare_max, "Fare")) return null;
  if (!validRange(values.distance_min, values.distance_max, "Distance")) return null;
  clearFilterError();
  return values;
}

// Check that a selected date is inside January 2019.
function januaryDate(value) {
  return !value || (value >= "2019-01-01" && value <= "2019-01-31");
}

// Reject a reversed optional number range.
function validRange(min, max, label) {
  if (min && max && Number(min) > Number(max)) return filterError(label + " minimum must not exceed its maximum.");
  return true;
}

// Show a filter error and return no filter object.
function filterError(message) {
  const status = document.getElementById("app-status");
  status.textContent = message;
  status.classList.add("is-error");
  return null;
}

// Clear the filter form message.
function clearFilterError() {
  const status = document.getElementById("app-status");
  status.textContent = "";
  status.classList.remove("is-error");
}

// Put a loading, empty, or error message in a widget.
function setState(id, message, kind) {
  const item = document.getElementById(id);
  item.textContent = message || "";
  item.className = "widget-state" + (kind ? " is-" + kind : "");
}

// Run one widget request and ignore responses made stale by newer requests.
async function runWidget(key, stateId, request, render) {
  if (state.controllers[key]) state.controllers[key].abort();
  const controller = new AbortController();
  state.controllers[key] = controller;
  setState(stateId, "", "loading");
  const retry = document.querySelector('[data-retry="' + key + '"]');
  if (retry) retry.hidden = true;
  try {
    const result = await request(controller.signal);
    if (controller.signal.aborted || state.controllers[key] !== controller) return;
    render(result);
  } catch (error) {
    if (error.name === "AbortError" || state.controllers[key] !== controller) return;
    widgetError(key, stateId, error);
  }
}

// Explain API errors, disabled routes, and network failures.
function widgetError(key, stateId, error) {
  let message = error.message || "The API request failed.";
  if (error.status === 503) message += " Trip data may be disabled; set TRIP_DATA_API_ENABLED=1 after confirming the API port is private.";
  if (error.isNetworkError) message = "The API is not running or unreachable at " + DashboardConfig.apiBase + ". " + message;
  setState(stateId, message, "error");
  const retry = document.querySelector('[data-retry="' + key + '"]');
  if (retry) retry.hidden = false;
  console.error("Dashboard widget " + key + " failed:", error);
}

// Format missing or numeric values consistently.
function number(value, digits) {
  if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "–";
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: digits || 0 });
}

// Format one fare as US dollars.
function money(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "–";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
}

// Add the dataset distance unit only when a value is present.
function miles(value) {
  const formatted = number(value, 2);
  return formatted === "–" ? formatted : formatted + " mi";
}

// Format an hour as a 24-hour clock label.
function hourLabel(value) {
  return value === null || value === undefined ? "–" : String(value).padStart(2, "0") + ":00";
}

// Add one safe label/value pair to a definition list.
function addDefinition(list, label, value) {
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = value === null || value === undefined ? "–" : String(value);
  list.append(term, detail);
}

// Add the documented weekday and hour choices.
function fillTimeOptions() {
  const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  ["hourly-weekday", "map-weekday", "weekday-select"].forEach((id) => fillWeekdays(id, weekdays));
  fillHours("map-hour", true);
  fillHours("hour-select", false);
}

// Fill one weekday selector with API weekday numbers.
function fillWeekdays(id, labels) {
  const select = document.getElementById(id);
  if (id !== "weekday-select") addOption(select, "", "All weekdays");
  labels.forEach((label, index) => addOption(select, index + 1, label));
  if (id === "weekday-select") select.value = "2";
}

// Fill one hour selector with 0 through 23.
function fillHours(id, includeAll) {
  const select = document.getElementById(id);
  if (includeAll) addOption(select, "", "All hours");
  for (let hour = 0; hour < 24; hour += 1) addOption(select, hour, hourLabel(hour));
  if (id === "hour-select") select.value = "12";
}

// Add a text-only option to a select.
function addOption(select, value, label) {
  const option = document.createElement("option");
  option.value = String(value);
  option.textContent = label;
  select.appendChild(option);
}

// Load zone names for both filters and map details.
async function loadZones() {
  await runWidget("zones", "zones-state", (signal) => DashboardApi.get("/api/zones", {}, signal), (data) => {
    state.zones = data.results;
    const sorted = state.zones.slice().sort((a, b) => a.zone.localeCompare(b.zone));
    ["pickup-zone", "dropoff-zone"].forEach((id) => {
      const select = document.getElementById(id);
      select.replaceChildren();
      addOption(select, "", id === "pickup-zone" ? "All pickup zones" : "All dropoff zones");
      sorted.forEach((zone) => addOption(select, zone.zone_id, zone.zone + " — " + zone.borough));
    });
    document.getElementById("insight-copy").textContent = "Loaded " + number(data.count) + " taxi zones for names and map details.";
    document.getElementById("connection-mode").textContent = DashboardConfig.mock ? "Mock data mode" : "API: " + DashboardConfig.apiBase;
    setState("zones-state", data.results.length ? "" : "No taxi zones returned.", data.results.length ? "" : "empty");
  });
}

// Load overview values for the current filters.
async function loadSummary(filters) {
  await runWidget("summary", "summary-state", (signal) => DashboardApi.get("/api/stats/summary", filters, signal), (data) => {
    document.getElementById("total-trips").textContent = number(data.total_trips);
    document.getElementById("average-fare").textContent = money(data.average_fare);
    document.getElementById("average-distance").textContent = miles(data.average_distance);
    document.getElementById("busiest-hour").textContent = hourLabel(data.busiest_hour);
    document.getElementById("busiest-hour-count").textContent = number(data.busiest_hour_trips) + " pickups in the busiest hour";
    setState("summary-state", data.total_trips ? "" : "No trips match these filters.", data.total_trips ? "" : "empty");
  });
}

// Load hourly trip counts for all hours.
async function loadHourly(filters) {
  const params = Object.assign({}, filters, { weekday: document.getElementById("hourly-weekday").value });
  await runWidget("hourly", "hourly-state", (signal) => DashboardApi.get("/api/stats/hourly", params, signal), (data) => {
    const rows = data.results || [];
    DashboardCharts.bars(document.getElementById("trip-activity"), rows, "hour", "trips", number);
    const hasTrips = rows.some((row) => row.trips);
    setState("hourly-state", hasTrips ? "" : "No hourly trips match these filters.", hasTrips ? "" : "empty");
  });
}

// Load zone statistics and cached GeoJSON for the map.
async function loadMap(filters) {
  const params = Object.assign({}, filters, {
    zone_type: document.getElementById("map-zone-type").value,
    weekday: document.getElementById("map-weekday").value,
    hour: document.getElementById("map-hour").value,
    sort_by: "trips", order: "desc", limit: 265
  });
  await runWidget("map", "map-state", async (signal) => {
    const requests = [DashboardApi.get("/api/stats/by-zone", params, signal)];
    if (!state.geojson) requests.push(DashboardApi.get("/api/zones/geojson", {}, signal));
    const values = await Promise.all(requests);
    if (!state.geojson) state.geojson = values[1];
    return { zoneData: values[0], geometry: state.geojson };
  }, (result) => {
    if (!document.querySelector("#map-view svg")) DashboardMap.draw(document.getElementById("map-view"), result.geometry, showZoneDetails);
    state.mapRows = result.zoneData.results;
    DashboardMap.update(state.mapRows, document.getElementById("map-metric").value, state.bestSpots, state.selectedZone);
    if (state.selectedZone !== null) showZoneDetails(state.selectedZone);
    const offMap = result.zoneData.results.filter((row) => [264, 265].includes(Number(row.zone_id)));
    document.getElementById("map-note").textContent = "Zones 264 and 265 have no map polygon" + (offMap.length ? "; matching zones in this view: " + offMap.map((row) => row.zone_id).join(", ") : "; neither has data in this filtered view.");
    const hasRows = result.zoneData.results.length > 0;
    setState("map-state", hasRows ? "" : "No zones match these filters.", hasRows ? "" : "empty");
  });
}

// Show map-zone facts and a pickup-filter button.
function showZoneDetails(zoneId) {
  const info = DashboardMap.getZone(zoneId) || {};
  state.selectedZone = Number(zoneId);
  const box = document.getElementById("zone-details");
  box.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = info.zone || "Zone " + zoneId;
  const facts = document.createElement("p");
  facts.textContent = (info.borough || "Borough unknown") + " · " + number(info.trips) + " trips · average fare " + money(info.average_fare) + " · average distance " + miles(info.average_distance);
  box.append(title, facts);
  const button = document.getElementById("use-pickup-zone");
  button.dataset.zoneId = String(info.zone_id || zoneId);
  button.hidden = false;
  DashboardMap.update(state.mapRows, document.getElementById("map-metric").value, state.bestSpots, state.selectedZone);
}

// Load trips using server-side page and sort parameters.
async function loadTrips(filters) {
  const params = Object.assign({}, filters, {
    page: state.page, per_page: state.perPage, sort_by: state.sortBy, order: state.order
  });
  await runWidget("trips", "trips-state", (signal) => DashboardApi.get("/api/trips", params, signal), (data) => {
    const body = document.getElementById("trips-results");
    body.replaceChildren();
    data.results.forEach((trip) => body.appendChild(tripRow(trip)));
    const pages = Math.max(1, Math.ceil(data.total / data.per_page));
    document.getElementById("trips-count").textContent = number(data.total) + " matching trips";
    document.getElementById("page-label").textContent = "Page " + data.page + " of " + pages;
    document.getElementById("previous-page").disabled = data.page <= 1;
    document.getElementById("next-page").disabled = data.page >= pages;
    updateSortLabels();
    setState("trips-state", data.results.length ? "" : "No trips match these filters.", data.results.length ? "" : "empty");
  });
}

// Build one trip row with zone names from the lookup response.
function tripRow(trip) {
  const row = document.createElement("tr");
  row.className = "trip-row";
  row.tabIndex = 0;
  row.dataset.tripId = String(trip.trip_id);
  const values = [trip.trip_id, formatDate(trip.pickup_datetime), zoneName(trip.pickup_zone), zoneName(trip.dropoff_zone), money(trip.fare), miles(trip.distance), money(trip.total)];
  values.forEach((value) => {
    const cell = document.createElement("td");
    cell.textContent = String(value);
    row.appendChild(cell);
  });
  return row;
}

// Find a zone's API name from its numeric ID.
function zoneName(zoneId) {
  const zone = state.zones.find((item) => Number(item.zone_id) === Number(zoneId));
  return zone ? zone.zone + " (" + zone.borough + ")" : "Zone " + (zoneId ?? "–");
}

// Format an API timestamp for the trips table.
function formatDate(value) {
  if (!value) return "–";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString("en-US");
}

// Update the visible sort direction and accessible table headers.
function updateSortLabels() {
  document.querySelectorAll("[data-sort]").forEach((button) => {
    const active = button.dataset.sort === state.sortBy;
    button.querySelector("span").textContent = active ? (state.order === "asc" ? "↑" : "↓") : "↕";
    button.closest("th").setAttribute("aria-sort", active ? (state.order === "asc" ? "ascending" : "descending") : "none");
  });
}

// Load and draw best pickup spots from the real response shape.
async function loadBestSpots(filters) {
  const button = document.getElementById("load-spots-button");
  button.disabled = true;
  const params = Object.assign({}, filters, {
    weekday: document.getElementById("weekday-select").value,
    hour: document.getElementById("hour-select").value,
    k: 5
  });
  await runWidget("best-spots", "spots-status", (signal) => DashboardApi.get("/api/stats/best-spots", params, signal), (data) => {
    state.bestSpots = data.results;
    drawBestSpots(data.results);
    const hasRows = data.results.length > 0;
    setState("spots-status", hasRows ? "" : "No pickup zones match this day and hour.", hasRows ? "" : "empty");
    if (state.geojson) DashboardMap.update(state.mapRows, document.getElementById("map-metric").value, state.bestSpots, state.selectedZone);
  });
  button.disabled = false;
}

// Fill the ranked bars and the existing pickup-spots table.
function drawBestSpots(spots) {
  const body = document.getElementById("spots-results");
  body.replaceChildren();
  spots.forEach((spot) => {
    const row = document.createElement("tr");
    [spot.rank, zoneName(spot.zone_id), spot.borough, money(spot.revenue_per_minute) + "/min", number(spot.trips)].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "–");
      row.appendChild(cell);
    });
    body.appendChild(row);
  });
  DashboardCharts.bars(document.getElementById("best-spots-chart"), spots, "zone", "revenue_per_minute", (value) => money(value) + "/min");
}

// Load the single JFK flat-fare comparison.
async function loadFlatFare(filters) {
  const params = Object.assign({}, filters, { direction: state.direction, airport_zone: 132 });
  delete params.pickup_zone;
  delete params.dropoff_zone;
  await runWidget("flat-fare", "flat-fare-state", (signal) => DashboardApi.get("/api/stats/flat-fare", params, signal), (data) => {
    DashboardCharts.comparison(document.getElementById("flat-fare-chart"), data, money);
    document.getElementById("flat-fare-copy").textContent = data.comparison;
    const hasRows = data.flat_fare_trips || data.metered_trips;
    setState("flat-fare-state", hasRows ? "" : "No airport trips match these filters.", hasRows ? "" : "empty");
  });
}

// Load borough trips and calculate each share in the browser.
async function loadEquity(filters) {
  await runWidget("equity", "equity-state", (signal) => DashboardApi.get("/api/stats/equity", filters, signal), (data) => {
    drawEquity(data.results);
    document.getElementById("equity-limitation").textContent = data.limitation;
    setState("equity-state", data.results.length ? "" : "No borough activity matches these filters.", data.results.length ? "" : "empty");
  });
}

// Compare pickup share with each borough's share of all taxi zones.
function drawEquity(results) {
  const container = document.getElementById("equity-chart");
  container.replaceChildren();
  const totalTrips = results.reduce((sum, item) => sum + Number(item.trips || 0), 0);
  const zoneTotals = {};
  state.zones.forEach((zone) => { zoneTotals[zone.borough] = (zoneTotals[zone.borough] || 0) + 1; });
  const totalZones = Object.values(zoneTotals).reduce((sum, count) => sum + count, 0);
  Object.keys(zoneTotals).sort().forEach((borough) => {
    const item = results.find((row) => row.borough === borough) || { trips: 0, zones: 0 };
    const pickupShare = totalTrips ? Number(item.trips) / totalTrips * 100 : 0;
    const zoneShare = totalZones ? zoneTotals[borough] / totalZones * 100 : 0;
    const row = document.createElement("div");
    row.className = "equity-row";
    const name = document.createElement("strong");
    name.textContent = borough;
    const shares = document.createElement("span");
    shares.textContent = number(pickupShare, 1) + "% of pickups · " + number(zoneShare, 1) + "% of taxi zones";
    const trips = document.createElement("span");
    const activeZones = Number(item.zones || 0);
    trips.textContent = number(item.trips) + " trips · " + number(activeZones ? item.trips / activeZones : 0, 1) + " trips per active zone";
    const bar = document.createElement("progress");
    bar.max = 100;
    bar.value = pickupShare;
    bar.setAttribute("aria-label", borough + " pickup share");
    row.append(name, shares, trips, bar);
    container.appendChild(row);
  });
}

// Load by-zone averages for the fare and distance scatter plot.
async function loadScatter(filters) {
  await runWidget("scatter", "scatter-state", (signal) => DashboardApi.get("/api/stats/by-zone", Object.assign({}, filters, { zone_type: "pickup", limit: 265 }), signal), (data) => {
    DashboardCharts.scatter(document.getElementById("fare-distance-chart"), data.results);
    setState("scatter-state", data.results.length ? "" : "No zone averages match these filters.", data.results.length ? "" : "empty");
  });
}

// Load null and unmatched-zone counts from the data-quality route.
async function loadQuality() {
  await runWidget("quality", "quality-state", (signal) => DashboardApi.get("/api/stats/data-quality", {}, signal), (data) => {
    const list = document.getElementById("quality-details");
    list.replaceChildren();
    addDefinition(list, "Source", data.source);
    addDefinition(list, "Rows", number(data.rows));
    Object.entries(data.nulls).forEach(([key, value]) => addDefinition(list, "Null " + key, number(value)));
    Object.entries(data.unmatched_zone_ids).forEach(([key, value]) => addDefinition(list, "Unmatched " + key + " zones", number(value)));
    addDefinition(list, "Unparseable values", number(data.unparseable_values));
    addDefinition(list, "Note", data.unparseable_values_note);
    setState("quality-state", data.rows ? "" : "No quality records returned.", data.rows ? "" : "empty");
  });
}

// Open one trip record in the detail drawer.
async function loadTripDetail(tripId) {
  state.selectedTrip = tripId;
  const drawer = document.getElementById("trip-drawer");
  if (!drawer.open) drawer.showModal();
  await runWidget("trip-detail", "trip-detail-state", (signal) => DashboardApi.get("/api/trips/" + encodeURIComponent(tripId), {}, signal), (data) => {
    const list = document.getElementById("trip-detail-fields");
    list.replaceChildren();
    Object.entries(data).forEach(([key, value]) => addDefinition(list, key.replaceAll("_", " "), value));
    setState("trip-detail-state", "", "");
  });
}

// Reload every trip-backed widget with the same global filters.
function refreshAll(filters) {
  state.filters = filters;
  Promise.all([
    loadSummary(filters), loadHourly(filters), loadMap(filters), loadTrips(filters),
    loadBestSpots(filters), loadFlatFare(filters), loadEquity(filters), loadScatter(filters), loadQuality()
  ]);
}

// Debounce automatic refreshes while a filter changes.
function scheduleRefresh() {
  window.clearTimeout(state.timer);
  state.timer = window.setTimeout(() => {
    const filters = filterValues();
    if (filters) { state.page = 1; refreshAll(filters); }
  }, 350);
}

// Retry one named widget with the current controls.
function retryWidget(key) {
  const filters = state.filters;
  if (key === "zones") return loadZones();
  if (key === "summary") return loadSummary(filters);
  if (key === "hourly") return loadHourly(filters);
  if (key === "map") return loadMap(filters);
  if (key === "trips") return loadTrips(filters);
  if (key === "best-spots") return loadBestSpots(filters);
  if (key === "flat-fare") return loadFlatFare(filters);
  if (key === "equity") return loadEquity(filters);
  if (key === "scatter") return loadScatter(filters);
  if (key === "quality") return loadQuality();
  if (key === "trip-detail" && state.selectedTrip !== null) return loadTripDetail(state.selectedTrip);
}

// Check whether the returned keys match the documented key list.
function sameKeys(actual, expected) {
  return JSON.stringify(Object.keys(actual || {}).sort()) === JSON.stringify(expected.slice().sort());
}

// Print one endpoint check in the page.
function checkResult(label, passed, details) {
  const item = document.createElement("li");
  item.className = passed ? "check-pass" : "check-fail";
  item.textContent = (passed ? "PASS " : "FAIL ") + label + (details ? " — " + details : "");
  document.getElementById("check-results").appendChild(item);
}

// Call every endpoint once and compare response fields.
async function runContractCheck() {
  document.getElementById("contract-check").hidden = false;
  const list = document.getElementById("check-results");
  list.replaceChildren();
  const get = (path, params) => DashboardApi.get(path, params || {});
  await checkEndpoint("/api/health", () => get("/api/health"), ["status"], null);
  await checkEndpoint("/api/zones", () => get("/api/zones"), ["count", "results"], ["borough", "has_polygon", "map_zone_id", "service_zone", "zone", "zone_id"]);
  await checkEndpoint("/api/zones/geojson", () => get("/api/zones/geojson"), ["crs", "features", "name", "type"], ["geometry", "properties", "type"]);
  let tripId = null;
  await checkEndpoint("/api/trips", async () => {
    const data = await get("/api/trips", { per_page: 1 });
    tripId = data.results[0] ? data.results[0].trip_id : null;
    return data;
  }, ["page", "per_page", "results", "total"], ["distance", "dropoff_datetime", "dropoff_zone", "fare", "passengers", "payment_type", "pickup_datetime", "pickup_zone", "rate_code", "tip", "tolls", "total", "trip_id"]);
  if (tripId === null) checkResult("/api/trips/<id>", false, "no trip was available to request");
  else await checkEndpoint("/api/trips/<id>", () => get("/api/trips/" + encodeURIComponent(tripId)), ["congestion_surcharge", "distance", "dropoff_datetime", "dropoff_zone", "extra", "fare", "improvement_surcharge", "mta_tax", "passengers", "payment_type", "pickup_datetime", "pickup_zone", "rate_code", "store_and_forward", "tip", "tolls", "total", "trip_id", "vendor_id"], null);
  await checkEndpoint("/api/stats/summary", () => get("/api/stats/summary"), ["average_distance", "average_duration_minutes", "average_fare", "busiest_hour", "busiest_hour_trips", "total_amount", "total_tips", "total_trips"], null);
  await checkEndpoint("/api/stats/hourly", () => get("/api/stats/hourly"), ["results"], ["average_duration_minutes", "average_fare", "hour", "trips"]);
  await checkEndpoint("/api/stats/by-zone", () => get("/api/stats/by-zone"), ["count", "results", "zone_type"], ["average_distance", "average_fare", "borough", "has_polygon", "map_zone_id", "service_zone", "trips", "zone", "zone_id"]);
  await checkEndpoint("/api/stats/best-spots", () => get("/api/stats/best-spots", { weekday: 2, hour: 8 }), ["hour", "k", "min_trips", "results", "weekday", "weekday_name"], ["borough", "map_zone_id", "rank", "revenue_per_minute", "trips", "zone", "zone_id"]);
  await checkEndpoint("/api/stats/flat-fare", () => get("/api/stats/flat-fare"), ["airport", "airport_zone", "comparison", "direction", "flat_fare_mean", "flat_fare_mean_below_meter_mean", "flat_fare_trips", "mean_difference_flat_minus_meter", "metered_fare_mean", "metered_trips"], null);
  await checkEndpoint("/api/stats/equity", () => get("/api/stats/equity"), ["limitation", "measure", "results"], ["average_distance", "average_fare", "borough", "trips", "zones"]);
  await checkEndpoint("/api/stats/data-quality", () => get("/api/stats/data-quality"), ["nulls", "rows", "source", "unmatched_zone_ids", "unparseable_values", "unparseable_values_note"], null);
}

// Check top-level keys and, when available, one result item.
async function checkEndpoint(label, request, topKeys, itemKeys) {
  try {
    const data = await request();
    let passed = sameKeys(data, topKeys);
    if (itemKeys) {
      const values = data.results || data.features || [];
      const first = values[0];
      passed = passed && Boolean(first) && sameKeys(first, itemKeys);
      if (label === "/api/zones/geojson") passed = passed && Boolean(first.properties) && "LocationID" in first.properties;
    }
    checkResult(label, passed, passed ? "response fields match" : "received " + Object.keys(data).join(", "));
  } catch (error) {
    checkResult(label, false, error.message);
  }
}

// Connect controls and start mock, contract-check, or live mode.
async function startDashboard() {
  fillTimeOptions();
  bindEvents();
  if (DashboardConfig.check) runContractCheck();
  else {
    await loadZones();
    refreshAll(filterValues() || {});
  }
}

// Attach all keyboard and pointer controls.
function bindEvents() {
  document.getElementById("filters-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const filters = filterValues();
    if (filters) { state.page = 1; refreshAll(filters); }
  });
  document.getElementById("reset-filters").addEventListener("click", resetFilters);
  document.querySelectorAll("#filters-form input, #filters-form select").forEach((input) => {
    input.addEventListener("input", scheduleRefresh);
    input.addEventListener("change", scheduleRefresh);
  });
  document.getElementById("hourly-weekday").addEventListener("change", () => loadHourly(state.filters));
  ["map-metric", "map-zone-type", "map-weekday", "map-hour"].forEach((id) => document.getElementById(id).addEventListener("change", () => loadMap(state.filters)));
  ["weekday-select", "hour-select"].forEach((id) => document.getElementById(id).addEventListener("change", () => loadBestSpots(state.filters)));
  document.getElementById("load-spots-button").addEventListener("click", () => loadBestSpots(state.filters));
  document.getElementById("fare-direction").addEventListener("click", toggleFareDirection);
  document.getElementById("per-page").addEventListener("change", changePageSize);
  document.getElementById("previous-page").addEventListener("click", () => changePage(-1));
  document.getElementById("next-page").addEventListener("click", () => changePage(1));
  document.querySelectorAll("[data-sort]").forEach((button) => button.addEventListener("click", () => sortTrips(button.dataset.sort)));
  document.getElementById("trips-results").addEventListener("click", openTripFromEvent);
  document.getElementById("trips-results").addEventListener("keydown", (event) => { if (event.key === "Enter") openTripFromEvent(event); });
  document.getElementById("close-trip-drawer").addEventListener("click", () => document.getElementById("trip-drawer").close());
  document.getElementById("use-pickup-zone").addEventListener("click", applyMapZone);
  document.querySelectorAll("[data-retry]").forEach((button) => button.addEventListener("click", () => retryWidget(button.dataset.retry)));
}

// Clear all shared filters and reload the page.
function resetFilters() {
  document.getElementById("filters-form").reset();
  state.page = 1;
  clearFilterError();
  const filters = filterValues();
  if (filters) refreshAll(filters);
}

// Change the trip table page size.
function changePageSize(event) {
  state.perPage = Number(event.target.value);
  state.page = 1;
  loadTrips(state.filters);
}

// Move the trip table by one page.
function changePage(direction) {
  state.page = Math.max(1, state.page + direction);
  loadTrips(state.filters);
}

// Toggle the active sort field and order.
function sortTrips(column) {
  state.order = state.sortBy === column && state.order === "desc" ? "asc" : "desc";
  state.sortBy = column;
  state.page = 1;
  loadTrips(state.filters);
}

// Open a trip detail when a table row is activated.
function openTripFromEvent(event) {
  const row = event.target.closest("[data-trip-id]");
  if (row) loadTripDetail(row.dataset.tripId);
}

// Apply a selected map zone to the pickup filter.
function applyMapZone(event) {
  document.getElementById("pickup-zone").value = event.currentTarget.dataset.zoneId;
  const filters = filterValues();
  if (filters) { state.page = 1; refreshAll(filters); }
}

// Switch between supported JFK comparison directions.
function toggleFareDirection(event) {
  state.direction = state.direction === "from_airport" ? "to_airport" : "from_airport";
  event.currentTarget.textContent = state.direction === "from_airport" ? "From airport" : "To airport";
  event.currentTarget.setAttribute("aria-pressed", String(state.direction === "to_airport"));
  loadFlatFare(state.filters);
}

document.addEventListener("DOMContentLoaded", startDashboard);
