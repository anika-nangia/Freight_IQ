# FreightIQ Backend: Weather Integration

FastAPI service that fetches port weather from Open-Meteo, converts it into a
transparent 0-100 weather-risk score, and feeds that score into a unified
recommendation as a **risk modifier**. If the weather provider is down, the
dashboard keeps working and weather shows as `UNKNOWN`.

## Architecture

```
Frontend (React/Vite)
   │  GET /api/weather/port/{port}      POST /api/recommendation
   ▼
FastAPI routes (app/api/routes)
   ▼
weather_service ── ports.py (server-side lat/lon) ── TTL cache
   │
   ▼  httpx (timeout, status + JSON validation)
Open-Meteo Forecast API
   ▼
normalise → weather_risk (deterministic score) → PortWeatherResponse
   ▼
recommendation_service (market entry + vessel + berth/demand + weather)
   ▼
decision · summary · risk · weather · explanations · explanation_inputs
```

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `WEATHER_API_BASE_URL` | `https://api.open-meteo.com/v1/forecast` | Provider URL (no API key needed) |
| `WEATHER_REQUEST_TIMEOUT` | `8` | Seconds before giving up on the provider |
| `WEATHER_CACHE_TTL` | `600` | Seconds to cache a successful response (0 = off) |
| `WEATHER_FORECAST_DAYS` | `5` | Forecast horizon (1-7) |
| `CORS_ALLOWED_ORIGINS` | localhost dev origins | Comma-separated frontend origins; add your Vercel URL |
| `SUPPORTED_PORTS` | *(empty = all)* | Restrict to your project's actual ports |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DATA_DIR` | `data` | Folder scanned for dataset CSVs |

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | `{"status": "ok"}` |
| GET | `/api/weather/ports` | Supported ports |
| GET | `/api/weather/port/{port_name}` | Current + forecast weather and risk |
| POST | `/api/weather/port` | Same, body `{"port": "Paradip"}` |
| GET | `/api/freight` | Available freight series (only BDI) |
| GET | `/api/freight/bdi?start_date&end_date&limit` | BDI history (Recharts-ready) |
| GET | `/api/freight/bdi/summary` | Latest, derived 14-day momentum, history percentile, 365d high/low |
| GET | `/api/forecast/bdi?horizon=14&window=60` | Trend forecast, 95% interval, walk-forward metrics |
| POST | `/api/recommendation` | Unified recommendation incl. weather; `use_bdi_market_data: true` fills missing momentum/percentile from BDI |

Unknown port → `404`. Malformed name or out-of-range input → `422`.
Provider failure → `200` with `available: false`, `risk.level: "UNKNOWN"`.

### Example: weather

```json
{
  "port": "Paradip",
  "coordinates": {"latitude": 20.2647, "longitude": 86.6947},
  "available": true,
  "current": {"wind_gust_kmh": 58.0, "visibility_m": 4200.0, "weather_code": 63},
  "forecast": [{"datetime": "2026-09-29T10:00", "precipitation_probability": 74}],
  "risk": {
    "score": 38, "level": "MODERATE",
    "factors": [
      {"factor": "Wind gusts", "value": 58, "unit": "km/h", "impact": "MODERATE", "points": 10}
    ],
    "disclaimer": "FreightIQ internal decision-support indicator; not an official maritime safety classification."
  },
  "provider": "Open-Meteo",
  "fetched_at": "2026-09-29T10:02:11Z"
}
```

### Example: recommendation request

All metrics are optional; anything omitted is reported as `UNAVAILABLE`, never
defaulted.

```json
{
  "port_name": "Paradip",
  "congestion_score": 20,
  "freight_rate": 14.2,
  "freight_rate_percentile": 15,
  "rate_momentum_14d": 5.0,
  "berth_availability": 80,
  "demand_volume": 120000,
  "demand_volume_reference": 100000,
  "vessel_compatibility": true
}
```

The response contains `decision` (`CHARTER NOW`, `CHARTER WITH CAUTION`,
`WAIT`, `MONITOR`, `RESOLVE VESSEL COMPATIBILITY`, `INSUFFICIENT DATA`),
`summary`, `market_entry`, `vessel`, `risk`, `weather`, `explanations`,
`explanation_inputs` (structured facts for your AI explainability layer) and
`data_provenance` (PROVIDED_BY_CALLER / REAL_DATA / DERIVED_METRIC / UNAVAILABLE).

`explanations` are rule-based strings and are labelled `explanations_source:
"rule_based"`. They are not AI-generated.

## Data and forecasting (Baltic Dry Index)

