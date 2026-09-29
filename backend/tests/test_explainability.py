def test_explainability_structured(client, mock_provider):
    r = client.post("/api/explainability", json={"port_name": "Paradip", "congestion_score": 20,
                                                  "rate_momentum_14d": 5.0})
    d = r.json()
    assert r.status_code == 200
    f = {x["factor"]: x for x in d["factors"]}
    assert f["Congestion score"]["impact"] == "positive"
    assert f["Berth availability"]["impact"] == "unavailable"
    assert d["ai_narrative"] is None and d["ai_narrative_status"] == "NOT_CONFIGURED"
