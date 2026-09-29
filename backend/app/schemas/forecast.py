from datetime import date

from pydantic import BaseModel, Field


class HistoricalPoint(BaseModel):
    date: date
    value: float


class ForecastPoint(BaseModel):
    date: date
    value: float
    lower: float
    upper: float


class BacktestMetrics(BaseModel):
    folds: int
    mape: float | None
    mae: float
    rmse: float
    directional_accuracy: float | None
    ci_coverage: float
    naive_mape: float | None
    naive_mae: float
    beats_naive: bool | None


class ModelInfo(BaseModel):
    type: str = "linear_regression_trend"
    window_observations: int
    horizon_business_days: int
    confidence_level: float = 0.95
    slope_per_observation: float
    residual_std_error: float


class DataCoverage(BaseModel):
    first_date: date
    last_date: date
    observations: int


class ForecastResponse(BaseModel):
    series: str = "BDI"
    unit: str = "index points"
    status: str
    message: str | None = None
    data: DataCoverage | None = None
    model: ModelInfo | None = None
    historical: list[HistoricalPoint] = Field(default_factory=list)
    forecast: list[ForecastPoint] = Field(default_factory=list)
    metrics: BacktestMetrics | None = None
    warnings: list[str] = Field(default_factory=list)
    scope_note: str
