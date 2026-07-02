import importlib
from fastapi.testclient import TestClient


def test_api_flow(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    import app.database as database
    import app.repository as repository
    import app.reporting as reporting
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(repository, "connect", database.connect)
    monkeypatch.setattr(reporting, "connect", database.connect)
    from app.main import app
    with TestClient(app) as client:
        listing = client.get("/api/ipos").json()
        assert listing["total"] == 4
        ipo_id = listing["items"][0]["id"]
        bad = client.post(f"/api/ipos/{ipo_id}/adjustments", json={"value": 11, "reason": "这是足够长的调整原因"})
        assert bad.status_code == 422
        short = client.post(f"/api/ipos/{ipo_id}/adjustments", json={"value": 2, "reason": "太短"})
        assert short.status_code == 422
        saved = client.post(f"/api/ipos/{ipo_id}/adjustments", json={"value": 2, "reason": "基于样例数据的合理人工调整"})
        assert saved.status_code == 201
        first = client.post("/api/reports").json()
        second = client.post("/api/reports").json()
        assert second["version"] == first["version"] + 1
        assert client.get(f"/api/reports/{first['id']}/download?format=md").status_code == 200
        pdf = client.get(f"/api/reports/{first['id']}/download?format=pdf")
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")

