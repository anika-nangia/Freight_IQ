import numpy as np

from app.forecasting import metrics
from app.forecasting.model import fit_trend, predict
from app.forecasting.validation import walk_forward


def test_fit_recovers_exact_line():
    y = 100 + 2.5 * np.arange(50)
    fit = fit_trend(y)
    assert abs(fit.slope - 2.5) < 1e-9
    mean, lo, hi = predict(fit, 5)
    assert np.allclose(mean, 100 + 2.5 * np.arange(50, 55))
    assert np.all(lo <= mean) and np.all(mean <= hi)


def test_interval_widens_with_horizon():
    rng = np.random.default_rng(0)
    y = 100 + 0.5 * np.arange(80) + rng.normal(0, 5, 80)
    mean, lo, hi = predict(fit_trend(y), 30)
    assert (hi - lo)[-1] > (hi - lo)[0]


def test_floor_prevents_negative_values():
    y = np.linspace(50, 5, 40)
    mean, lo, hi = predict(fit_trend(y), 30)
    assert mean.min() >= 0 and lo.min() >= 0


def test_metrics_known_values():
    a = np.array([100.0, 200.0])
    f = np.array([110.0, 180.0])
    assert abs(metrics.mape(a, f) - 10.0) < 1e-9
    assert metrics.mae(a, f) == 15.0
    assert abs(metrics.rmse(a, f) - np.sqrt(250)) < 1e-9
    last = np.array([100.0, 100.0, 100.0])
    assert metrics.directional_accuracy(last, np.array([110.0, 90.0, 100.0]),
                                        np.array([105.0, 95.0, 120.0])) == 100.0  # flat actual ignored


def test_walk_forward_perfect_on_linear_series():
    result = walk_forward(100 + 2.0 * np.arange(200), window=30, horizon=5, step=5)
    assert result.mape < 1e-6
    assert result.directional_accuracy == 100.0
    assert result.beats_naive is True


def test_walk_forward_none_when_too_short():
    assert walk_forward(np.arange(10.0), window=30, horizon=5, step=5) is None


def test_endpoint_real_data(client):
    body = client.get("/api/forecast/bdi?horizon=10&window=60").json()
    assert body["status"] == "ok"
    assert len(body["forecast"]) == 10
    assert body["forecast"][0]["date"] > body["data"]["last_date"]
    for p in body["forecast"]:
        assert p["lower"] <= p["value"] <= p["upper"]
    m = body["metrics"]
    assert m["folds"] >= 20 and m["mape"] > 0
    assert 0 <= m["directional_accuracy"] <= 100
    assert body["model"]["type"] == "linear_regression_trend"
    assert "not a port" in body["scope_note"].lower() or "not port" in body["scope_note"].lower()


def test_forecast_dates_are_business_days(client):
    from datetime import date
    body = client.get("/api/forecast/bdi").json()
    assert all(date.fromisoformat(p["date"]).weekday() < 5 for p in body["forecast"])


def test_warning_when_model_loses_to_naive(client):
    body = client.get("/api/forecast/bdi").json()
    if body["metrics"]["beats_naive"] is False:
        assert any("naive" in w for w in body["warnings"])


def test_insufficient_data_not_fabricated(client, synthetic_bdi):
    synthetic_bdi(list(range(100, 140)))
    body = client.get("/api/forecast/bdi").json()
    assert body["status"] == "insufficient_data"
    assert body["forecast"] == [] and body["metrics"] is None
    assert body["message"]


def test_synthetic_trend_forecast_and_no_warnings(client, synthetic_bdi):
    synthetic_bdi([1000 + 3 * i for i in range(400)])
    body = client.get("/api/forecast/bdi?horizon=5&window=40").json()
    assert body["status"] == "ok"
    assert abs(body["forecast"][0]["value"] - (1000 + 3 * 400)) < 1
    assert body["metrics"]["beats_naive"] is True
    assert body["warnings"] == []


def test_unknown_series_and_port_names_rejected(client):
    for name in ("Paradip", "capesize"):
        r = client.get(f"/api/forecast/{name}")
        assert r.status_code == 404 and r.json()["error"] == "SERIES_NOT_AVAILABLE"


def test_parameter_validation(client):
    assert client.get("/api/forecast/bdi?horizon=0").status_code == 422
    assert client.get("/api/forecast/bdi?horizon=999").status_code == 422
    assert client.get("/api/forecast/bdi?window=5").status_code == 422
