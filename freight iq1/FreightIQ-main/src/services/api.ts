import {
  getCongestionSeries,
  getCongestionIndex,
  getPortActivityForAppPort,
  getBerthOccupancy,
  getCargoMix,
  getWaitingVessels,
  getLatestSnapshotDate,
  getAvailableDates,
  fmtShortDate,
} from "./csvData";

const FASTAPI_BASE_URL = "http://127.0.0.1:8000";

export async function testFastAPI() {
  const response = await fetch(`${FASTAPI_BASE_URL}/health`);
  return response.json();
}

export async function fetchPortMap() {
  const response = await fetch(`${FASTAPI_BASE_URL}/ports/map`);

  if (!response.ok) {
    throw new Error(`FastAPI error: ${response.status}`);
  }

  return response.json();
}

export interface CargoInput {
  cargoType: string;
  quantity: number;
  origin: string;
  destination: string;
  vesselPreference: string;
  contractDuration: string;
  laycanDate: string;
  constraints: string;
}

export interface Port {
  id: string;
  name: string;
  state: string;
  lat: number;
  lng: number;
  berths: number;
  maxDraft: number;
  maxLOA: number;
  cargoTypes: string[];
  throughput: string;
  status: "operational" | "congested" | "maintenance";
}

// Port metadata (berths/draft/LOA/throughput) is static infrastructure data, sourced
// from port authority publications — not derived from the CSVs, which don't carry it.
export const EAST_COAST_PORTS: Port[] = [
  { id: "haldia", name: "Haldia", state: "West Bengal", lat: 22.03, lng: 88.07, berths: 24, maxDraft: 8.5, maxLOA: 210, cargoTypes: ["Bulk", "Liquid", "Container"], throughput: "42 MT/year", status: "operational" },
  { id: "sagar", name: "Sagar & Sandheads", state: "West Bengal", lat: 21.65, lng: 88.1, berths: 6, maxDraft: 9.5, maxLOA: 230, cargoTypes: ["Bulk", "Anchorage"], throughput: "12 MT/year", status: "operational" },
  { id: "paradip", name: "Paradip", state: "Odisha", lat: 20.32, lng: 86.61, berths: 18, maxDraft: 14.5, maxLOA: 295, cargoTypes: ["Coal", "Iron Ore", "Fertilizer", "POL"], throughput: "138 MT/year", status: "operational" },
  { id: "dhamra", name: "Dhamra", state: "Odisha", lat: 20.76, lng: 86.9, berths: 8, maxDraft: 17.0, maxLOA: 300, cargoTypes: ["Coal", "Iron Ore", "Limestone"], throughput: "35 MT/year", status: "operational" },
  { id: "gopalpur", name: "Gopalpur", state: "Odisha", lat: 19.27, lng: 84.9, berths: 4, maxDraft: 9.0, maxLOA: 185, cargoTypes: ["Bulk", "General Cargo"], throughput: "8 MT/year", status: "operational" },
  { id: "gangavaram", name: "Gangavaram", state: "Andhra Pradesh", lat: 17.63, lng: 83.22, berths: 10, maxDraft: 21.0, maxLOA: 350, cargoTypes: ["Coal", "Iron Ore", "Bauxite", "Container"], throughput: "58 MT/year", status: "operational" },
  { id: "visakhapatnam", name: "Visakhapatnam", state: "Andhra Pradesh", lat: 17.68, lng: 83.28, berths: 26, maxDraft: 18.0, maxLOA: 320, cargoTypes: ["Coal", "Iron Ore", "Container", "POL", "Fertilizer"], throughput: "72 MT/year", status: "congested" },
];

export function mapFastAPIPortNameToFrontendPort(name: string): Port | undefined {
  const normalizedName =
    name === "Vizag"
      ? "Visakhapatnam"
      : name === "Sagar-Sandheads"
        ? "Sagar & Sandheads"
        : name;

  return EAST_COAST_PORTS.find((p) => p.name === normalizedName);
}

/** Live status per port, computed from the real congestion index (replaces the hardcoded field above). */
export async function getLivePortStatuses(): Promise<Record<string, Port["status"]>> {
  const date = await getLatestSnapshotDate();
  const out: Record<string, Port["status"]> = {};
  for (const p of EAST_COAST_PORTS) {
    const idx = await getCongestionIndex(p.id, p.berths, date);
    out[p.id] = idx === null ? "operational" : idx >= 65 ? "congested" : "operational";
  }
  return out;
}

