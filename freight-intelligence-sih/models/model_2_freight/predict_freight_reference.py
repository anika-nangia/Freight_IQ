"""
Prediction service: loads a pre-trained per-route XGBoost forecaster if
available (from app/forecasting/artifacts/, produced by train.py),
otherwise builds features and fits one on-the-fly from whatever history
exists in the DB. This means the API works immediately even before a
training job has ever run.
"""

from __future__ import annotations
import pickle
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.forecasting.freight_forecaster import FreightForecaster
from app.forecasting.train import (
    build_features_for_route,
    _route_key,
    MODEL_DIR,
)
from app.schemas.forecast import ForecastResponse, ForecastPoint
from app.constants import VesselClass


def get_forecaster(db: Session, origin_country: str, destination_port: str, vessel_class: VesselClass) -> FreightForecaster:
    key = _route_key(origin_country, destination_port, vessel_class.value)
    artifact_path = Path(MODEL_DIR) / f"{key}.pkl"

    if artifact_path.exists():
        with open(artifact_path, "rb") as f:
            return pickle.load(f)

    features = build_features_for_route(db, origin_country, destination_port, vessel_class.value)
    if len(features) < 10:
        raise ValueError(
            f"Not enough freight-rate history for {origin_country} -> {destination_port} "
            f"({vessel_class.value}) to train an XGBoost forecaster. Need at least 10 "
            f"labeled observations — currently have {len(features)}."
        )
    return FreightForecaster().fit(features)


def forecast_route(
    db: Session,
    origin_country: str,
    destination_port: str,
    vessel_class: VesselClass,
    horizon_days: int = 30,
) -> ForecastResponse:
    forecaster = get_forecaster(db, origin_country, destination_port, vessel_class)
    raw_points = forecaster.predict(horizon_days)
    trend = forecaster.trend_label(min(14, horizon_days))

    points = [
        ForecastPoint(
            forecast_date=p.forecast_date.date(),
            predicted_rate_usd_per_tonne=round(p.predicted_rate_usd_per_tonne, 2),
            lower_bound=round(p.lower_bound, 2) if p.lower_bound is not None else None,
            upper_bound=round(p.upper_bound, 2) if p.upper_bound is not None else None,
        )
        for p in raw_points
    ]

    return ForecastResponse(
        origin_country=origin_country,
        destination_port=destination_port,
        vessel_class=vessel_class,
        generated_at=date.today(),
        points=points,
        model_name="xgboost_v1",
        trend=trend,
    )