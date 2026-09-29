from app.data.ports import PORTS, find_port
from app.errors import ProviderHTTPError, ProviderTimeoutError


def test_valid_port_returns_weather(client, mock_provider):
    response = client.get("/api/weather/port/Paradip")
    assert response.status_code == 200
    body = response.json()
    assert body["port"] == "Paradip"
    assert body["available"] is True
    assert body["provider"] == "Open-Meteo"
    assert body["current"]["wind_gust_kmh"] == 12.0
    assert body["forecast"], "forecast should not be empty"
    assert body["risk"]["level"] == "LOW"
    assert set(body["coordinates"]) == {"latitude", "longitude"}


def test_forecast_starts_from_current_hour_and_is_downsampled(client, mock_provider):
    body = client.get("/api/weather/port/Paradip").json()
    assert body["forecast"][0]["datetime"] == "2026-09-29T10:00"
    assert body["forecast"][1]["datetime"] == "2026-09-29T13:00"


def test_alias_and_case_insensitive_lookup(client, mock_provider):
    assert client.get("/api/weather/port/vizag").json()["port"] == "Visakhapatnam"
    assert client.get("/api/weather/port/paradip").json()["port"] == "Paradip"


def test_unknown_port_404(client, mock_provider):
    response = client.get("/api/weather/port/Atlantis")
    assert response.status_code == 404
    assert mock_provider.calls == 0


def test_malformed_port_name_rejected(client, mock_provider):
    response = client.get("/api/weather/port/Par<script>")
    assert response.status_code == 422
    assert mock_provider.calls == 0


def test_provider_timeout_is_handled(client, mock_provider):
    mock_provider.error = ProviderTimeoutError("t")
    response = client.get("/api/weather/port/Paradip")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["risk"]["level"] == "UNKNOWN"
    assert body["risk"]["score"] is None
    assert body["message"] == "Weather data is temporarily unavailable."


def test_provider_500_is_handled(client, mock_provider):
    mock_provider.error = ProviderHTTPError("500")
    body = client.get("/api/weather/port/Paradip").json()
    assert body["available"] is False


def test_malformed_provider_response_is_handled(client, mock_provider):
    mock_provider.payload = {"unexpected": "shape"}
    body = client.get("/api/weather/port/Paradip").json()
    assert body["available"] is False


def test_hourly_not_a_dict_is_handled(client, mock_provider):
    mock_provider.payload = {"current": "oops", "hourly": ["x"]}
    assert client.get("/api/weather/port/Paradip").json()["available"] is False


def test_null_and_missing_fields_are_tolerated(client, mock_provider, payload_factory):
    payload = payload_factory()
    payload["current"]["visibility"] = None
    del payload["current"]["wind_gusts_10m"]
    payload["hourly"]["wind_gusts_10m"] = [None] * 48
    del payload["hourly"]["visibility"]
    mock_provider.payload = payload
    body = client.get("/api/weather/port/Paradip").json()
    assert body["available"] is True
    assert body["current"]["visibility_m"] is None
    assert body["current"]["wind_gust_kmh"] is None


def test_responses_are_cached(client, mock_provider):
    client.get("/api/weather/port/Paradip")
    client.get("/api/weather/port/Paradip")
    assert mock_provider.calls == 1


def test_failures_are_not_cached(client, mock_provider):
    mock_provider.error = ProviderTimeoutError("t")
    client.get("/api/weather/port/Paradip")
    mock_provider.error = None
    assert client.get("/api/weather/port/Paradip").json()["available"] is True


def test_post_endpoint(client, mock_provider):
    response = client.post("/api/weather/port", json={"port": "Haldia"})
    assert response.status_code == 200
    assert response.json()["port"] == "Haldia"


def test_supported_ports_endpoint(client):
    names = [p["name"] for p in client.get("/api/weather/ports").json()]
    assert "Paradip" in names


def test_supported_ports_env_restriction(client, mock_provider, monkeypatch):
    monkeypatch.setenv("SUPPORTED_PORTS", "Paradip,Haldia")
    assert client.get("/api/weather/port/Chennai").status_code == 404
    assert client.get("/api/weather/port/Haldia").status_code == 200


def test_port_coordinates_are_plausible_east_coast():
    for port in PORTS.values():
        assert 8 <= port.latitude <= 23
        assert 77 <= port.longitude <= 89
    assert find_port("Port of Paradip").name == "Paradip"
