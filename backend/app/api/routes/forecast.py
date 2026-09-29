from typing import Annotated

from fastapi import APIRouter, Query

from app.errors import SeriesNotFoundError
from app.schemas.forecast import ForecastResponse
from app.services import forecast_service as fs

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/{series}", response_model=ForecastResponse)
def forecast(
    series: str,
    horizon: Annotated[int, Query(ge=1, le=fs.MAX_HORIZON)] = fs.DEFAULT_HORIZON,
    window: Annotated[int, Query(ge=fs.MIN_WINDOW, le=fs.MAX_WINDOW)] = fs.DEFAULT_WINDOW,
) -> ForecastResponse:
    if series.lower() != "bdi":
        raise SeriesNotFoundError(
            "Only the Baltic Dry Index ('bdi') is available. "
            "No port- or route-level freight data has been loaded."
        )
    return fs.build_forecast(window=window, horizon=horizon)
