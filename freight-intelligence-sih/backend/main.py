"""
FastAPI backend for FreightIQ.

What changed, and why
---------------------
The previous main.py called `train_model()` on every /api/query/route request, which
meant an XGBoost fit per request, and it called a berth "scraper" and an FX fetcher
that both returned hardcoded dictionaries. It also hardcoded a distance:

    "distance_km": 2147 if origin == "Visakhapatnam" and destination == "Ganganagar" else 3850

and returned invented freight rates from a dict of made-up base rates.

Now:
  * models are trained offline and loaded read-only; no request triggers a fit;
  * every response carries provenance and a confidence flag;
  * a corridor with no rate history returns `available: false` with the reason,
    rather than a plausible number;
  * distances come from port coordinates, and an unknown pair says so.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database.db_config import init_db, get_db_cursor  # noqa: E402
from backend.schemas import (  # noqa: E402
    LoginRequest, UserResponse, RouteQueryRequest, ContractQueryRequest,
)
from data_pipeline import provenance as prov  # noqa: E402
from models.model_1_congestion.predict_congestion import get_predictor as congestion_predictor  # noqa: E402
from models.model_2_freight.predict_freight import get_predictor as freight_predictor  # noqa: E402
from services.market_timing_service import get_service as timing_service  # noqa: E402
from services.vessel_optimizer_service import get_service as vessel_service  # noqa: E402
from services.idle_management_service import get_service as idle_service  # noqa: E402
from services.risk_mitigation_service import get_service as risk_service  # noqa: E402

ART = ROOT / "models" / "artifacts"
CONGESTION_METRICS = ART / "congestion_metrics.json"
FREIGHT_METRICS = ART / "freight_metrics.json"
PANEL_REPORT = ROOT / "data" / "interim" / "weekly_panel_report.json"
CONGESTION_REPORT = ROOT / "data" / "interim" / "congestion_report.json"
CORRIDOR_REPORT = ROOT / "data" / "interim" / "corridor_table_report.json"

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="FreightIQ Maritime Decision Support API",
    version="3.0.0",
    description="Dry bulk chartering decision support. Every number carries its source; "
                "where a source is missing the API says so instead of estimating.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# --------------------------------------------------------------------------
# health and provenance
# --------------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app": "FreightIQ Maritime Intelligence",
        "version": "3.0.0",
        "models_trained": {
            "model_1_congestion": CONGESTION_METRICS.exists(),
            "model_2_freight": FREIGHT_METRICS.exists(),
        },
        "note": "Metrics are read from files written by the training scripts. No request "
                "trains a model.",
    }


@app.get("/api/data-coverage")
def data_coverage() -> Dict[str, Any]:
    """The data-coverage panel: what is observed, what is derived, what is missing.

    This is the endpoint to point at when someone asks what the system actually knows.
    """
    reports = {
        "route_rates_weekly": _read_json(PANEL_REPORT),
        "congestion": _read_json(CONGESTION_REPORT),
        "corridor_monthly": _read_json(CORRIDOR_REPORT),
    }
    return prov.envelope({
        "datasets": prov.coverage_report(),
        "summary": prov.coverage_by_tier(),
        "limits": {k: v.get("known_limitations", []) for k, v in reports.items() if v},
        "rebuild_commands": [
            "python -m data_pipeline.fetchers.world_bank_prices",
            "python -m data_pipeline.fetchers.open_meteo_weather",
            "python -m data_pipeline.fetchers.frankfurter_fx",
            "python -m data_pipeline.fetchers.bdi_subindices --input <downloaded.csv>",
            "python -m data_pipeline.build_weekly_panel",
            "python -m data_pipeline.build_corridor_table",
            "python -m data_pipeline.build_congestion_dataset",
            "python -m models.model_2_freight.train_freight",
            "python -m models.model_1_congestion.train_congestion",
        ],
    }, list(prov.REGISTRY.keys()))


@app.get("/api/model-report")
def model_report() -> Dict[str, Any]:
    """Validation results for both models, plus their published model cards."""
    m1, m2 = _read_json(CONGESTION_METRICS), _read_json(FREIGHT_METRICS)
    return prov.envelope({
        "model_1_congestion": m1 or {"status": "not trained",
                                     "run": "python -m models.model_1_congestion.train_congestion"},
        "model_2_freight": m2 or {"status": "not trained",
                                 "run": "python -m models.model_2_freight.train_freight"},
        "model_cards": {
            "model_1_congestion": (ART / "congestion_model_card.md").read_text(encoding="utf-8")
            if (ART / "congestion_model_card.md").exists() else None,
            "model_2_freight": (ART / "freight_model_card.md").read_text(encoding="utf-8")
            if (ART / "freight_model_card.md").exists() else None,
        },
    }, ["port_lineups", "route_rates_weekly"])


# --------------------------------------------------------------------------
# corridors
# --------------------------------------------------------------------------
@app.get("/api/corridors")
def list_corridors() -> Dict[str, Any]:
    """Every corridor the system can price, with its observation window."""
    try:
        rows = freight_predictor().available_corridors()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return prov.envelope({"corridors": rows, "count": len(rows)}, ["route_rates_weekly"])


@app.post("/api/query/route")
def query_route(req: RouteQueryRequest) -> Dict[str, Any]:
    """Full decision pack for one corridor and cargo.

    Every section reports `available: false` with a reason if its input is missing.
    No section substitutes a default value for absent data.
    """
    # ---------------------------------------------------- Model 2: rate forecast
    forecast = freight_predictor().forecast(
        req.origin, req.destination, req.vessel_class, cargo_volume_mt=req.cargo_volume_mt)
    contract = (freight_predictor().contract_path(
        req.origin, req.destination, req.vessel_class, n_voyages=req.n_voyages)
        if forecast.get("available") else {"available": False,
                                          "reason": forecast.get("reason")})

    # ------------------------------------------------- Model 1: port congestion
    congestion = congestion_predictor().predict(req.destination)
    weather = congestion.get("weather") if congestion.get("available") else {}

    # --------------------------------------------------------- Pillar A: timing
    timing = timing_service().evaluate(
        forecast, demurrage_usd_per_day=req.demurrage_usd_per_day)
    contract_comparison = (timing_service().compare_contract(contract, req.n_voyages)
                           if contract.get("available") else
                           {"available": False, "reason": contract.get("reason")})

    # ------------------------------------------------------ Pillar B: vessel fit
    vessel = vessel_service().optimize(req.origin, req.destination, req.cargo_volume_mt)

    # ------------------------------------------------------------ Pillar C: idle
    day_rate = req.day_rate_usd
    if day_rate is None and vessel.get("cost_per_ton_usd"):
        # Prefer the class's own published day rate over a derived figure.
        day_rate = _class_day_rate(vessel.get("recommended_vessel"))
    idle = idle_service().analyze(req.destination, req.vessel_class, day_rate_usd=day_rate)

    # ------------------------------------------------------------- Pillar D: risk
    risk = risk_service().assess(req.destination, congestion=congestion, weather=weather)

    return prov.envelope({
        "route": {
            "origin": req.origin,
            "destination": req.destination,
            "vessel_class": req.vessel_class,
            "cargo_type": req.cargo_type,
            "cargo_volume_mt": req.cargo_volume_mt,
        },
        "freight_forecast": forecast,
        "congestion_model": congestion,
        "market_timing": timing,
        "contract_comparison": contract_comparison,
        "vessel_optimizer": vessel,
        "idle_analysis": idle,
        "risk_mitigation": risk,
        "corridor_data": _corridor_table(req.origin, req.destination, req.vessel_class),
        "model_valuation": _valuation(),
    }, ["route_rates_weekly", "port_lineups", "berth_status", "port_constraints",
        "loading_port_constraints", "vessel_specs", "world_bank_pink_sheet", "port_weather"])


def _class_day_rate(vessel_class: Optional[str]) -> Optional[float]:
    if not vessel_class:
        return None
    import pandas as pd
    specs = pd.read_csv(ROOT / "data" / "vessel_specs.csv")
    hit = specs[specs["vessel_class"].astype(str).str.strip().eq(vessel_class)]
    if hit.empty:
        return None
    v = hit.iloc[0].get("cost_index_usd_day")
    return float(v) if pd.notna(v) else None


def _corridor_table(origin: str, destination: str, vessel_class: str) -> Dict[str, Any]:
    """Has this exact corridor ever carried a rate, and for how long?"""
    try:
        rows = freight_predictor().available_corridors()
    except FileNotFoundError:
        return {"available": False, "reason": "panel not built"}
    o, d = str(origin).strip().title(), str(destination).strip().title()
    hit = [r for r in rows
           if r["corridor_id"].lower() == f"{o}->{d}".lower()
           and r["vessel_class"].lower() == str(vessel_class).replace(" ", "").lower()]
    return {"available": bool(hit), "rows": hit}


def _valuation() -> Dict[str, Any]:
    """Validation numbers, read from files. Never recomputed per request."""
    m2, m1 = _read_json(FREIGHT_METRICS), _read_json(CONGESTION_METRICS)
    out: Dict[str, Any] = {}
    if m2:
        w = m2.get("deployed_model")
        c = (m2.get("candidates") or {}).get(w, {})
        out["freight"] = {
            "model": w,
            "validation": m2.get("validation_scheme"),
            "walk_forward_mae_usd_mt": c.get("mae_usd_mt"),
            "walk_forward_rmse_usd_mt": c.get("rmse_usd_mt"),
            "asymmetric_regret": c.get("asym_regret_logret"),
            "regret_reduction_vs_persistence_pct": m2.get("regret_reduction_vs_persistence_pct"),
            "out_of_sample_weeks": m2.get("out_of_sample_weeks"),
            "out_of_sample_rows": m2.get("out_of_sample_rows"),
            "deployed_features": m2.get("features"),
            "features_not_validated": m2.get("features_available_but_not_validated"),
        }
    if m1:
        w = m1.get("deployed_model")
        c = (m1.get("candidates") or {}).get(w, {})
        out["congestion"] = {
            "model": w,
            "validation": m1.get("validation_scheme"),
            "mae_days": c.get("mae_days"),
            "rmse_days": c.get("rmse_days"),
            "beats_port_median_baseline": m1.get("beats_naive_baseline"),
            "margin_is_material": m1.get("margin_is_material"),
            "honest_reading": m1.get("honest_reading"),
        }
    return out


# --------------------------------------------------------------------------
# standalone pillar endpoints
# --------------------------------------------------------------------------
@app.get("/api/idle-analysis")
def idle_analysis(discharge_port: str = "Paradip", vessel_class: str = "Supramax",
                  day_rate_usd: Optional[float] = None) -> Dict[str, Any]:
    return prov.envelope(idle_service().analyze(discharge_port, vessel_class, day_rate_usd),
                         ["port_lineups"])


@app.get("/api/idle-network")
def idle_network() -> Dict[str, Any]:
    rows = idle_service().network_summary()
    return prov.envelope({"ports": rows, "count": len(rows)}, ["port_lineups"])


@app.get("/api/ports")
def ports() -> Dict[str, Any]:
    """Congestion score and modelled turnaround for every port with a line-up."""
    try:
        rows = congestion_predictor().port_summary()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return prov.envelope({
        "ports": rows,
        "count": len(rows),
        "lineup_as_of": congestion_predictor().latest_snapshot_date(),
    }, ["port_lineups", "berth_status", "port_weather"])


@app.get("/api/port/{port_name}")
def port_detail(port_name: str) -> Dict[str, Any]:
    res = congestion_predictor().predict(port_name)
    if not res.get("available"):
        raise HTTPException(status_code=404, detail=res.get("reason"))
    return prov.envelope(res, ["port_lineups", "berth_status", "port_weather"])


@app.get("/api/vessel-compatibility")
def vessel_compatibility(origin: str, destination: str,
                         cargo_volume_mt: float = 55000.0) -> Dict[str, Any]:
    return prov.envelope(
        vessel_service().optimize(origin, destination, cargo_volume_mt),
        ["port_constraints", "loading_port_constraints", "vessel_specs"])


@app.get("/api/reference/ports")
def reference_ports() -> Dict[str, Any]:
    svc = vessel_service()
    return prov.envelope({
        "discharge_ports": svc.discharge_ports(),
        "loading_terminals": svc.loading_terminals(),
    }, ["port_constraints", "loading_port_constraints"])


@app.post("/api/contract/compare")
def contract_compare(req: ContractQueryRequest) -> Dict[str, Any]:
    """Spot every voyage versus fixing N voyages at today's observed rate."""
    path = freight_predictor().contract_path(
        req.origin, req.destination, req.vessel_class, n_voyages=req.n_voyages)
    if not path.get("available"):
        return prov.envelope(path, ["route_rates_weekly"])
    return prov.envelope(timing_service().compare_contract(path, req.n_voyages),
                         ["route_rates_weekly"])


