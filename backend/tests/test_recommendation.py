from app.errors import ProviderTimeoutError

FAVOURABLE = {
    "port_name": "Paradip",
    "congestion_score": 20,
    "freight_rate_percentile": 15,
    "rate_momentum_14d": 5.0,
    "berth_availability": 80,
    "vessel_compatibility": True,
}


def test_weather_included_when_available(client, mock_provider):
    body = client.post("/api/recommendation", json=FAVOURABLE).json()
    assert body["weather"]["available"] is True
    assert body["weather"]["level"] == "LOW"
    assert body["decision"] == "CHARTER NOW"
    assert body["market_entry"]["status"] == "FAVOURABLE"
    assert body["vessel"]["status"] == "COMPATIBLE"
    assert body["explanations_source"] == "rule_based"
    assert body["data_provenance"]["weather_observations"] == "REAL_DATA"


def test_works_when_weather_unavailable(client, mock_provider):
    mock_provider.error = ProviderTimeoutError("t")
    response = client.post("/api/recommendation", json=FAVOURABLE)
    assert response.status_code == 200
    body = response.json()
    assert body["weather"]["available"] is False
    assert body["weather"]["score"] is None
    assert body["weather"]["level"] == "UNKNOWN"
    assert body["decision"] == "CHARTER NOW"
    assert body["market_entry"]["status"] == "FAVOURABLE"
    assert body["data_provenance"]["weather_risk_score"] == "UNAVAILABLE"
    assert "not assessed" in body["risk"]["reason"]


def test_high_weather_adds_caution_without_changing_market_status(
    client, mock_provider, payload_factory
):
    mock_provider.payload = payload_factory(
        gust=70, wind=60, precip=20, prob=90, visibility=900, code=95
    )
    body = client.post("/api/recommendation", json=FAVOURABLE).json()
    assert body["market_entry"]["status"] == "FAVOURABLE"  # unchanged
    assert body["vessel"]["status"] == "COMPATIBLE"  # unchanged
    assert body["decision"] == "CHARTER WITH CAUTION"
    assert body["risk"]["overall_level"] in ("HIGH", "SEVERE")
    assert body["weather"]["key_factors"]


def test_bad_weather_does_not_turn_wait_into_charter(client, mock_provider, payload_factory):
    mock_provider.payload = payload_factory(code=1)
    request = {**FAVOURABLE, "congestion_score": 90, "freight_rate_percentile": 90,
               "rate_momentum_14d": -6}
    assert client.post("/api/recommendation", json=request).json()["decision"] == "WAIT"


def test_incompatible_vessel_takes_priority(client, mock_provider):
    request = {**FAVOURABLE, "vessel_compatibility": False,
               "vessel_compatibility_reason": "Draft exceeds berth limit."}
    body = client.post("/api/recommendation", json=request).json()
    assert body["decision"] == "RESOLVE VESSEL COMPATIBILITY"
    assert "Draft exceeds" in body["vessel"]["reason"]


def test_missing_inputs_are_unavailable_not_faked(client, mock_provider):
    body = client.post("/api/recommendation", json={"port_name": "Paradip"}).json()
    assert body["decision"] == "INSUFFICIENT DATA"
    assert body["market_entry"]["status"] == "INSUFFICIENT_DATA"
    assert body["vessel"]["status"] == "UNKNOWN"
    assert body["risk"]["operational_level"] == "UNKNOWN"
    assert body["data_provenance"]["congestion_score"] == "UNAVAILABLE"


def test_berth_and_demand_drive_operational_risk(client, mock_provider):
    request = {**FAVOURABLE, "berth_availability": 10,
               "demand_volume": 150, "demand_volume_reference": 100}
    body = client.post("/api/recommendation", json=request).json()
    assert body["risk"]["operational_level"] == "HIGH"
    assert body["decision"] == "CHARTER WITH CAUTION"


def test_unknown_port_404(client, mock_provider):
    assert client.post("/api/recommendation", json={"port_name": "Atlantis"}).status_code == 404


def test_out_of_range_input_rejected(client, mock_provider):
    request = {**FAVOURABLE, "congestion_score": 500}
    assert client.post("/api/recommendation", json=request).status_code == 422


def test_structured_explanation_inputs_exposed(client, mock_provider, payload_factory):
    mock_provider.payload = payload_factory(gust=70)
    body = client.post("/api/recommendation", json=FAVOURABLE).json()
    facts = body["explanation_inputs"]
    assert facts["weather_risk_score"] is not None
    assert any(f["factor"] == "Wind gusts" for f in facts["weather_factors"])


def test_bdi_market_data_fills_missing_and_labels_provenance(client, mock_provider):
    body = client.post("/api/recommendation",
                       json={"port_name": "Paradip", "use_bdi_market_data": True}).json()
    prov = body["data_provenance"]
    assert prov["rate_momentum_14d"] == "DERIVED_FROM_BDI"
    assert prov["freight_rate_percentile"] == "DERIVED_FROM_BDI"
    assert body["market_entry"]["status"] != "INSUFFICIENT_DATA"
    assert any("proxy" in e for e in body["explanations"])


def test_caller_values_win_over_bdi(client, mock_provider):
    body = client.post("/api/recommendation", json={
        "port_name": "Paradip", "use_bdi_market_data": True,
        "rate_momentum_14d": 7.0, "freight_rate_percentile": 10}).json()
    assert body["data_provenance"]["rate_momentum_14d"] == "PROVIDED_BY_CALLER"
    assert body["explanation_inputs"]["inputs"]["rate_momentum_14d"] == 7.0


def test_bdi_flag_off_by_default(client, mock_provider):
    body = client.post("/api/recommendation", json={"port_name": "Paradip"}).json()
    assert body["decision"] == "INSUFFICIENT DATA"


def test_recommendation_survives_dataset_failure(client, mock_provider, monkeypatch):
    from app.errors import DatasetError
    from app.services import freight_service

    def boom():
        raise DatasetError("x")

    monkeypatch.setattr(freight_service, "load_bdi", boom)
    r = client.post("/api/recommendation", json={"port_name": "Paradip", "use_bdi_market_data": True,
                                                  "congestion_score": 20})
    assert r.status_code == 200
