
const API_BASE_URL =
    "https://bug-free-goldfish-5gp6g6gw659624gw9-5000.app.github.dev";

// Load taxi-zone information
async function loadTaxiZones() {
    const insightCopy = document.getElementById("insight-copy");

    try {
        const response = await fetch(`${API_BASE_URL}/api/zones`);

        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }

        const data = await response.json();

        console.log("Taxi zones loaded successfully:", data);

        if (insightCopy) {
            insightCopy.textContent =
                `Taxi zone data loaded successfully. The dataset contains ${data.count} zones.`;
        }
    } catch (error) {
        console.error("Could not load taxi zones:", error);

        if (insightCopy) {
            insightCopy.textContent =
                "Could not load taxi-zone data. Please check that the API is running.";
        }
    }
}

// Load Best Pickup Spots
async function loadBestSpots() {
    const weekday = document.getElementById("weekday-select")?.value;
    const hour = document.getElementById("hour-select")?.value;
    const resultsTable = document.getElementById("spots-results");
    const statusMessage = document.getElementById("spots-status");
    const loadButton = document.getElementById("load-spots-button");

    if (!weekday || hour === undefined || !resultsTable || !statusMessage) {
        console.error("Best Pickup Spots elements could not be found.");
        return;
    }

    statusMessage.textContent = "Loading sample pickup spots...";
    resultsTable.innerHTML =
        '<tr><td colspan="5">Loading results...</td></tr>';

    if (loadButton) {
        loadButton.disabled = true;
    }

    try {
        const url =
            `${API_BASE_URL}/api/stats/best-spots` +
            `?weekday=${encodeURIComponent(weekday)}` +
            `&hour=${encodeURIComponent(hour)}&k=5`;

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }

        const data = await response.json();

        const spots = Array.isArray(data)
            ? data
            : data.results || data.spots || data.data || [];

        if (spots.length === 0) {
            resultsTable.innerHTML =
                '<tr><td colspan="5">No results returned.</td></tr>';
            statusMessage.textContent =
                "No sample results are available for this selection.";
            return;
        }

        resultsTable.innerHTML = "";

        spots.forEach((spot, index) => {
            const row = document.createElement("tr");

            const values = [
                spot.rank ?? index + 1,
                spot.zone ?? spot.zone_name ?? spot.zone_id ?? "Unknown",
                spot.borough ?? "Unknown",
                spot.revenue_per_minute ?? "—",
                spot.trips ?? "—"
            ];

            values.forEach((value) => {
                const cell = document.createElement("td");
                cell.textContent = String(value);
                row.appendChild(cell);
            });

            resultsTable.appendChild(row);
        });

        statusMessage.textContent =
            `Showing ${spots.length} sample result(s). These are demonstration values, not verified real-world rankings.`;

    } catch (error) {
        console.error("Could not load Best Pickup Spots:", error);

        resultsTable.innerHTML =
            '<tr><td colspan="5">Could not load results. Check the API connection.</td></tr>';

        statusMessage.textContent =
            "Unable to load pickup spots. Please try again.";
    } finally {
        if (loadButton) {
            loadButton.disabled = false;
        }
    }
}

// Start the dashboard after the page loads
document.addEventListener("DOMContentLoaded", () => {
    loadTaxiZones();

    const loadButton = document.getElementById("load-spots-button");

    if (loadButton) {
        loadButton.addEventListener("click", loadBestSpots);
    }
});
