import importlib
from fastapi.testclient import TestClient


def test_api_flow(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    import app.database as database
    import app.daily_ipo as daily_ipo
    import app.repository as repository
    import app.reporting as reporting
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(daily_ipo, "DATA_DIR", tmp_path)
    monkeypatch.setattr(repository, "connect", database.connect)
    monkeypatch.setattr(reporting, "connect", database.connect)
    (tmp_path / "daily_ipo_2026-07-02.csv").write_text(
        "\n".join([
            "record_date,stock_code,company_name,status,subscription_end_date,expected_listing_date,data_source,source_url",
            "2026-07-02,02667,同仁堂医养,认购中（当日截止）,2026-07-02,2026-07-07,测试数据,local",
            "2026-07-02,01770,东方科脉,认购中,2026-07-04,2026-07-08,测试数据,local",
            "2026-07-02,07656,瑞为技术,认购中,2026-07-03,2026-07-08,测试数据,local",
            "2026-07-02,07687,易控智驾,认购中,2026-07-03,2026-07-08,测试数据,local",
            "2026-07-02,08090,宝盖新材,认购中,2026-07-03,2026-07-08,测试数据,local",
            "2026-07-02,09971,基本半导体,认购中,2026-07-03,2026-07-08,测试数据,local",
            "2026-07-02,06880,MOMENTA-W,认购中,2026-07-03,2026-07-08,测试数据,local",
            "2026-07-02,02797,齐云山食品,认购中,2026-07-06,2026-07-09,测试数据,local",
            "2026-07-02,03752,珞石机器人,认购中,2026-07-06,2026-07-09,测试数据,local",
            "2026-07-02,00537,普源精电,认购中,2026-07-06,2026-07-09,测试数据,local",
            "2026-07-02,02475,立讯精密,认购中,2026-07-06,2026-07-09,测试数据,local",
            "2026-07-02,06951,三环集团,认购中,2026-07-06,2026-07-09,测试数据,local",
            "2026-07-02,01377,鼎泰高科,认购中,2026-07-06,2026-07-09,测试数据,local",
            "2026-07-02,02249,晶合集成,认购中,2026-07-07,2026-07-10,测试数据,local",
            "2026-07-02,06745,滨化股份,认购中,2026-07-07,2026-07-10,测试数据,local",
            "2026-07-02,02523,永康控股,认购中,2026-07-08,2026-07-13,测试数据,local",
        ]),
        encoding="utf-8",
    )
    from app.main import app
    with TestClient(app) as client:
        listing = client.get("/api/ipos").json()
        assert listing["total"] == 16
        assert all(not item["is_sample"] for item in listing["items"])
        assert listing["insights"]["fundamental_valuation_ranking"]
        assert listing["insights"]["allotment_difficulty"]
        ipo_id = listing["items"][0]["id"]
        detail = client.get(f"/api/ipos/{ipo_id}").json()
        assert detail["minimum_subscription_amount"] is not None
        assert detail["issuance_shares"] is not None
        assert detail["lot_size"] is not None
        bad = client.post(f"/api/ipos/{ipo_id}/adjustments", json={"value": 2, "reason": "这是足够长的调整原因"})
        assert bad.status_code == 422
        short = client.post(f"/api/ipos/{ipo_id}/adjustments", json={"value": 2, "reason": "太短"})
        assert short.status_code == 422
        saved = client.post(f"/api/ipos/{ipo_id}/adjustments", json={"value": 1, "reason": "基于本地招股资料的合理人工调整"})
        assert saved.status_code == 201
        first = client.post("/api/reports?report_date=2026-07-02").json()
        second = client.post("/api/reports?report_date=2026-07-02").json()
        refreshed = client.get("/api/ipos").json()
        oriental = next(item for item in refreshed["items"] if item["code"] == "01770.HK")
        assert oriental["deadline"] == "2026-07-04"
        reports = client.get("/api/reports").json()
        assert second["version"] == 1
        assert len(reports) == 1
        assert reports[0]["id"] == second["id"]
        assert first["created_at"] <= second["created_at"]
        assert client.get(f"/api/reports/{second['id']}/download?format=md").status_code == 200
        pdf = client.get(f"/api/reports/{second['id']}/download?format=pdf")
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")
