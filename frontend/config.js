// Read the dashboard options from the page address.
window.DashboardConfig = (() => {
  const params = new URLSearchParams(window.location.search);
  const apiBase = params.get("api") || "http://127.0.0.1:5000";
  return {
    apiBase: apiBase.replace(/\/$/, ""),
    mock: params.get("mock") === "1",
    check: params.get("check") === "1"
  };
})();