// ---------------------------------------------------------------------------
// Congestion Pressure Index — REAL data, computed from vessel_snapshots.csv +
// berth_operations.csv (queue length + berth occupancy). This is a directional
// signal, not a $/day freight rate: no rate/price data exists in any source
// file, so a genuine rate forecast cannot be built. See src/services/csvData.ts.
// ---------------------------------------------------------------------------
export interface CongestionForecastData {
  dataAsOf: string;
  historical: { date: string; label: string; index: number }[];
  projected: { date: string; label: string; index: number }[];
  currentIndex: number;
  change7d: number;
  volatility: number;
  vesselsWorking: number;
  vesselsWaiting: number;
  vesselsExpected: number;
  outlook: string;
}

function linearTrendProjection(series: { date: string; index: number }[], daysAhead: number): { date: string; index: number }[] {
  if (series.length < 2) return [];
  const n = series.length;
  const xs = series.map((_, i) => i);
  const ys = series.map((s) => s.index);
  const meanX = xs.reduce((a, b) => a + b, 0) / n;
  const meanY = ys.reduce((a, b) => a + b, 0) / n;
  const num = xs.reduce((acc, x, i) => acc + (x - meanX) * (ys[i] - meanY), 0);
  const den = xs.reduce((acc, x) => acc + (x - meanX) ** 2, 0) || 1;
  const slope = num / den;
  const intercept = meanY - slope * meanX;
  const lastDate = new Date(series[series.length - 1].date + "T00:00:00");
  const out: { date: string; index: number }[] = [];
  for (let d = 1; d <= daysAhead; d++) {
    const projDate = new Date(lastDate);
    projDate.setDate(projDate.getDate() + d);
    const iso = projDate.toISOString().slice(0, 10);
    const val = Math.min(100, Math.max(0, Math.round(intercept + slope * (n - 1 + d))));
    out.push({ date: iso, index: val });
  }
  return out;
}

export async function fetchFreightForecast(port: Port): Promise<CongestionForecastData> {
  const series = await getCongestionSeries(port.id, port.berths);
  const dataAsOf = await getLatestSnapshotDate();
  const activity = await getPortActivityForAppPort(port.id, dataAsOf);

  const projected = linearTrendProjection(series, 7);
  const current = series[series.length - 1]?.index ?? 0;
  const weekAgo = series.length >= 6 ? series[Math.max(0, series.length - 6)].index : series[0]?.index ?? current;
  const change7d = current - weekAgo;
  const deltas = series.slice(1).map((s, i) => s.index - series[i].index);
  const meanDelta = deltas.reduce((a, b) => a + b, 0) / (deltas.length || 1);
  const volatility = Math.sqrt(deltas.reduce((acc, d) => acc + (d - meanDelta) ** 2, 0) / (deltas.length || 1));

  const trendWord = change7d > 5 ? "rising" : change7d < -5 ? "easing" : "holding steady";
  const outlook = `${port.name}'s congestion pressure index is ${trendWord} (${change7d >= 0 ? "+" : ""}${change7d} pts over the last week of captured data). ` +
    `This reflects real vessel-queue and berth-occupancy movement from ${dataAsOf} — it is a directional port-pressure signal, not a freight-rate forecast. ` +
    `No $/day rate feed is connected to this app, so no rate prediction is shown.`;

  return {
    dataAsOf,
    historical: series.map((s) => ({ date: s.date, label: fmtShortDate(s.date), index: s.index })),
    projected: projected.map((s) => ({ date: s.date, label: fmtShortDate(s.date), index: s.index })),
    currentIndex: current,
    change7d,
    volatility: Math.round(volatility * 10) / 10,
    vesselsWorking: activity.working,
    vesselsWaiting: activity.waiting,
    vesselsExpected: activity.expected,
    outlook,
  };
}

// ---------------------------------------------------------------------------
// Market Entry — recommendation derived from the same real congestion signal.
// ---------------------------------------------------------------------------
export interface MarketEntryData {
  recommendation: "BOOK NOW" | "MONITOR" | "WAIT";
  confidence: number;
  currentCongestionIndex: number;
  change7d: number;
  dataAsOf: string;
  rationale: string[];
}

