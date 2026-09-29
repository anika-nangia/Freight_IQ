def test_congestion_falls_back_to_snapshots(client, monkeypatch):
    monkeypatch.setenv("CONGESTION_FILE", "")
    d = client.get("/api/congestion").json()
    assert d["source"] == "DERIVED_FROM_VESSEL_SNAPSHOTS"
    rows = {r["port"]: r for r in d["ports"]}
    assert len(rows) == 14
    assert rows["Paradip"]["queue_congestion_index"] is None  # combined status only
    assert 0 <= rows["Visakhapatnam"]["queue_congestion_index"] <= 100
    assert "model congestion" in d["note"].lower()


def test_port_congestion_and_history_fallback(client):
    assert client.get("/api/congestion/Haldia").json()["source"] == "DERIVED_FROM_VESSEL_SNAPSHOTS"
    assert len(client.get("/api/congestion/Haldia/history").json()["history"]) >= 2
    assert client.get("/api/congestion/Atlantis").status_code == 404


def test_risk_endpoint(client):
    r = client.get("/api/risk/Visakhapatnam").json()
    assert r["operational_level"] in {"LOW", "MODERATE", "HIGH", "SEVERE", "UNKNOWN"}
    assert r["source"] == "PROXY_FROM_VESSEL_SNAPSHOTS" and "berth_availability" in r["inputs"]


def test_vessel_optimizer_never_claims_compatible(client):
    ok = client.post("/api/vessel/optimize", json={"port_name": "Paradip", "loa_m": 100}).json()
    assert ok["status"] == "PRECEDENT_EXISTS" and ok["compatible"] is None
    big = client.post("/api/vessel/optimize", json={"port_name": "Paradip", "loa_m": 400}).json()
    assert big["status"] == "NO_PRECEDENT" and big["warnings"]
    none = client.post("/api/vessel/optimize", json={"port_name": "Paradip"}).json()
    assert none["status"] == "UNKNOWN"
    assert client.post("/api/vessel/optimize", json={"port_name": "Atlantis", "loa_m": 1}).status_code == 404


def test_recommendation_uses_snapshot_proxies(client, mock_provider):
    d = client.post("/api/recommendation", json={"port_name": "Visakhapatnam",
                                                  "use_vessel_snapshot_data": True}).json()
    assert d["data_provenance"]["berth_availability"] == "PROXY_FROM_VESSEL_SNAPSHOTS"
    assert d["risk"]["operational_level"] != "UNKNOWN"


def test_explicit_values_not_overwritten(client, mock_provider):
    d = client.post("/api/recommendation", json={"port_name": "Visakhapatnam", "berth_availability": 90,
                                                  "use_vessel_snapshot_data": True}).json()
    assert d["data_provenance"]["berth_availability"] != "PROXY_FROM_VESSEL_SNAPSHOTS"


def test_optimizer_unknown_when_port_has_no_dimension_data(client):
    r = client.post("/api/vessel/optimize", json={"port_name": "Visakhapatnam", "loa_m": 100}).json()
    assert r["status"] == "UNKNOWN" and r["unknown"]
