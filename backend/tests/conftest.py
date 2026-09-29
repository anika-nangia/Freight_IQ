from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.data.loaders import clear_dataset_cache
from app.services import weather_service


@pytest.fixture(autouse=True)
def _reset_state():
    get_settings.cache_clear()
    weather_service.clear_cache()
    clear_dataset_cache()
    yield
    get_settings.cache_clear()
    weather_service.clear_cache()
    clear_dataset_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def make_payload(
    *, gust=12.0, wind=8.0, precip=0.0, prob=10.0, visibility=24000.0, code=1, hours=48
) -> dict[str, Any]:
    start = datetime(2026, 9, 29, 0, 0)
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    return {
        "current": {
            "time": "2026-09-29T10:00",
            "temperature_2m": 29.5,
            "relative_humidity_2m": 78,
            "precipitation": precip,
            "weather_code": code,
            "wind_speed_10m": wind,
            "wind_direction_10m": 210,
            "wind_gusts_10m": gust,
            "visibility": visibility,
        },
        "hourly": {
            "time": times,
            "precipitation_probability": [prob] * hours,
            "precipitation": [precip] * hours,
            "wind_speed_10m": [wind] * hours,
            "wind_gusts_10m": [gust] * hours,
            "weather_code": [code] * hours,
            "visibility": [visibility] * hours,
        },
    }


@pytest.fixture
def payload_factory():
    return make_payload


@pytest.fixture
def mock_provider(monkeypatch):
    """Replace the network call. Configure with .payload or .error."""

    class Mock:
        payload: Any = make_payload()
        error: Exception | None = None
        calls = 0

    mock = Mock()

    async def fake_fetch(url, params, timeout):
        mock.calls += 1
        if mock.error:
            raise mock.error
        return mock.payload

    monkeypatch.setattr(weather_service, "fetch_json", fake_fetch)
    return mock


@pytest.fixture
def synthetic_bdi(monkeypatch):
    """Patch the dataset loaders with a caller-supplied price list (business days)."""
    import pandas as pd

    from app.services import forecast_service, freight_service

    def install(prices, start="2025-01-01"):
        dates = pd.bdate_range(start, periods=len(prices))
        frame = pd.DataFrame({
            "date": dates, "price": [float(p) for p in prices],
            "open": float("nan"), "high": float("nan"), "low": float("nan"),
            "change_pct": float("nan"),
        })
        monkeypatch.setattr(forecast_service, "load_bdi", lambda: frame)
        monkeypatch.setattr(freight_service, "load_bdi", lambda: frame)
        return frame

    return install