export async function fetchMarketEntry(port: Port): Promise<MarketEntryData> {
  const forecast = await fetchFreightForecast(port);
  const idx = forecast.currentIndex;
  const trend = forecast.change7d;

  let recommendation: MarketEntryData["recommendation"] = "MONITOR";
  if (idx < 40 && trend <= 5) recommendation = "BOOK NOW";
  else if (idx >= 65 || trend > 15) recommendation = "WAIT";

  // Confidence reflects data completeness (how many of the 12 real snapshot
  // dates we actually have for this port), not a model's self-reported score.
  const dates = await getAvailableDates();
  const seriesLen = forecast.historical.length;
  const confidence = Math.round((seriesLen / dates.length) * 100);

  const rationale = [
    `Congestion Pressure Index at ${port.name}: ${idx}/100 as of ${forecast.dataAsOf} (${trend >= 0 ? "+" : ""}${trend} pts over the last week of data).`,
    `${forecast.vesselsWaiting} vessel(s) currently waiting vs. ${forecast.vesselsWorking} working — real counts from vessel_snapshots.csv.`,
    `${forecast.vesselsExpected} vessel(s) expected to arrive in the current data window.`,
    `Based on ${seriesLen} of ${dates.length} captured snapshot dates (${confidence}% data coverage) — no live rate feed factored in.`,
  ];

  return { recommendation, confidence, currentCongestionIndex: idx, change7d: trend, dataAsOf: forecast.dataAsOf, rationale };
}

