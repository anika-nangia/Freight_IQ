from datetime import date

from pydantic import BaseModel


class BdiPoint(BaseModel):
    date: date
    price: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    change_pct: float | None = None


class BdiHistoryResponse(BaseModel):
    series: str = "BDI"
    unit: str = "index points"
    count: int
    data: list[BdiPoint]


class Momentum(BaseModel):
    window_days: int
    percent: float | None
    base_date: date | None
    base_price: float | None
    definition: str


class BdiSummary(BaseModel):
    series: str = "BDI"
    latest_date: date
    latest_price: float
    previous_price: float | None
    momentum_14d: Momentum
    percentile_in_history: float
    high_365d: float
    low_365d: float
    observations: int
    first_date: date
    scope_note: str


class SeriesInfo(BaseModel):
    id: str
    name: str
    first_date: date
    last_date: date
    observations: int


class FreightCatalogue(BaseModel):
    series: list[SeriesInfo]
    port_level_data_available: bool
    note: str
