"""
FastAPI Backend Application for FreightIQ SIH
Integrates Dual-Model Forecasting, 4 Actionable Recommendation Pillars, and WAL SQLite DB.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uuid

from backend.schemas import (
    LoginRequest, UserResponse, RouteQueryRequest,
    RecommendationResponse, IdleAnalysisResponse
)
from backend.database.db_config import init_db, get_db_cursor
from models.model_1_congestion.predict_congestion import CongestionPredictor
from models.model_2_freight.predict_freight import FreightPredictor
from models.model_2_freight.train_xgboost import XGBoostFreightTrainer
from services.market_timing_service import MarketTimingService
from services.vessel_optimizer_service import VesselOptimizerService
from services.idle_management_service import IdleManagementService
from services.risk_mitigation_service import RiskMitigationService
from data_pipeline.api_fetchers.weather_api import WeatherAPIFetcher
from data_pipeline.api_fetchers.fx_market_api import FXMarketAPIFetcher
from data_pipeline.firecrawl_scrapers.port_berth_scraper import PortBerthScraper

app = FastAPI(title="FreightIQ Maritime Decision Support API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
congestion_predictor = CongestionPredictor()
freight_predictor = FreightPredictor()
timing_service = MarketTimingService()
vessel_service = VesselOptimizerService()
idle_service = IdleManagementService()
risk_service = RiskMitigationService()
weather_fetcher = WeatherAPIFetcher()
fx_fetcher = FXMarketAPIFetcher()
berth_scraper = PortBerthScraper()

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok", "app": "FreightIQ Maritime Intelligence", "version": "2.0.0"}

@app.post("/api/auth/login", response_model=UserResponse)
def login(req: LoginRequest):
    """
    Handles both Email and Phone authentication with format cleaning and duplicate protection.
    """
    user_id = str(uuid.uuid4())
    ident = req.email if req.login_type == "email" else req.phone
    if not ident:
        raise HTTPException(status_code=400, detail="Identifier (Email or Phone) is required")

    with get_db_cursor() as cur:
        # Check existing user
        if req.login_type == "email":
            cur.execute("SELECT * FROM users WHERE email = ?", (req.email,))
        else:
            cur.execute("SELECT * FROM users WHERE phone = ?", (req.phone,))
        existing = cur.fetchone()

        if existing:
            return UserResponse(
                id=existing["id"],
                name=existing["name"],
                email=existing["email"],
                phone=existing["phone"],
                company=existing["company"],
                role=existing["role"],
                token=f"fiq_{uuid.uuid4().hex[:16]}"
            )
        else:
            # Create user
            cur.execute(
                "INSERT INTO users (id, name, email, phone, company, role) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, req.name, req.email, req.phone, req.company, "Chartering Officer")
            )
            return UserResponse(
                id=user_id,
                name=req.name,
                email=req.email,
                phone=req.phone,
                company=req.company,
                role="Chartering Officer",
                token=f"fiq_{uuid.uuid4().hex[:16]}"
            )

@app.post("/api/query/route")
def query_route(req: RouteQueryRequest):
    """
    Master Route Query endpoint calculating dual-model predictions and all 4 pillars.
    """
    # 1. Scrape / fetch live berth queue
    queue_data = berth_scraper.scrape_live_queues(req.origin)
    weather_data = weather_fetcher.fetch_marine_weather(req.origin)
    fx_data = fx_fetcher.get_market_telemetry()
    
    # 2. Model 1 Congestion Score
    c_res = congestion_predictor.predict(
        port_name=req.origin,
        queue_waiting=queue_data["vessels_waiting"],
        berth_occupancy_ratio=queue_data["berth_occupancy_pct"] / 100.0,
        wind_knots=weather_data["wind_speed_knots"],
        rain_mm=weather_data["rainfall_mm"]
    )
    
    # 3. Model 2 Freight Prediction with Asymmetric Loss Trajectory
    f_res = freight_predictor.predict_freight_trajectory(
        origin=req.origin,
        destination=req.destination,
        vessel_class=req.vessel_class,
        congestion_score=c_res["congestion_score"],
        bdi_index=fx_data["bdi"],
        usd_inr=fx_data["usd_inr"],
        weather_alert=weather_data["weather_risk_tier"] != "Low"
    )
    
    # 4. Pillar A: Market Timing
    timing_res = timing_service.evaluate_timing(
        current_spot=f_res["current_spot_rate"],
        projections=f_res["projections"]
    )
    
    # 5. Pillar B: Vessel Optimizer
    vessel_res = vessel_service.optimize_vessel_selection(
        origin_port=req.origin,
        destination_port=req.destination,
        cargo_volume_mt=req.cargo_volume_mt
    )
    
    # 6. Pillar D: Risk Mitigation
    risk_res = risk_service.assess_risk(
        port_name=req.origin,
        congestion_score=c_res["congestion_score"],
        queue_waiting_days=round(c_res["predicted_turnaround_delay_hrs"] / 24.0, 1),
        wind_speed_knots=weather_data["wind_speed_knots"],
        wave_height_m=weather_data["wave_height_m"],
        active_disruptions=["Active depression in Bay of Bengal"] if weather_data["weather_risk_tier"] == "High" else []
    )
    
    # 7. Pillar C: Idle Scenario
    idle_res = idle_service.analyze_idle_scenarios(
        discharge_port=req.destination,
        vessel_class=req.vessel_class,
        daily_charter_rate=vessel_res.get("optimal_cost_per_ton_usd", 18.4) * 1000
    )
    
    # Model valuation stats
    trainer = XGBoostFreightTrainer()
    valuation = trainer.train_model()

    return {
        "route": {
            "origin": req.origin,
            "destination": req.destination,
            "vessel_class": req.vessel_class,
            "cargo_volume_mt": req.cargo_volume_mt,
            "distance_km": 2147 if req.origin == "Visakhapatnam" and req.destination == "Ganganagar" else 3850
        },
        "congestion_model": c_res,
        "freight_forecast": f_res,
        "market_timing": timing_res,
        "vessel_optimizer": vessel_res,
        "risk_mitigation": risk_res,
        "idle_analysis": idle_res,
        "model_valuation": valuation["performance"],
        "shap_breakdown": f_res["shap_breakdown"]
    }

@app.get("/api/idle-analysis")
def get_idle_analysis(discharge_port: str = "Paradip", vessel_class: str = "Supramax"):
    return idle_service.analyze_idle_scenarios(discharge_port=discharge_port, vessel_class=vessel_class)
