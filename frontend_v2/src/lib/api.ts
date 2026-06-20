const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function fetchApi(path: string, params: Record<string, any> = {}) {
  try {
    const url = new URL(`${BASE_URL}${path}`);
    Object.keys(params).forEach(key => {
      if (params[key] !== undefined && params[key] !== null) {
        url.searchParams.append(key, String(params[key]));
      }
    });

    const response = await fetch(url.toString(), {
      next: { revalidate: 300 }, // Cache for 5 minutes
    });
    
    if (!response.ok) {
      console.error(`API Error: ${response.status} ${response.statusText}`);
      return null;
    }
    
    return await response.json();
  } catch (error) {
    console.error("API Fetch Error:", error);
    return null;
  }
}

export async function getStats() {
  const data = await fetchApi("/stats");
  return data || {};
}

export async function getPriority(filters = {}) {
  const data = await fetchApi("/priority", filters);
  return data?.priority || [];
}

export async function getHotspots(filters = { limit: 1200 }) {
  const data = await fetchApi("/hotspots", filters);
  return data?.hotspots || [];
}

export async function getForecast(top_n = 20) {
  const data = await fetchApi("/forecast", { top_n });
  return data || { forecast: [] };
}

export async function getPatrol(units = 10) {
  const data = await fetchApi("/patrol", { units });
  return data || { assignments: [], coverage_curve: [] };
}

export async function getStations() {
  const data = await fetchApi("/stations");
  return data?.stations || [];
}

export async function getPoiStats() {
  const data = await fetchApi("/poi-stats");
  return data || { by_category: [] };
}

export async function getJunctions(filters = { min_violations: 50 }) {
  const data = await fetchApi("/junctions", filters);
  return data?.junctions || [];
}
