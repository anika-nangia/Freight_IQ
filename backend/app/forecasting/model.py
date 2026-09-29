"""Linear-regression trend projection with 95% prediction intervals."""
from dataclasses import dataclass

import numpy as np

Z_95 = 1.96  # normal approximation; windows are >= 20 observations


@dataclass(frozen=True)
class TrendFit:
    slope: float
    intercept: float
    n: int
    residual_std: float
    x_mean: float
    sxx: float


def fit_trend(values: np.ndarray) -> TrendFit:
    n = len(values)
    if n < 3:
        raise ValueError("Need at least 3 observations to fit a trend.")
    x = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x, values, 1)
    residuals = values - (intercept + slope * x)
    residual_std = float(np.sqrt(np.sum(residuals**2) / (n - 2)))
    x_mean = float(x.mean())
    return TrendFit(
        slope=float(slope),
        intercept=float(intercept),
        n=n,
        residual_std=residual_std,
        x_mean=x_mean,
        sxx=float(np.sum((x - x_mean) ** 2)),
    )


def predict(
    fit: TrendFit, steps: int, floor: float = 0.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Forecast steps 1..steps ahead: (mean, lower95, upper95). Values floored at `floor`."""
    xs = np.arange(fit.n, fit.n + steps, dtype=float)
    mean = fit.intercept + fit.slope * xs
    se = fit.residual_std * np.sqrt(1 + 1 / fit.n + (xs - fit.x_mean) ** 2 / fit.sxx)
    return (
        np.maximum(mean, floor),
        np.maximum(mean - Z_95 * se, floor),
        np.maximum(mean + Z_95 * se, floor),
    )
