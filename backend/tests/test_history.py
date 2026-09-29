import pytest


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "h.sqlite3"))


def test_create_get_list_delete(client):
    body = {"port": "Paradip", "vessel": "Capesize", "inputs": {"cargo": "coal"},
            "recommendation": {"decision": "WAIT"}}
    r = client.post("/api/history", json=body)
    assert r.status_code == 201
    rec_id = r.json()["id"]
    assert client.get(f"/api/history/{rec_id}").json()["recommendation"]["decision"] == "WAIT"
    assert [x["id"] for x in client.get("/api/history").json()] == [rec_id]
    assert client.delete(f"/api/history/{rec_id}").status_code == 200
    assert client.get(f"/api/history/{rec_id}").status_code == 404


def test_newest_first_and_clear(client):
    for p in ("Paradip", "Haldia"):
        client.post("/api/history", json={"port": p})
    assert [x["port"] for x in client.get("/api/history").json()] == ["Haldia", "Paradip"]
    assert client.delete("/api/history").json()["deleted"] == 2


def test_delete_missing_and_bad_port(client):
    assert client.delete("/api/history/nope").json()["error"] == "NOT_FOUND"
    assert client.post("/api/history", json={"port": "<x>"}).status_code == 422
