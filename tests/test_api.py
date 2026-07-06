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
    import app.a_share_sentiment as a_share_sentiment
    import app.us_market as us_market
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(daily_ipo, "DATA_DIR", tmp_path)
    monkeypatch.setattr(a_share_sentiment, "DATA_DIR", tmp_path)
    monkeypatch.setattr(us_market, "DATA_DIR", tmp_path)
    monkeypatch.setattr(a_share_sentiment, "fetch_market_rows", lambda: ([
        a_share_sentiment.MarketRow("000001", "平安银行", 11.2, 1.23, 0.14, 100, 200),
        a_share_sentiment.MarketRow("600000", "浦发银行", 9.8, -0.4, -0.04, 80, 160),
    ], "测试行情源"))
    monkeypatch.setattr(a_share_sentiment, "fetch_discussion_titles", lambda: (["反弹 修复 成交活跃", "震荡 谨慎 资金观望"], ["测试热词源"]))
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
        sentiment = client.get("/api/a-shares/sentiment?record_date=2026-07-02").json()
        assert sentiment["average_price"] == 10.5
        assert sentiment["market_source"] == "测试行情源"
        assert sentiment["hot_word_sources"] == ["测试热词源"]
        assert "反弹" in [item["word"] for item in sentiment["hot_words"]]
        assert (tmp_path / "a_share_market_2026-07-02.csv").exists()
        assert (tmp_path / "a_share_hot_words_2026-07-02.csv").exists()
        monkeypatch.setattr(us_market, "fetch_news_items", lambda query, limit=5, fallback_query=None: [
            us_market.NewsItem(
                "AI memory demand rises",
                "测试新闻",
                "https://example.com/news",
                None,
                original_url="https://example.com/original-news",
                original_title="AI memory demand rises",
                original_body="AI memory demand rises as server buyers add capacity.",
                original_saved_at="2026-07-02T10:00:00+08:00",
            )
        ])
        monkeypatch.setattr(us_market, "fetch_qqq_quote", lambda: {"price": 512.3, "change": 2.1, "change_pct": 0.41, "quote_time": "2026-07-02"})
        monkeypatch.setattr(us_market, "fetch_qqq_history", lambda: [{"date": "2026-07-02", "open": 510.2, "high": 513.1, "low": 509.8, "close": 512.3, "change_pct": 0.41}])
        us_dashboard = client.get("/api/us-market/dashboard?record_date=2026-07-02&refresh=true").json()
        assert us_dashboard["qqq"]["symbol"] == "QQQ"
        assert "内存芯片" in [item["name"] for item in us_dashboard["modules"]]
        assert us_dashboard["qqq"]["history"][0]["open"] == 510.2
        assert us_dashboard["modules"][0]["news"][0]["title_zh"]
        assert us_dashboard["modules"][0]["news"][0]["article_summary_zh"].startswith("文章总结")
        assert us_dashboard["modules"][0]["news"][0]["original_body"].startswith("AI memory demand rises")
        assert (tmp_path / "us_market_news_2026-07-02.json").exists()
