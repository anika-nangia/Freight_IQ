from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.weather import PORT_NAME_PATTERN, RiskFactor, RiskLevel


class RecommendationRequest(BaseModel):
    """Every metric is optional: missing means UNAVAILABLE, never a fake default."""

    port_name: str = Field(pattern=PORT_NAME_PATTERN)
    congestion_score: float | None = Field(default=None, ge=0, le=100)
    freight_rate: float | None = Field(default=None, ge=0)
    freight_rate_percentile: float | None = Field(
        default=None, ge=0, le=100,
        description="Where the current rate sits in its history (0 = cheapest).",
    )
    rate_momentum_14d: float | None = Field(
        default=None, description="14-day rate change in percent."
    )
    berth_availability: float | None = Field(default=None, ge=0, le=100)
    demand_volume: float | None = Field(default=None, ge=0)
    demand_volume_reference: float | None = Field(
        default=None, gt=0, description="Baseline demand to compare against."
    )
    vessel_compatibility: bool | None = None
    vessel_compatibility_reason: str | None = Field(default=None, max_length=300)
    use_bdi_market_data: bool = Field(
        default=False,
        description="Fill missing momentum / rate percentile from the Baltic Dry Index (proxy).",
    )
    use_vessel_snapshot_data: bool = Field(
        default=False,
        description="Fill missing berth availability / demand from vessel_snapshots.csv (proxies).",
    )


class StatusReason(BaseModel):
    status: str
    reason: str


class RiskSummary(BaseModel):
    overall_level: RiskLevel
    operational_level: RiskLevel
    weather_level: RiskLevel
    weather_score: int | None
    reason: str


class WeatherSummary(BaseModel):
    available: bool
    score: int | None
    level: RiskLevel
    key_factors: list[RiskFactor]
    message: str | None = None
    provider: str
    fetched_at: datetime


class RecommendationResponse(BaseModel):
    port: str
    decision: str
    summary: str
    market_entry: StatusReason
    vessel: StatusReason
    risk: RiskSummary
    weather: WeatherSummary
    explanations: list[str]
    explanations_source: str = "rule_based"
    explanation_inputs: dict[str, Any]
    data_provenance: dict[str, str]
