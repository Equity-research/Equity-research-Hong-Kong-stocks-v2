import importlib
from datetime import date, datetime
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
    import app.grey_market as grey_market
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
        monkeypatch.setattr(repository, "fetch_grey_market_quote", lambda code: grey_market.GreyMarketQuote(49.25, datetime.fromisoformat("2026-07-02T18:31:00"), "测试暗盘行情", offer_price=48.5))
        grey_quote = client.post(f"/api/ipos/{ipo_id}/grey-market-price").json()
        assert grey_quote["price"] == 49.25
        assert grey_quote["source"] == "测试暗盘行情"
        assert grey_quote["reference_price"] == 48.5
        assert grey_quote["reference_label"] == "最新招股价"
        detail_with_grey = client.get(f"/api/ipos/{ipo_id}").json()
        assert detail_with_grey["price_low"] == detail["price_low"]
        assert detail_with_grey["price_high"] == detail["price_high"]
        assert detail_with_grey["metrics"]["grey_market_price"] == 49.25
        assert detail_with_grey["metrics"]["grey_market_offer_price"] == 48.5
        assert detail_with_grey["metrics"]["grey_market_change_pct"] == 1.55
        manual_quote = client.put(f"/api/ipos/{ipo_id}/grey-market-price", json={"price": 5.72}).json()
        assert manual_quote["price"] == 5.72
        assert manual_quote["source"] == "手动输入"
        manual_detail = client.get(f"/api/ipos/{ipo_id}").json()
        assert manual_detail["metrics"]["grey_market_price"] == 5.72
        assert manual_detail["metrics"]["grey_market_source"] == "手动输入"
        monkeypatch.setattr(repository, "fetch_grey_market_quote", lambda code: grey_market.GreyMarketQuote(3.3, datetime.fromisoformat("2026-07-03T16:15:00"), "腾讯港股行情", offer_price=5.5, reference_label="昨日收盘价"))
        manual_refresh_result = repository.refresh_grey_market_prices(date.fromisoformat("2026-07-02"))
        assert manual_refresh_result["refreshed"]
        manual_after_refresh = client.get(f"/api/ipos/{ipo_id}").json()
        assert manual_after_refresh["metrics"]["grey_market_price"] == 5.72
        assert manual_after_refresh["metrics"]["grey_market_source"] == "手动输入"
        assert manual_after_refresh["metrics"]["grey_market_reference_price"] == 5.5
        assert manual_after_refresh["metrics"]["grey_market_reference_label"] == "昨日收盘价"
        assert manual_after_refresh["metrics"]["grey_market_change_pct"] == 4.0
        assert manual_after_refresh["price_low"] == 5.5
        assert manual_after_refresh["price_high"] == 5.5
        finalized = client.post(f"/api/ipos/{ipo_id}/grey-market-price/finalize").json()
        assert finalized["metrics"]["grey_market_finalized"] is True
        monkeypatch.setattr(repository, "fetch_grey_market_quote", lambda code: grey_market.GreyMarketQuote(6.0, datetime.fromisoformat("2026-07-03T16:15:00"), "测试暗盘行情", offer_price=5.0))
        refresh_result = repository.refresh_grey_market_prices(date.fromisoformat("2026-07-03"))
        assert refresh_result["refreshed"]
        assert detail["code"] in refresh_result["skipped"]
        refreshed_code = refresh_result["refreshed"][0]["code"]
        refreshed_detail = client.get(f"/api/ipos/{next(item['id'] for item in listing['items'] if item['code'] == refreshed_code)}").json()
        assert refreshed_detail["metrics"]["grey_market_offer_price"] == 5.0
        assert refreshed_detail["metrics"]["grey_market_change_pct"] == 20.0
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


def test_futu_dark_quote_parser(monkeypatch):
    import app.grey_market as grey_market

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ret_code": 0,
                "data": {
                    "section_list": [
                        {
                            "trade_section": "HK_DARK",
                            "point_list": [
                                {"time": 1783333860000, "cur_price": 5.68, "issue_price": 5.48},
                                {"time": 1783333920000, "cur_price": 5.72},
                            ],
                        }
                    ]
                },
            }

    monkeypatch.setattr(grey_market.httpx, "get", lambda *args, **kwargs: Response())
    quote = grey_market.fetch_futu_dark_quote("02667")
    assert quote is not None
    assert quote.price == 5.72
    assert quote.offer_price == 5.48
    assert quote.source == "富途暗盘行情"


def test_grey_market_quote_uses_backup_sources(monkeypatch):
    import app.grey_market as grey_market

    monkeypatch.setattr(grey_market, "fetch_futu_dark_quote", lambda code: None)
    monkeypatch.setattr(grey_market, "fetch_tencent_hk_quote", lambda code: grey_market.GreyMarketQuote(
        4.87,
        datetime.fromisoformat("2026-07-06T16:40:29"),
        "腾讯港股行情",
    ))
    monkeypatch.setattr(grey_market, "fetch_yahoo_hk_quote", lambda code: None)

    quote = grey_market.fetch_grey_market_quote("02667.HK")

    assert quote.price == 4.87
    assert quote.source == "腾讯港股行情"


def test_tencent_quote_uses_previous_close_as_reference(monkeypatch):
    import app.grey_market as grey_market

    class Response:
        text = 'v_hk02667="100~同仁堂医养~02667~3.280~5.500~4.760~29154960.0~0~0~3.280~0~0~0~0~0~0~0~0~0~3.280~0~0~0~0~0~0~0~0~0~29154960.0~2026/07/07 13:08:35~-2.220~-40.36";'

        def raise_for_status(self):
            return None

    monkeypatch.setattr(grey_market.httpx, "get", lambda *args, **kwargs: Response())

    quote = grey_market.fetch_tencent_hk_quote("02667")

    assert quote is not None
    assert quote.price == 3.28
    assert quote.offer_price == 5.5
    assert quote.reference_label == "昨日收盘价"