@app.get("/api/fx")
def fx() -> Dict[str, Any]:
    """USD/INR reference rate, for presenting USD figures in INR."""
    path = ROOT / "data" / "external" / "fx_usd_inr.csv"
    if not path.exists():
        return prov.envelope(prov.unavailable(
            "fx_usd_inr", "run python -m data_pipeline.fetchers.frankfurter_fx"), ["fx_usd_inr"])
    import pandas as pd
    df = pd.read_csv(path, parse_dates=["date"])
    last = df.iloc[-1]
    return prov.envelope({
        "usd_inr": float(last["usd_inr"]),
        "as_of": last["date"].strftime("%Y-%m-%d"),
        "source": "ECB reference rate via Frankfurter",
    }, ["fx_usd_inr"])


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------
@app.post("/api/auth/login", response_model=UserResponse)
def login(req: LoginRequest):
    user_id = str(uuid.uuid4())
    ident = req.email if req.login_type == "email" else req.phone
    if not ident:
        raise HTTPException(status_code=400, detail="Identifier (email or phone) is required")

    with get_db_cursor() as cur:
        if req.login_type == "email":
            cur.execute("SELECT * FROM users WHERE email = ?", (req.email,))
        else:
            cur.execute("SELECT * FROM users WHERE phone = ?", (req.phone,))
        existing = cur.fetchone()

    if existing:
        return UserResponse(
            id=existing["id"], name=existing["name"], email=existing["email"],
            phone=existing["phone"], company=existing["company"], role=existing["role"],
            token=f"fiq_{uuid.uuid4().hex[:16]}")

    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, name, email, phone, company, role) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, req.name, req.email, req.phone, req.company, "Chartering Officer"))
    return UserResponse(id=user_id, name=req.name, email=req.email, phone=req.phone,
                        company=req.company, role="Chartering Officer",
                        token=f"fiq_{uuid.uuid4().hex[:16]}")
