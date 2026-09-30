"""
Pydantic v2 schemas.

The old `RecommendationResponse` was never used by any route and did not match what
the endpoints actually returned. The request schemas are kept, with the additions the
real predictors need (n_voyages, demurrage rate), and the response schemas describe
what is genuinely returned.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
import re


class LoginRequest(BaseModel):
    login_type: str = Field(..., description="'email' or 'phone'")
    email: Optional[str] = None
    phone: Optional[str] = None
    password_or_otp: str = Field(..., description="Password or 6-digit OTP")
    name: Optional[str] = "SAIL Logistics User"
    company: Optional[str] = "Steel Authority of India Limited (SAIL)"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v:
            cleaned = v.strip().lower()
            pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
            if not re.match(pattern, cleaned):
                raise ValueError("Invalid email format. Provide a standard address, "
                                 "e.g. name@domain.com")
            return cleaned
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v:
            digits = re.sub(r"\D", "", v.strip())
            if len(digits) < 10 or len(digits) > 13:
                raise ValueError("Invalid phone number. Must contain 10 digits (e.g. +91 98765 43210)")
            return re.sub(r"[^\d+]", "", v.strip())
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
    origin: str = Field(..., json_schema_extra={"example": "Xingang"},
                        description="Loading port or terminal. Must match a corridor with "
                                    "observed rate history to receive a forecast.")
    destination: str = Field(..., json_schema_extra={"example": "Paradip"})
    vessel_class: str = Field(default="Supramax",
                              description="Handysize, Handymax, Supramax, Panamax or Capesize")
    cargo_type: str = Field(default="Coking Coal")
    cargo_volume_mt: float = Field(default=55000.0, gt=0)
    n_voyages: int = Field(default=3, ge=1, le=20,
                           description="Voyages to compare spot against a fixed contract")
    demurrage_usd_per_day: float = Field(default=18500.0, gt=0,
                                         description="Your demurrage rate. Used to price the "
                                                     "cost of waiting; not a market value.")
    day_rate_usd: Optional[float] = Field(default=None, gt=0,
                                          description="Vessel day rate, for idle-cost exposure")


class ContractQueryRequest(BaseModel):
    origin: str
    destination: str
    vessel_class: str = "Supramax"
    n_voyages: int = Field(default=3, ge=1, le=20)


class DataCoverageResponse(BaseModel):
    datasets: List[Dict[str, Any]]
    summary: Dict[str, int]


class ModelReportResponse(BaseModel):
    model_1_congestion: Dict[str, Any]
    model_2_freight: Dict[str, Any]


class ProvenanceBlock(BaseModel):
    datasets: List[Dict[str, Any]]
    generated_at: str


class Envelope(BaseModel):
    """Every endpoint returns this shape, or an explicit `available: false`."""
    available: bool = True
    provenance: ProvenanceBlock
    confidence: Optional[Dict[str, Any]] = None
