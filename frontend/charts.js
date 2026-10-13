// Draw charts with basic SVG elements and no extra library.
window.DashboardCharts = (() => {
  const ns = "http://www.w3.org/2000/svg";

  // Make one SVG element with optional text content.
  function element(name, attrs = {}, text = "") {
    const node = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text) node.textContent = text;
    return node;
  }

  // Draw bars and labels for hourly and ranked results.
  function bars(container, rows, labelKey, valueKey, format = (value) => value) {
    container.replaceChildren();
    if (!rows.length) return;
    const width = 640, height = 250, pad = 34;
    const max = Math.max(1, ...rows.map((row) => Number(row[valueKey]) || 0));
    const svg = element("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Bar chart" });
    rows.forEach((row, index) => {
      const slot = (width - pad * 2) / rows.length;
      const barHeight = (Number(row[valueKey]) || 0) / max * (height - 70);
      const x = pad + index * slot + slot * 0.18;
      const y = height - 35 - barHeight;
      const rect = element("rect", { x, y, width: slot * 0.64, height: barHeight, rx: 3, class: "chart-bar" });
      rect.appendChild(element("title", {}, `${row[labelKey]}: ${format(row[valueKey])}`));
      svg.append(rect, element("text", { x: x + slot * 0.32, y: height - 12, "text-anchor": "middle", class: "axis-label" }, String(row[labelKey])));
    });
    container.appendChild(svg);
  }

  // Draw a scatter plot from average distance and fare values.
  function scatter(container, rows) {
    container.replaceChildren();
    const usable = rows.filter((row) => row.average_distance !== null && row.average_fare !== null && row.average_distance !== undefined && row.average_fare !== undefined && Number.isFinite(Number(row.average_distance)) && Number.isFinite(Number(row.average_fare)));
    if (!usable.length) return;
    const width = 640, height = 280, pad = 42;
    const maxX = Math.max(1, ...usable.map((row) => Number(row.average_distance)));
    const maxY = Math.max(1, ...usable.map((row) => Number(row.average_fare)));
    const svg = element("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Average fare by average distance" });
    svg.append(element("line", { x1: pad, y1: height - pad, x2: width - pad, y2: height - pad, class: "axis-line" }));
    svg.append(element("line", { x1: pad, y1: pad, x2: pad, y2: height - pad, class: "axis-line" }));
    usable.forEach((row) => {
      const x = pad + Number(row.average_distance) / maxX * (width - pad * 2);
      const y = height - pad - Number(row.average_fare) / maxY * (height - pad * 2);
      const point = element("circle", { cx: x, cy: y, r: 4, class: "scatter-point" });
      point.appendChild(element("title", {}, `${row.zone}: ${row.average_distance} distance, ${row.average_fare} fare`));
      svg.appendChild(point);
    });
    svg.append(element("text", { x: width / 2, y: height - 5, "text-anchor": "middle", class: "axis-label" }, "Average distance (mi)"));
    svg.append(element("text", { x: 14, y: height / 2, class: "axis-label", transform: `rotate(-90 14 ${height / 2})` }, "Average fare ($)"));
    container.appendChild(svg);
  }

  // Draw the two observed airport fare groups with counts.
  function comparison(container, data, money) {
    const rows = [
      { label: "Flat fare", value: data.flat_fare_mean, trips: data.flat_fare_trips },
      { label: "Metered", value: data.metered_fare_mean, trips: data.metered_trips }
    ];
    container.replaceChildren();
    rows.forEach((row) => {
      const card = document.createElement("div");
      card.className = "fare-compare-item";
      const heading = document.createElement("strong");
      heading.textContent = row.label;
      const value = document.createElement("span");
      value.textContent = `${money(row.value)} · ${row.trips} trips`;
      card.append(heading, value);
      container.appendChild(card);
    });
  }

  return { bars, scatter, comparison };
})();
