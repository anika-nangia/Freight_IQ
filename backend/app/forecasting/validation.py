"""Walk-forward backtest: refit on a rolling window, forecast `horizon` ahead."""
from dataclasses import dataclass

import numpy as np

from app.forecasting import metrics
from app.forecasting.model import fit_trend, predict


@dataclass(frozen=True)
class BacktestResult:
    folds: int
    mape: float | None
    mae: float
    rmse: float
    directional_accuracy: float | None
    ci_coverage: float
    naive_mape: float | None
    naive_mae: float
    beats_naive: bool | None


def walk_forward(
    values: np.ndarray, window: int, horizon: int, step: int
) -> BacktestResult | None:
    actual, forecast, lower, upper, last = [], [], [], [], []
    for origin in range(window - 1, len(values) - horizon, step):
        train = values[origin - window + 1 : origin + 1]
        mean, lo, hi = predict(fit_trend(train), horizon)
        forecast.append(mean[-1])
        lower.append(lo[-1])
        upper.append(hi[-1])
        actual.append(values[origin + horizon])
        last.append(values[origin])
    if not actual:
        return None

    a, f, lo, hi, base = map(np.array, (actual, forecast, lower, upper, last))
    model_mape = metrics.mape(a, f)
    naive_mape = metrics.mape(a, base)
    beats = None if model_mape is None or naive_mape is None else model_mape < naive_mape
    return BacktestResult(
        folds=len(a),
        mape=model_mape,
        mae=metrics.mae(a, f),
        rmse=metrics.rmse(a, f),
        directional_accuracy=metrics.directional_accuracy(base, a, f),
        ci_coverage=metrics.interval_coverage(a, lo, hi),
        naive_mape=naive_mape,
        naive_mae=metrics.mae(a, base),
        beats_naive=beats,
    )