Datasets live in `backend/data/` (every `*.csv` there is loaded and de-duplicated by
date). The two supplied files are both the **Baltic Dry Index** (5-year file plus a
3-year file that is an exact subset). There is **no** port-level, route-level,
congestion or vessel data, so those endpoints do not exist yet, and
`/api/forecast/{port}` returns `SERIES_NOT_AVAILABLE`.

- **Model:** linear-regression trend on the last `window` observations, projected
  `horizon` business days, with 95% prediction intervals.
- **Validation:** walk-forward backtest (refit every 5 observations). Reports MAPE,
  MAE, RMSE, directional accuracy, interval coverage, and a naive last-value baseline.
- **14-day momentum** is derived, not a dataset column: see the `definition` field.
- Current backtest (60-obs window, 14-day horizon): MAPE about 24.9% vs 18.1% for the
  naive baseline, directional accuracy about 50%, and 95% interval coverage about 58%.
  The API returns `warnings` when the model loses to the naive baseline.
- BDI is a global proxy. Do not present it as port-specific freight.

## Added: ports, congestion, history, explainability

| Method | Path | Notes |
|---|---|---|
| GET | `/api/ports`, `/api/ports/{port}` | Coordinates from `app/data/ports.py` |
| GET | `/api/congestion` | Latest row per port (scoreboard boxes + port map) |
| GET | `/api/congestion/{port}` , `/history` | Score, freight rate, 14d momentum from the dataset |
| GET/POST/DELETE | `/api/history`, `/api/history/{id}` | SQLite-backed Chrome-style analysis log |
| POST | `/api/explainability` | Structured evidence; `ai_narrative` is null until an AI model is wired in |

Congestion loader matches column names loosely (see `CANDIDATES` in
`app/data/congestion_loader.py`); it has NOT been tested against Aditi's real files.

## Vessel snapshots (vessel_snapshots.csv)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/vessels?port=&status=&snapshot=latest\|all` | Vessel rows, latest snapshot by default |
| GET | `/api/vessels/port/{port}` , `/api/vessels/{id}` | ids are row-based (`v123`), stable only while the CSV is unchanged |
| GET | `/api/ports/{port}/operations` | Working/waiting/expected counts, inbound MT, berth-utilisation PROXY |
| GET | `/api/ports/{port}/queue-history` | Per-snapshot queue counts for charts |

`vessel_dimensions` like `179.90/7.43` is assumed to be LOA(m)/draft(m) - confirm with Aditi.
Only ~7% of rows have `vessel_type`; the rest stay null.

## Working with only BDI + vessel_snapshots.csv

- `/api/congestion*` uses the congestion CSV if present, else falls back to a queue-based index from the
  snapshots (`source: DERIVED_FROM_VESSEL_SNAPSHOTS`). This is NOT the model congestion score.
- `GET /api/risk/{port}` and `POST /api/recommendation` with `use_vessel_snapshot_data: true` fill berth
  availability (100 - utilisation proxy) and demand (expected inbound MT vs port median) - explicit values win.
- `POST /api/vessel/optimize` never returns `compatible: true`; it reports whether the vessel is within
  dimensions/classes *observed* at the port. Only Paradip has parseable LOA/draft in the current file.

## Weather risk score

Score = gusts (≤20) + wind (≤10) + precipitation (≤15) + precipitation
probability (≤10) + visibility (≤15) + severe weather code (≤30) = max 100.
Bands: 0-29 LOW, 30-59 MODERATE, 60-79 HIGH, 80-100 SEVERE. Tiers are named
constants at the top of `app/services/weather_risk.py`. The score uses the worst
conditions over the current reading and the next 72 hours. It is an internal
decision-support indicator, **not** an official maritime safety classification.

## Recommendation logic

Market entry scores congestion, freight-rate percentile and 14-day momentum
(+1/-1 each); ≥2 is FAVOURABLE, ≤-2 is UNFAVOURABLE. Operational risk comes
from berth availability and demand vs. reference. Weather never changes the
market-entry or vessel status; it only raises overall risk and turns
`CHARTER NOW` into `CHARTER WITH CAUTION`. Thresholds are constants in
`app/services/recommendation_service.py`. Align them with your existing logic.

## Frontend integration

Copy `docs/freightiqApi.js` into your frontend, set `VITE_API_BASE_URL`, then
call `getPortWeather(port)` or `getRecommendation(port, metrics)` when a
destination port is selected. Handle `weather.available === false` by showing
"Weather unavailable" instead of a score.

## Tests

```bash
pytest -q
```

The weather provider is mocked; tests never use the network.
