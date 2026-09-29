"""Fetch, normalise, cache and score port weather from Open-Meteo."""
import logging
import math
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.data.ports import Port, find_port
from app.errors import PortNotFoundError, ProviderError, ProviderInvalidResponseError
from app.schemas.weather import (
    Coordinates,
    CurrentWeather,
    ForecastPoint,
    PortWeatherResponse,
    WeatherRisk,
)
from app.services.weather_risk import calculate_weather_risk
from app.utils.cache import TTLCache
from app.utils.http_client import fetch_json

logger = logging.getLogger(__name__)

PROVIDER_NAME = "Open-Meteo"
UNAVAILABLE_MESSAGE = "Weather data is temporarily unavailable."
FORECAST_STEP_HOURS = 3
RISK_WINDOW_HOURS = 72
TIMEZONE = "Asia/Kolkata"

CURRENT_VARIABLES = (
    "temperature_2m", "relative_humidity_2m", "precipitation", "weather_code",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m", "visibility",
)
HOURLY_VARIABLES = (
    "precipitation_probability", "precipitation", "wind_speed_10m",
    "wind_gusts_10m", "weather_code", "visibility",
)

_cache: TTLCache[PortWeatherResponse] = TTLCache()


def clear_cache() -> None:
    _cache.clear()


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return None if math.isnan(value) or math.isinf(value) else float(value)


def _int(value: Any) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def _at(series: list[Any], index: int) -> Any:
    return series[index] if index < len(series) else None


def _build_params(port: Port, days: int) -> dict[str, Any]:
    return {
        "latitude": port.latitude,
        "longitude": port.longitude,
        "current": ",".join(CURRENT_VARIABLES),
        "hourly": ",".join(HOURLY_VARIABLES),
        "forecast_days": days,
        "timezone": TIMEZONE,
        "wind_speed_unit": "kmh",
    }


def _parse_current(raw: dict[str, Any]) -> CurrentWeather | None:
    current = CurrentWeather(
        observed_at=raw.get("time") if isinstance(raw.get("time"), str) else None,
        temperature_c=_num(raw.get("temperature_2m")),
        humidity_percent=_num(raw.get("relative_humidity_2m")),
        precipitation_mm=_num(raw.get("precipitation")),
        wind_speed_kmh=_num(raw.get("wind_speed_10m")),
        wind_gust_kmh=_num(raw.get("wind_gusts_10m")),
        wind_direction_deg=_num(raw.get("wind_direction_10m")),
        visibility_m=_num(raw.get("visibility")),
        weather_code=_int(raw.get("weather_code")),
    )
    metrics = current.model_dump(exclude={"observed_at"})
    return current if any(v is not None for v in metrics.values()) else None


def _parse_hourly(raw: dict[str, Any]) -> list[ForecastPoint]:
    times = raw.get("time")
    if not isinstance(times, list):
        raise ProviderInvalidResponseError("hourly.time missing")
    series = {
        key: raw[key] if isinstance(raw.get(key), list) else []
        for key in HOURLY_VARIABLES
    }
    points: list[ForecastPoint] = []
    for index, stamp in enumerate(times):
        if not isinstance(stamp, str):
            continue
        points.append(
            ForecastPoint(
                datetime=stamp,
                precipitation_probability=_num(
                    _at(series["precipitation_probability"], index)
                ),
                precipitation_mm=_num(_at(series["precipitation"], index)),
                wind_speed_kmh=_num(_at(series["wind_speed_10m"], index)),
                wind_gust_kmh=_num(_at(series["wind_gusts_10m"], index)),
                visibility_m=_num(_at(series["visibility"], index)),
                weather_code=_int(_at(series["weather_code"], index)),
            )
        )
    return points


def _normalise(
    payload: dict[str, Any],
) -> tuple[CurrentWeather | None, list[ForecastPoint]]:
    raw_current = payload.get("current")
    raw_hourly = payload.get("hourly")
    current = _parse_current(raw_current) if isinstance(raw_current, dict) else None
    hourly = _parse_hourly(raw_hourly) if isinstance(raw_hourly, dict) else []
    if current is None and not hourly:
        raise ProviderInvalidResponseError("no usable current or hourly data")
    return current, hourly


def _forecast_window(
    current: CurrentWeather | None, hourly: list[ForecastPoint]
) -> list[ForecastPoint]:
    """Hourly points from the current hour onward, capped at the risk window."""
    marker = current.observed_at[:13] if current and current.observed_at else None
    upcoming = [p for p in hourly if marker is None or p.datetime[:13] >= marker]
    return (upcoming or hourly)[:RISK_WINDOW_HOURS]


def _unavailable(port: Port) -> PortWeatherResponse:
    return PortWeatherResponse(
        port=port.name,
        coordinates=Coordinates(latitude=port.latitude, longitude=port.longitude),
        available=False,
        message=UNAVAILABLE_MESSAGE,
        risk=WeatherRisk(),
        provider=PROVIDER_NAME,
        fetched_at=datetime.now(timezone.utc),
    )


async def get_port_weather(port_name: str) -> PortWeatherResponse:
    """Return weather + risk for a port. Provider failures never raise."""
    settings = get_settings()
    port = find_port(port_name, settings.supported_ports_list)
    if port is None:
        raise PortNotFoundError(port_name)

    logger.info("Weather request started for port=%s", port.name)
    cache_key = f"{port.name}:{settings.weather_forecast_days}"
    cached = _cache.get(cache_key)
    if cached is not None:
        logger.info("Weather cache hit for port=%s", port.name)
        return cached

    try:
        payload = await fetch_json(
            settings.weather_api_base_url,
            _build_params(port, settings.weather_forecast_days),
            settings.weather_request_timeout,
        )
        current, hourly = _normalise(payload)
    except ProviderError as exc:
        logger.warning(
            "Weather unavailable for port=%s (%s)", port.name, type(exc).__name__
        )
        return _unavailable(port)

    window = _forecast_window(current, hourly)
    response = PortWeatherResponse(
        port=port.name,
        coordinates=Coordinates(latitude=port.latitude, longitude=port.longitude),
        available=True,
        current=current,
        forecast=window[::FORECAST_STEP_HOURS],
        risk=calculate_weather_risk(current, window),
        provider=PROVIDER_NAME,
        fetched_at=datetime.now(timezone.utc),
    )
    _cache.set(cache_key, response, settings.weather_cache_ttl)
    logger.info(
        "Weather fetched for port=%s risk=%s", port.name, response.risk.level.value
    )
    return response
