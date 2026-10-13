// Draw zone polygons once and update their colours from API values.
window.DashboardMap = (() => {
  const ns = "http://www.w3.org/2000/svg";
  const width = 760, height = 470, pad = 14;
  let svg, paths = [], geoData, clickZone;
  let rows = [], highlights = [], selected = null;

  // Add a simple SVG element.
  function node(name, attrs = {}, text = "") {
    const item = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([key, value]) => item.setAttribute(key, value));
    if (text) item.textContent = text;
    return item;
  }

  // Keep coordinates from polygon and multipolygon features.
  function rings(geometry) {
    if (geometry.type === "Polygon") return geometry.coordinates;
    return geometry.coordinates.flat();
  }

  // Convert one geometry to a path using a small equirectangular projection.
  function pathFor(geometry, project) {
    return rings(geometry).map((ring) => ring.map((point, index) => {
      const [x, y] = project(point);
      return `${index ? "L" : "M"}${x.toFixed(4)} ${y.toFixed(4)}`;
    }).join(" ") + " Z").join(" ");
  }

  // Build all polygon paths once from the GeoJSON coordinates.
  function makeProjection(features) {
    const points = features.flatMap((feature) => rings(feature.geometry).flat());
    const meanLat = points.reduce((sum, point) => sum + point[1], 0) / Math.max(1, points.length);
    const cosine = Math.cos(meanLat * Math.PI / 180);
    const bounds = points.reduce((box, point) => {
      const x = point[0] * cosine;
      return { minX: Math.min(box.minX, x), maxX: Math.max(box.maxX, x), minY: Math.min(box.minY, point[1]), maxY: Math.max(box.maxY, point[1]) };
    }, { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
    const scale = Math.min((width - pad * 2) / (bounds.maxX - bounds.minX), (height - pad * 2) / (bounds.maxY - bounds.minY));
    return ([lon, lat]) => [pad + (lon * cosine - bounds.minX) * scale, height - pad - (lat - bounds.minY) * scale];
  }

  // Create the SVG and attach the precomputed zone paths.
  function draw(container, geojson, onClick) {
    geoData = geojson;
    clickZone = onClick;
    container.replaceChildren();
    svg = node("svg", { viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": "Taxi zone map" });
    const project = makeProjection(geojson.features);
    paths = geojson.features.map((feature) => {
      const zoneId = Number(feature.properties.LocationID);
      const path = node("path", { d: pathFor(feature.geometry, project), class: "zone-shape", tabindex: "0", role: "button", "data-zone-id": zoneId });
      path.addEventListener("click", () => clickZone?.(zoneId));
      path.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); clickZone?.(zoneId); }
      });
      svg.appendChild(path);
      return path;
    });
    container.appendChild(svg);
    update(rows, "trips", highlights, selected);
  }

  // Find data for an area, letting a real zone owner take priority over its twin.
  function rowFor(zoneId, values, metric) {
    const owner = values.find((row) => Number(row.zone_id) === zoneId);
    if (owner && (metric === undefined || owner[metric] !== null && owner[metric] !== undefined)) return owner;
    const twins = values.filter((row) => Number(row.map_zone_id) === zoneId && (metric === undefined || row[metric] !== null && row[metric] !== undefined));
    twins.sort((first, second) => Number(first.zone_id) - Number(second.zone_id));
    return twins[0] || owner;
  }

  // Change fills, tooltips and highlighted best-spot outlines without rebuilding paths.
  function update(values, metric, bestSpots = [], selectedZone = null) {
    rows = values;
    highlights = bestSpots;
    selected = selectedZone;
    if (!paths.length) return;
    const numeric = values.map((row) => row[metric]).filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value))).map(Number);
    const min = Math.min(...numeric), max = Math.max(...numeric);
    paths.forEach((path) => {
      const zoneId = Number(path.dataset.zoneId);
      const data = rowFor(zoneId, values, metric);
      const rawValue = data ? data[metric] : null;
      const value = rawValue === null || rawValue === undefined ? NaN : Number(rawValue);
      const ratio = Number.isFinite(value) && max !== min ? (value - min) / (max - min) : (Number.isFinite(value) ? 0.5 : -1);
      path.setAttribute("fill", ratio < 0 ? "#d8dde0" : `hsl(${48 - ratio * 42} 72% ${83 - ratio * 30}%)`);
      const isBest = bestSpots.some((spot) => Number(spot.zone_id) === zoneId || Number(spot.map_zone_id) === zoneId);
      path.classList.toggle("is-best-spot", isBest);
      path.classList.toggle("is-selected", Number(selectedZone) === zoneId);
      const title = node("title", {}, data ? `${data.zone}: ${value} ${metric}; ${data.trips} trips` : `Zone ${zoneId}: no data`);
      path.replaceChildren(title);
    });
    document.getElementById("map-min").textContent = numeric.length ? String(min.toFixed(2)) : "–";
    document.getElementById("map-max").textContent = numeric.length ? String(max.toFixed(2)) : "–";
  }

  // Return the chosen zone row for the map detail panel.
  function getZone(zoneId) {
    return rowFor(Number(zoneId), rows) || geoData.features.find((feature) => Number(feature.properties.LocationID) === Number(zoneId))?.properties || null;
  }

  return { draw, update, getZone };
})();
