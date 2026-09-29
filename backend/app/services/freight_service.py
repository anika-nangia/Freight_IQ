"""Baltic Dry Index history, summary and derived market signals."""
from datetime import date, timedelta

import pandas as pd

from app.data.loaders import load_bdi
from app.errors import InvalidParameterError
from app.schemas.freight import (
    BdiHistoryResponse,
    BdiPoint,
    BdiSummary,
    FreightCatalogue,
    Momentum,
    SeriesInfo,
)
from app.schemas.recommendation import RecommendationRequest

MOMENTUM_WINDOW_DAYS = 14
HIGH_LOW_LOOKBACK_DAYS = 365
MAX_HISTORY_ROWS = 5000
SCOPE_NOTE = (
    "Baltic Dry Index is a global dry-bulk market index. It is a proxy for "
    "market direction, not a port- or route-specific freight rate."
)
MOMENTUM_DEFINITION = (
    "(latest price - price on the last observation on/before 14 calendar days "
    "earlier) / that earlier price x 100. Derived by FreightIQ; not a dataset column."
)
DERIVED_LABEL = "DERIVED_FROM_BDI"


def _nan_to_none(value: float) -> float | None:
    return None if pd.isna(value) else float(value)


def get_catalogue() -> FreightCatalogue:
    frame = load_bdi()
    return FreightCatalogue(
        series=[
            SeriesInfo(
                id="bdi",
                name="Baltic Dry Index",
                first_date=frame["date"].iloc[0].date(),
                last_date=frame["date"].iloc[-1].date(),
                observations=len(frame),
            )
        ],
        port_level_data_available=False,
        note="Only the Baltic Dry Index is loaded. No port- or route-level freight data is available.",
    )


def get_history(
    start: date | None, end: date | None, limit: int | None
) -> BdiHistoryResponse:
    if start and end and start > end:
        raise InvalidParameterError("start_date must not be after end_date.")
    frame = load_bdi()
    if start:
        frame = frame[frame["date"] >= pd.Timestamp(start)]
    if end:
        frame = frame[frame["date"] <= pd.Timestamp(end)]
    if limit:
        frame = frame.tail(min(limit, MAX_HISTORY_ROWS))
    points = [
        BdiPoint(
            date=row.date.date(),
            price=float(row.price),
            open=_nan_to_none(row.open),
            high=_nan_to_none(row.high),
            low=_nan_to_none(row.low),
            change_pct=_nan_to_none(row.change_pct),
        )
        for row in frame.itertuples()
    ]
    return BdiHistoryResponse(count=len(points), data=points)


def compute_momentum(frame: pd.DataFrame, window_days: int = MOMENTUM_WINDOW_DAYS) -> Momentum:
    latest = frame.iloc[-1]
    target = latest["date"] - timedelta(days=window_days)
    earlier = frame[frame["date"] <= target]
    if earlier.empty:
        return Momentum(window_days=window_days, percent=None, base_date=None,
                        base_price=None, definition=MOMENTUM_DEFINITION)
    base = earlier.iloc[-1]
    percent = (latest["price"] / base["price"] - 1) * 100
    return Momentum(
        window_days=window_days,
        percent=round(float(percent), 2),
        base_date=base["date"].date(),
        base_price=float(base["price"]),
        definition=MOMENTUM_DEFINITION,
    )


def compute_percentile(frame: pd.DataFrame) -> float:
    """Share of all observations at or below the latest price (0 = cheapest, 100 = dearest)."""
    latest = frame["price"].iloc[-1]
    return round(float((frame["price"] <= latest).mean() * 100), 1)


def get_summary() -> BdiSummary:
    frame = load_bdi()
    latest = frame.iloc[-1]
    year = frame[frame["date"] >= latest["date"] - timedelta(days=HIGH_LOW_LOOKBACK_DAYS)]
    return BdiSummary(
        latest_date=latest["date"].date(),
        latest_price=float(latest["price"]),
        previous_price=float(frame["price"].iloc[-2]) if len(frame) > 1 else None,
        momentum_14d=compute_momentum(frame),
        percentile_in_history=compute_percentile(frame),
        high_365d=float(year["price"].max()),
        low_365d=float(year["price"].min()),
        observations=len(frame),
        first_date=frame["date"].iloc[0].date(),
        scope_note=SCOPE_NOTE,
    )


def apply_bdi_market_data(
    request: RecommendationRequest,
) -> tuple[RecommendationRequest, dict[str, str]]:
    """Fill missing momentum / rate percentile from BDI. Caller-supplied values win."""
    frame = load_bdi()
    updates: dict[str, float] = {}
    derived: dict[str, str] = {}
    if request.rate_momentum_14d is None:
        momentum = compute_momentum(frame).percent
        if momentum is not None:
            updates["rate_momentum_14d"] = momentum
            derived["rate_momentum_14d"] = DERIVED_LABEL
    if request.freight_rate_percentile is None:
        updates["freight_rate_percentile"] = compute_percentile(frame)
        derived["freight_rate_percentile"] = DERIVED_LABEL
    return request.model_copy(update=updates), derived
