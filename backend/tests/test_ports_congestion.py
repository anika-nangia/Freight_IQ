import pytest

from app.data.congestion_loader import clear_congestion_cache


@pytest.fixture
def congestion_csv(tmp_path, monkeypatch):
    f = tmp_path / "port_congestion.csv"
    f.write_text(
        "Date,Port,Model Congestion Score,Freight Rate,Rate Momentum 14d\n"
        "2026-09-01,Paradip,40,12.0,1.5\n"
        "2026-09-02,Paradip,55,12.5,2.0\n"
        "2026-09-02,Haldia,20,11.0,-1.0\n"
    )
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    clear_congestion_cache()
    yield
    clear_congestion_cache()


def test_ports_list_and_invalid(client):
    assert any(p["name"] == "Paradip" for p in client.get("/api/ports").json())
    assert client.get("/api/ports/Paradip").status_code == 200
    assert client.get("/api/ports/Atlantis").json()["error"] == "PORT_NOT_FOUND"


def test_congestion_missing_dataset_is_clean_error(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    clear_congestion_cache()
    r = client.get("/api/congestion")
    assert r.status_code == 503 and r.json()["error"] == "DATASET_UNAVAILABLE"


def test_scoreboard_latest_per_port(client, congestion_csv):
    rows = {r["port"]: r for r in client.get("/api/congestion").json()["ports"]}
    assert rows["Paradip"]["congestion_score"] == 55
    assert rows["Haldia"]["rate_momentum_14d"] == -1.0


def test_port_and_history(client, congestion_csv):
    assert client.get("/api/congestion/paradip").json()["congestion_score"] == 55
    assert len(client.get("/api/congestion/Paradip/history").json()["history"]) == 2
    assert client.get("/api/congestion/Kolkata").status_code == 404
