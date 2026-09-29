"""BDI trend forecast with 95% intervals and walk-forward validation."""
import logging

import pandas as pd

from app.data.loaders import load_bdi
from app.errors import InvalidParameterError
from app.forecasting.model import fit_trend, predict
from app.forecasting.validation import walk_forward
from app.schemas.forecast import (
    BacktestMetrics,
    DataCoverage,
    ForecastPoint,
    ForecastResponse,
    HistoricalPoint,
    ModelInfo,
)
from app.services.freight_service import SCOPE_NOTE

logger = logging.getLogger(__name__)

DEFAULT_WINDOW = 60
DEFAULT_HORIZON = 14
MIN_WINDOW = 20
MAX_WINDOW = 250
MAX_HORIZON = 60
BACKTEST_STEP = 5
MIN_BACKTEST_FOLDS = 20
HISTORY_POINTS = 180
ROUND_DP = 2


def _validate(window: int, horizon: int) -> None:
    if not MIN_WINDOW <= window <= MAX_WINDOW:
        raise InvalidParameterError(f"window must be between {MIN_WINDOW} and {MAX_WINDOW}.")
    if not 1 <= horizon <= MAX_HORIZON:
        raise InvalidParameterError(f"horizon must be between 1 and {MAX_HORIZON}.")


def build_forecast(window: int = DEFAULT_WINDOW, horizon: int = DEFAULT_HORIZON) -> ForecastResponse:
    _validate(window, horizon)
    frame = load_bdi()
    required = window + horizon + MIN_BACKTEST_FOLDS * BACKTEST_STEP
    if len(frame) < required:
        return ForecastResponse(
            status="insufficient_data",
            message=(f"Need at least {required} observations for window={window}, "
                     f"horizon={horizon}; dataset has {len(frame)}."),
            scope_note=SCOPE_NOTE,
        )

    values = frame["price"].to_numpy(dtype=float)
    backtest = walk_forward(values, window, horizon, BACKTEST_STEP)
    if backtest is None or backtest.folds < MIN_BACKTEST_FOLDS:
        return ForecastResponse(
            status="insufficient_data",
            message="Not enough history to run a reliable walk-forward backtest.",
            scope_note=SCOPE_NOTE,
        )

    fit = fit_trend(values[-window:])
    mean, lower, upper = predict(fit, horizon)
    last_date = frame["date"].iloc[-1]
    dates = pd.bdate_range(last_date + pd.Timedelta(days=1), periods=horizon)

    warnings: list[str] = []
    if backtest.beats_naive is False:
        warnings.append(
            "On the walk-forward backtest this trend model did not beat a naive "
            "last-value forecast; treat the projection with caution."
        )
    if backtest.ci_coverage < 90:
        warnings.append(
            f"The 95% interval contained only {backtest.ci_coverage:.0f}% of backtest "
            "outcomes, so it is narrower than real-world uncertainty."
        )

    recent = frame.tail(HISTORY_POINTS)
    return ForecastResponse(
        status="ok",
        data=DataCoverage(first_date=frame["date"].iloc[0].date(), last_date=last_date.date(),
                          observations=len(frame)),
        model=ModelInfo(window_observations=window, horizon_business_days=horizon,
                        slope_per_observation=round(fit.slope, ROUND_DP),
                        residual_std_error=round(fit.residual_std, ROUND_DP)),
        historical=[HistoricalPoint(date=r.date.date(), value=float(r.price)) for r in recent.itertuples()],
        forecast=[ForecastPoint(date=d.date(), value=round(float(m), ROUND_DP),
                                lower=round(float(lo), ROUND_DP), upper=round(float(hi), ROUND_DP))
                  for d, m, lo, hi in zip(dates, mean, lower, upper)],
        metrics=BacktestMetrics(
            folds=backtest.folds,
            mape=None if backtest.mape is None else round(backtest.mape, ROUND_DP),
            mae=round(backtest.mae, ROUND_DP),
            rmse=round(backtest.rmse, ROUND_DP),
            directional_accuracy=None if backtest.directional_accuracy is None
            else round(backtest.directional_accuracy, ROUND_DP),
            ci_coverage=round(backtest.ci_coverage, ROUND_DP),
            naive_mape=None if backtest.naive_mape is None else round(backtest.naive_mape, ROUND_DP),
            naive_mae=round(backtest.naive_mae, ROUND_DP),
            beats_naive=backtest.beats_naive,
        ),
        warnings=warnings,
        scope_note=SCOPE_NOTE,
    )