// ---------------------------------------------------------------------------
// Vessel Optimizer — port draft/LOA constraints are real (EAST_COAST_PORTS).
// The available-vessel fleet below is illustrative: no live chartering/fixture
// feed is connected, so specific vessel names/day-rates are example options,
// clearly flagged in the UI rather than presented as live market data.
// ---------------------------------------------------------------------------
export interface VesselOption {
  name: string;
  type: string;
  dwt: number;
  draft: number;
  loa: number;
  dailyRate: number;
  availability: string;
  suitabilityScore: number;
  flags: string[];
}
export interface VesselData {
  recommended: VesselOption;
  alternatives: VesselOption[];
  draftConstraintMet: boolean;
  loaConstraintMet: boolean;
  cargoSuitability: number;
  isIllustrative: true;
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function fetchVesselData(port: Port, cargo: CargoInput): Promise<VesselData> {
  await delay(150);
  const candidates: VesselOption[] = [
    { name: "MV Kaveri Star", type: "Supramax", dwt: 57000, draft: 12.5, loa: 196, dailyRate: 18200, availability: "Available on request", suitabilityScore: 96, flags: ["Best Value", "Draft Compliant", "Port Familiar"] },
    { name: "MV Eastern Horizon", type: "Panamax", dwt: 75000, draft: 13.8, loa: 225, dailyRate: 22500, availability: "Available on request", suitabilityScore: 82, flags: ["Higher Capacity"] },
    { name: "MV Coastal Pride", type: "Handymax", dwt: 45000, draft: 11.2, loa: 183, dailyRate: 14800, availability: "Available on request", suitabilityScore: 78, flags: ["Fast Available", "Lower Cost"] },
    { name: "MV Bengal Queen", type: "Supramax", dwt: 58000, draft: 12.8, loa: 199, dailyRate: 19100, availability: "Available on request", suitabilityScore: 91, flags: ["High Capacity", "EC India Expert"] },
  ];
  const scored = candidates.map((v) => {
    const draftOk = v.draft <= port.maxDraft;
    const loaOk = v.loa <= port.maxLOA;
    const penalty = (draftOk ? 0 : 20) + (loaOk ? 0 : 20);
    return { ...v, suitabilityScore: Math.max(0, v.suitabilityScore - penalty), draftOk, loaOk };
  }).sort((a, b) => b.suitabilityScore - a.suitabilityScore);

  const [recommended, ...alternatives] = scored;
  return {
    recommended,
    alternatives,
    draftConstraintMet: recommended.draftOk,
    loaConstraintMet: recommended.loaOk,
    cargoSuitability: Math.min(99, recommended.suitabilityScore + 3),
    isIllustrative: true,
  };
}

// ---------------------------------------------------------------------------
// Idle Scenario Analysis — idle-day math is real once you supply a day rate
// (no rate feed exists, so the rate is a user-editable assumption, not a
// fetched number). Queue context (vessels ahead) comes from real CSV data.
// ---------------------------------------------------------------------------
export interface IdleScenario { days: number; idleCost: number; recommendation: string; }
export interface IdleScenarioData {
  assumedDailyRate: number;
  vesselsWaitingAhead: number;
  dataAsOf: string;
  scenarios: IdleScenario[];
}

export async function fetchIdleAnalysis(port: Port, assumedDailyRate: number): Promise<IdleScenarioData> {
  const dataAsOf = await getLatestSnapshotDate();
  const waiting = await getWaitingVessels(port.id, dataAsOf);
  const days = [7, 14, 21];
  const scenarios: IdleScenario[] = days.map((d) => {
    const idleCost = assumedDailyRate * d;
    const recommendation =
      waiting.length === 0
        ? "No vessels currently queued at this port — idling carries limited queue-position risk."
        : waiting.length <= 2
          ? `${waiting.length} vessel(s) ahead in queue — moderate risk of losing berth priority.`
          : `${waiting.length} vessels already queued — idling ${d} days risks falling further back in the berth line.`;
    return { days: d, idleCost, recommendation };
  });
  return { assumedDailyRate, vesselsWaitingAhead: waiting.length, dataAsOf, scenarios };
}

// ---------------------------------------------------------------------------
// Risk Monitor — every category below is computed from real CSV data.
// Market Risk (BDI/C5TC-style volatility) is intentionally NOT shown as a
// score: no rate feed is connected, so it's surfaced as "data unavailable"
// rather than a fabricated number.
// ---------------------------------------------------------------------------
export interface RiskCategory { label: string; score: number; trend: "up" | "down" | "stable"; factors: string[]; }
export interface RiskAlert { severity: "high" | "medium" | "low"; message: string; }
export interface RiskData {
  overall: number;
  dataAsOf: string;
  categories: RiskCategory[];
  marketRiskAvailable: false;
  alerts: RiskAlert[];
}

export async function fetchRiskData(port: Port): Promise<RiskData> {
  const dataAsOf = await getLatestSnapshotDate();
  const forecast = await fetchFreightForecast(port);
  const occ = await getBerthOccupancy(port.id, port.berths, dataAsOf);
  const mix = await getCargoMix(port.id, dataAsOf);
  const dates = await getAvailableDates();

  const congestionScore = forecast.currentIndex;
  const congestionTrend: RiskCategory["trend"] = forecast.change7d > 5 ? "up" : forecast.change7d < -5 ? "down" : "stable";

  const berthScore = occ ? occ.occupancyPct : 50;
  const berthTrend: RiskCategory["trend"] = "stable";

  const totalMt = mix.reduce((a, c) => a + c.totalMt, 0);
  const demandScore = Math.min(100, Math.round((totalMt / 200000) * 100));

  // Expected 12 dates across Aug 10-31; gaps in capture reduce recency confidence.
  const expectedSpanDays = 22;
  const recencyScore = Math.round(100 - (dates.length / expectedSpanDays) * 100);

  const categories: RiskCategory[] = [
    { label: "Port Congestion Risk", score: congestionScore, trend: congestionTrend, factors: [`Waiting vessels: ${forecast.vesselsWaiting}`, `Working vessels: ${forecast.vesselsWorking}`, occ ? `Berth occupancy: ${occ.occupancyPct}%` : "Berth occupancy: no vacancy log for this port"] },
    { label: "Berth Availability Risk", score: berthScore, trend: berthTrend, factors: occ ? [`${occ.occupied}/${occ.total} berths occupied`, `${occ.vacant} berths vacant`, `As of ${dataAsOf}`] : ["Berth data unavailable for this port"] },
    { label: "Demand Volume Risk", score: demandScore, trend: "stable", factors: mix.slice(0, 3).map((m) => `${m.category}: ${m.totalMt.toLocaleString()} MT (${m.vesselCount} vessels)`) },
    { label: "Data Recency Risk", score: recencyScore, trend: "stable", factors: [`${dates.length} of ${expectedSpanDays} calendar days captured`, `Latest snapshot: ${dataAsOf}`, "Gaps reduce confidence in day-to-day trend reads"] },
  ];

  const overall = Math.round(categories.reduce((a, c) => a + c.score, 0) / categories.length);

  const alerts: RiskAlert[] = [];
  if (congestionScore >= 65) alerts.push({ severity: "high", message: `Port congestion at ${port.name} — Congestion Pressure Index ${congestionScore}/100.` });
  if (occ && occ.occupancyPct >= 90) alerts.push({ severity: "medium", message: `Berth occupancy at ${port.name} is ${occ.occupancyPct}% — limited free berths.` });
  if (dates.length < expectedSpanDays) alerts.push({ severity: "low", message: `Only ${dates.length} of ${expectedSpanDays} days captured in this data window — treat trend reads as directional.` });
  alerts.push({ severity: "low", message: "Market Risk (rate volatility) unavailable — no external freight-rate feed connected to this app." });

  return { overall, dataAsOf, categories, marketRiskAvailable: false, alerts };
}
