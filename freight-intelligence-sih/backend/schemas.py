"""
Pydantic v2 Schemas for FreightIQ API
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
import re

class LoginRequest(BaseModel):
    login_type: str = Field(..., description="'email' or 'phone'")
    email: Optional[str] = None
    phone: Optional[str] = None
    password_or_otp: str = Field(..., description="Password or 6-digit OTP")
    name: Optional[str] = "SAIL Logistics User"
    company: Optional[str] = "Steel Authority of India Limited (SAIL)"

    @field_validator("email")
    def validate_and_clean_email(cls, v, values):
        if v:
            cleaned = v.strip().lower()
            # Strict RFC-compliant regex
            pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
            if not re.match(pattern, cleaned):
                raise ValueError("Invalid email format. Please provide a standard address, e.g., name@domain.com")
            return cleaned
        return v

    @field_validator("phone")
    def validate_phone(cls, v):
        if v:
            cleaned = re.sub(r"[^\d+]", "", v.strip())
            # Basic validation for 10-digit or +91 standard mobile numbers
            digits = re.sub(r"\D", "", cleaned)
            if len(digits) < 10 or len(digits) > 13:
                raise ValueError("Invalid phone number. Must contain 10 digits (e.g. +91 98765 43210)")
            return cleaned
        return v

class UserResponse(BaseModel):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    company: str
    role: str
    token: str

class RouteQueryRequest(BaseModel):
    origin: str = Field(..., example="Paradip")
    destination: str = Field(..., example="Qingdao")
    vessel_class: str = Field(default="Supramax", example="Supramax")
    cargo_type: str = Field(default="Coking Coal", example="Coking Coal")
    cargo_volume_mt: float = Field(default=55000.0, example=55000.0)
    contract_horizon_days: int = Field(default=30, example=30)
    scenario_weights: Optional[Dict[str, float]] = Field(
        default_factory=lambda: {"weather": 1.0, "congestion": 1.0, "bdi": 1.0, "fx": 1.0}
    )

class ModelValuationMetrics(BaseModel):
    rmse_usd_ton: float
    mae_usd_ton: float
    r2_score: float
    backtest_accuracy_pct: float
    asymmetric_regret_score: float
    regret_reduction_pct: float

class ForecastTrajectoryPoint(BaseModel):
    horizon_days: int
    target_date: str
    projected_rate: float
    lower_bound: float
    upper_bound: float

class RecommendationResponse(BaseModel):
    # Pillar A: Market Timing
    market_timing: Dict[str, Any]
    # Pillar B: Vessel Optimization
    vessel_optimization: Dict[str, Any]
    # Pillar D: Risk Mitigation
    risk_mitigation: Dict[str, Any]
    # Explainability & SHAP
    shap_breakdown: Dict[str, float]
    counterfactual_scenarios: List[Dict[str, Any]]

class IdleAnalysisResponse(BaseModel):
    discharge_port: str
    vessel_class: str
    daily_charter_rate_usd: float
    deadhead_risk_tier: str
    idle_scenarios: List[Dict[str, Any]]
    repositioning_alert: str
    suggested_alternative_ports: List[Dict[str, Any]]
    workers_advisory: str
