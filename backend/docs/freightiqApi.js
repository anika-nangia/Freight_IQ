// Drop into your Vite frontend (e.g. src/services/freightiqApi.js).
// Add VITE_API_BASE_URL=http://localhost:8000 to the frontend .env
const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export const getPortWeather = (port) =>
  request(`/api/weather/port/${encodeURIComponent(port)}`);

export const getSupportedPorts = () => request("/api/weather/ports");

// metrics keys: congestion_score, freight_rate, freight_rate_percentile,
// rate_momentum_14d, berth_availability, demand_volume,
// demand_volume_reference, vessel_compatibility, vessel_compatibility_reason.
// Omit (or send null) anything you don't have: it is treated as UNAVAILABLE.
export const getRecommendation = (port, metrics = {}) =>
  request("/api/recommendation", {
    method: "POST",
    body: JSON.stringify({ port_name: port, ...metrics }),
  });
