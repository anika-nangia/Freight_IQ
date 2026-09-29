def test_catalogue_states_no_port_level_data(client):
    body = client.get("/api/freight").json()
    assert body["port_level_data_available"] is False
    assert body["series"][0]["id"] == "bdi"
    assert body["series"][0]["observations"] == 1236


def test_history_filters_by_date(client):
    body = client.get("/api/freight/bdi?start_date=2026-09-01&end_date=2026-09-25").json()
    assert body["count"] == len(body["data"]) > 0
    assert all("2026-09-01" <= p["date"] <= "2026-09-25" for p in body["data"])
    assert {"date", "price"} <= set(body["data"][0])


def test_history_limit_returns_latest(client):
    body = client.get("/api/freight/bdi?limit=5").json()
    assert body["count"] == 5
    assert body["data"][-1]["date"] == "2026-09-25"


def test_history_bad_range_and_params(client):
    r = client.get("/api/freight/bdi?start_date=2026-09-25&end_date=2026-09-01")
    assert r.status_code == 422 and r.json()["error"] == "INVALID_PARAMETER"
    assert client.get("/api/freight/bdi?limit=0").status_code == 422
    assert client.get("/api/freight/bdi?start_date=garbage").json()["error"] == "VALIDATION_ERROR"


def test_history_empty_range_is_empty_not_error(client):
    body = client.get("/api/freight/bdi?start_date=2030-01-01").json()
    assert body["count"] == 0


def test_summary_real_data(client):
    body = client.get("/api/freight/bdi/summary").json()
    assert body["latest_price"] == 3426.0
    assert body["momentum_14d"]["base_date"] == "2026-09-11"
    assert body["momentum_14d"]["percent"] == -2.31
    assert 0 <= body["percentile_in_history"] <= 100
    assert "proxy" in body["scope_note"]


def test_momentum_formula_synthetic(client, synthetic_bdi):
    # 30 business days; latest is 110, price 14 calendar days earlier is 100
    prices = [100] * 20 + [110] * 10
    frame = synthetic_bdi(prices)
    body = client.get("/api/freight/bdi/summary").json()
    latest = frame["date"].iloc[-1]
    assert body["momentum_14d"]["percent"] == 10.0
    assert body["momentum_14d"]["base_price"] == 100.0
    assert latest.date().isoformat() == body["latest_date"]


def test_momentum_none_when_history_too_short(client, synthetic_bdi):
    synthetic_bdi([100, 101, 102])
    assert client.get("/api/freight/bdi/summary").json()["momentum_14d"]["percent"] is None


def test_dataset_failure_returns_clean_error(client, monkeypatch):
    from app.errors import DatasetError
    from app.services import freight_service

    def boom():
        raise DatasetError("Could not read dataset file x.csv.")

    monkeypatch.setattr(freight_service, "load_bdi", boom)
    r = client.get("/api/freight/bdi/summary")
    assert r.status_code == 503
    assert r.json()["error"] == "DATASET_UNAVAILABLE"
    assert "Traceback" not in r.text
