const API_BASE_URL =
    "https://bug-free-goldfish-5gp6g6gw659624gw9-5000.app.github.dev";

async function loadTaxiZones() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/zones`);

        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }

        const data = await response.json();

        console.log("Taxi zones loaded successfully:", data);
        console.log("Number of zones:", data.count);

        const insightCopy = document.getElementById("insight-copy");

    if (insightCopy) {
        insightCopy.textContent =
            `Taxi zone data loaded successfully. The dataset contains ${data.count} zones.`;
    }
        } catch (error) {
        console.error("Could not load taxi zones:", error);
        }
}

loadTaxiZones();
