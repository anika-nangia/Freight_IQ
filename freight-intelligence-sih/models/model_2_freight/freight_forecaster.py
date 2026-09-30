"""
Freight rate forecaster — XGBoost regression trained on engineered features
(lagged rates, rolling stats, BDI/sub-indices, FX, seasonality, coal import
volume), NOT a plain time-series smoother. This matches the project summary:
"machine learning model (XGBoost) trained on historical freight rates (BDI
and sub-indices), trade routes, vessel types in ports ..., currency exchange
rates, with port infrastructure constraints".

Forecasting future dates with a supervised model is done via a recursive
one-step-ahead strategy: predict day+1, feed that prediction back in to
build day+2's lag features, and so on. Market features we can't know in
advance (BDI, FX) are held at their last observed value for the horizon —
a reasonable MVP assumption; swap for their own sub-forecasts later if
needed.

Usage:
    forecaster = FreightForecaster()
    forecaster.fit(feature_df, target_col="rate_usd_per_tonne")
    points = forecaster.predict(horizon_days=30)
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
import numpy as np
import pandas as pd

from xgboost import XGBRegressor

# Feature columns the model trains on. Must all exist (or be computed) in
# the DataFrame passed to fit()/produced during recursive prediction.
# See app/features/feature_engineering.py::merge_market_features for how
# these get built from raw tables.
FEATURE_COLUMNS = [
    "rate_lag_7d",
    "rate_rolling_mean_14d",
    "rate_rolling_std_14d",
    "bdi",
    "bci",
    "bpi",
    "bsi",
    "bhsi",
    "usd_inr",
    "month_sin",
    "month_cos",
    "day_of_week",
    "coal_import_volume_tonnes",
]


@dataclass
class ForecastPointResult:
    forecast_date: pd.Timestamp
    predicted_rate_usd_per_tonne: float
    lower_bound: float | None
    upper_bound: float | None


class FreightForecaster:
    """XGBoost regressor for next-day freight rate, used recursively to
    produce a multi-day horizon forecast."""

    def __init__(self, **xgb_kwargs):
        params = dict(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=42,
        )
        params.update(xgb_kwargs)
        self.model = XGBRegressor(**params)
        self.residual_std: float = 0.0
        self.last_row: pd.Series | None = None
        self.last_date: pd.Timestamp | None = None
        self.target_col: str = "rate_usd_per_tonne"

    def fit(self, feature_df: pd.DataFrame, target_col: str = "rate_usd_per_tonne") -> "FreightForecaster":
        """feature_df must contain 'record_date', target_col, and (ideally)
        all of FEATURE_COLUMNS — produced by
        app.features.feature_engineering.merge_market_features(). Missing
        feature columns are filled with 0 rather than erroring, so the
        model still trains with partial data (e.g. before coal-import
        volume is wired up) — accuracy improves as more sources come online.
        """
        self.target_col = target_col
        df = feature_df.copy()
        df["record_date"] = pd.to_datetime(df["record_date"])
        df = df.sort_values("record_date")

        for col in FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0
        # coerce to numeric explicitly — a column that's all-None (e.g. an
        # unavailable sub-index) stays dtype 'object' otherwise, which
        # XGBoost rejects outright.
        for col in FEATURE_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].ffill().fillna(0.0)

        train_df = df.dropna(subset=[target_col])
        if len(train_df) < 10:
            raise ValueError(
                f"Need at least 10 labeled rows to train, got {len(train_df)}. "
                f"Ingest more freight_rate_observation history for this route/class."
            )

        X = train_df[FEATURE_COLUMNS]
        y = train_df[target_col]
        self.model.fit(X, y)

        residuals = y - self.model.predict(X)
        self.residual_std = float(residuals.std())

        self.last_row = df.iloc[-1].copy()
        self.last_date = df["record_date"].max()
        self._history = df.set_index("record_date")[target_col]
        return self

    def _step_features(self, row: pd.Series, next_date: pd.Timestamp, recent_rates: list[float]) -> pd.DataFrame:
        """Builds the feature row for one future day, given the running
        window of predicted-so-far rates (for lag/rolling features) and the
        last known market row (BDI/FX held flat — see module docstring)."""
        feat = row.copy()
        feat["month_sin"] = np.sin(2 * np.pi * next_date.month / 12)
        feat["month_cos"] = np.cos(2 * np.pi * next_date.month / 12)
        feat["day_of_week"] = next_date.dayofweek

        window = recent_rates[-14:] if len(recent_rates) >= 1 else [row.get(self.target_col, 0.0)]
        feat["rate_rolling_mean_14d"] = float(np.mean(window))
        feat["rate_rolling_std_14d"] = float(np.std(window)) if len(window) > 1 else 0.0
        feat["rate_lag_7d"] = recent_rates[-7] if len(recent_rates) >= 7 else recent_rates[0]

        out = pd.DataFrame([feat[FEATURE_COLUMNS]])
        for col in FEATURE_COLUMNS:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        return out

    def predict(self, horizon_days: int) -> list[ForecastPointResult]:
        if self.last_row is None:
            raise RuntimeError("Forecaster must be fit() before predict().")

        recent_rates = list(self._history.tail(14).values)
        results = []
        row = self.last_row

        for i in range(1, horizon_days + 1):
            next_date = self.last_date + timedelta(days=i)
            X_next = self._step_features(row, next_date, recent_rates)
            pred = float(self.model.predict(X_next)[0])
            pred = max(0.0, pred)

            recent_rates.append(pred)
            band = self.residual_std * np.sqrt(i) * 1.28  # ~80% band, grows with sqrt(horizon)
            results.append(
                ForecastPointResult(
                    forecast_date=next_date,
                    predicted_rate_usd_per_tonne=pred,
                    lower_bound=max(0.0, pred - band),
                    upper_bound=pred + band,
                )
            )
        return results

    def trend_label(self, horizon_days: int = 14) -> str:
        points = self.predict(horizon_days)
        start, end = points[0].predicted_rate_usd_per_tonne, points[-1].predicted_rate_usd_per_tonne
        if start == 0:
            return "flat"
        if end > start * 1.02:
            return "rising"
        if end < start * 0.98:
            return "falling"
        return "flat"

    def feature_importances(self) -> dict[str, float]:
        """Exposes which inputs actually drive predictions — useful for the
        dashboard/report to show *why* a forecast looks the way it does."""
        importances = self.model.feature_importances_
        return dict(sorted(zip(FEATURE_COLUMNS, importances.tolist()), key=lambda x: -x[1]))