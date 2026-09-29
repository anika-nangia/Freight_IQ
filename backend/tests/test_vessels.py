from app.data.vessel_loader import _dims, _direction


def test_parsers():
    assert _dims("179.90/7.43") == (179.9, 7.43)
    assert _dims("200.00/") == (200.0, None)
    assert _dims("GEARED") == (None, None)
    assert [_direction(x) for x in ("D", "DISCH", "IMP", "LOADING", "D/L", "D/D/D")] == \
        ["DISCHARGE", "DISCHARGE", "DISCHARGE", "LOAD", "BOTH", "DISCHARGE"]


def test_latest_list_and_port_filter(client):
    r = client.get("/api/vessels/port/Paradip").json()
    assert r["vessels"] and all(v["port"] == "Paradip" for v in r["vessels"])
    assert len({v["snapshot_date"] for v in r["vessels"]}) == 1


def test_vessel_by_id_and_missing(client):
    assert client.get("/api/vessels/v0").json()["vessel_id"] == "v0"
    assert client.get("/api/vessels/v99999999").status_code == 422
    assert client.get("/api/vessels/v9999999").json()["error"] == "NOT_FOUND"
    assert client.get("/api/vessels/port/Atlantis").json()["error"] == "PORT_NOT_FOUND"


def test_operations_and_queue_history(client):
    o = client.get("/api/ports/Visakhapatnam/operations").json()
    assert o["total_vessels"] > 0 and "proxy" in o["notes"].lower()
    h = client.get("/api/ports/Haldia/queue-history").json()["history"]
    assert len(h) >= 2 and "waiting" in h[0]


def test_all_dataset_ports_resolve(client):
    for name in ("Karaikal", "Kattupalli", "Sagar", "Sandheads", "Gopalpur"):
        assert client.get(f"/api/ports/{name}/operations").status_code == 200
