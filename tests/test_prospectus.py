from datetime import date

import app.daily_ipo as daily_ipo
import app.prospectus as prospectus


def test_parse_prospectus_url_from_hkipox_detail_page():
    page = """
    <div class="detail-titlebar">
      <a href="https://example.com/doc.pdf" class="pdf-link" target="_blank">招股书</a>
    </div>
    """

    assert prospectus.parse_prospectus_url(page) == "https://example.com/doc.pdf"


def test_sync_prospectuses_deletes_stale_reuses_existing_and_downloads_new(tmp_path, monkeypatch):
    report_date = date(2026, 7, 3)
    monkeypatch.setattr(daily_ipo, "DATA_DIR", tmp_path / "data")
    daily_ipo.DATA_DIR.mkdir()
    (daily_ipo.DATA_DIR / "daily_ipo_2026-07-03.csv").write_text(
        "\n".join([
            "record_date,stock_code,company_name,status,subscription_end_date,expected_listing_date,data_source,source_url",
            "2026-07-03,00537,普源精电,认购中,2026-07-06,2026-07-09,测试数据,local",
            "2026-07-03,02249,晶合集成,认购中,2026-07-07,2026-07-10,测试数据,local",
            "2026-07-03,02667,同仁堂医养,认购中,2026-07-03,2026-07-07,测试数据,local",
        ]),
        encoding="utf-8",
    )
    old_dir = tmp_path / "prospectuses" / "2026-07-02"
    today_dir = tmp_path / "prospectuses" / "2026-07-03"
    old_dir.mkdir(parents=True)
    today_dir.mkdir(parents=True)
    (old_dir / "00537_普源精电_招股书.pdf").write_bytes(b"%PDF old")
    stale = today_dir / "02667_同仁堂医养_招股书.pdf"
    stale.write_bytes(b"%PDF stale")

    monkeypatch.setattr(prospectus, "fetch_prospectus_url", lambda code: f"https://example.com/{code}.pdf")

    def fake_download(url, destination):
        destination.write_bytes(b"%PDF new")

    monkeypatch.setattr(prospectus, "download_prospectus", fake_download)

    result = prospectus.sync_prospectuses_for_date(report_date, root=tmp_path)

    assert not stale.exists()
    assert (today_dir / "00537_普源精电_招股书.pdf").read_bytes() == b"%PDF old"
    assert (today_dir / "02249_晶合集成_招股书.pdf").read_bytes() == b"%PDF new"
    assert [path.name for path in result.reused] == ["00537_普源精电_招股书.pdf"]
    assert [path.name for path in result.downloaded] == ["02249_晶合集成_招股书.pdf"]
    assert [path.name for path in result.deleted] == ["02667_同仁堂医养_招股书.pdf"]
