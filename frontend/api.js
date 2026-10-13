// Build API requests and keep errors readable for the page.
window.DashboardApi = (() => {
  // Get one response from either the API or the mock fixtures.
  async function get(path, params = {}, signal) {
    if (window.DashboardConfig.mock) return window.DashboardMock.get(path, params);
    const url = new URL(`${window.DashboardConfig.apiBase}${path}`);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
    });
    let response;
    try {
      response = await fetch(url, { signal });
    } catch (error) {
      error.isNetworkError = true;
      throw error;
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(body.error?.message || `API request failed with HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  return { get };
})();
