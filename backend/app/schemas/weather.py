from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

PORT_NAME_PATTERN = r"^[A-Za-z][A-Za-z .&'-]{1,59}$"
RISK_DISCLAIMER = (
    "FreightIQ internal decision-support indicator; "
    "not an official maritime safety classification."
)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class CurrentWeather(BaseModel):
    observed_at: str | None = None
    temperature_c: float | None = None
    humidity_percent: float | None = None
    precipitation_mm: float | None = None
    wind_speed_kmh: float | None = None
    wind_gust_kmh: float | None = None
    wind_direction_deg: float | None = None
    visibility_m: float | None = None
    weather_code: int | None = None


class ForecastPoint(BaseModel):
    datetime: str
    precipitation_probability: float | None = None
    precipitation_mm: float | None = None
    wind_speed_kmh: float | None = None
    wind_gust_kmh: float | None = None
    visibility_m: float | None = None
    weather_code: int | None = None


class RiskFactor(BaseModel):
    factor: str
    value: float | int
    unit: str
    impact: RiskLevel
    points: int
    detail: str | None = None


class WeatherRisk(BaseModel):
    score: int | None = Field(default=None, ge=0, le=100)
    level: RiskLevel = RiskLevel.UNKNOWN
    factors: list[RiskFactor] = Field(default_factory=list)
    disclaimer: str = RISK_DISCLAIMER


class PortWeatherResponse(BaseModel):
    port: str
    coordinates: Coordinates
    available: bool
    message: str | None = None
    current: CurrentWeather | None = None
    forecast: list[ForecastPoint] = Field(default_factory=list)
    risk: WeatherRisk = Field(default_factory=WeatherRisk)
    provider: str = "Open-Meteo"
    fetched_at: datetime


class PortWeatherRequest(BaseModel):
    port: str = Field(pattern=PORT_NAME_PATTERN)


class PortInfo(BaseModel):
    name: str
    state: str
    latitude: float
    longitude: float
