from datetime import date

from app import subscription
from app.subscription import HKIPOxRow, parse_hkipox_today_rows, write_daily_ipo_from_hkipox


def test_parse_hkipox_today_rows_cleans_badges_and_multiples():
    html = """
    <h2 class="section-title">今日申购 <span class="count">(1)</span></h2>
    <table><thead><tr><th>代码</th></tr></thead><tbody>
      <tr data-href="/stock/00537">
        <td class="code" data-label="代码">00537</td>
        <td class="name" data-label="名称">普源精电 AH 无鞋</td>
        <td data-label="招股结束日"><span>2026-07-06 <span class="wk">一</span></span></td>
        <td data-label="上市日"><span>2026-07-09 <span class="wk">四</span></span></td>
        <td class="num" data-label="认购倍数"><span>20.25x</span></td>
      </tr>
    </tbody></table>
    """

    rows = parse_hkipox_today_rows(html)

    assert len(rows) == 1
    assert rows[0].stock_code == "00537"
    assert rows[0].company_name == "普源精电"
    assert rows[0].subscription_multiple == 20.25


def test_write_daily_ipo_replaces_existing_file_without_file_write_permission(tmp_path, monkeypatch):
    monkeypatch.setattr(subscription, "DATA_DIR", tmp_path)
    path = tmp_path / "daily_ipo_2026-07-07.csv"
    path.write_text("stale\n", encoding="utf-8")
    path.chmod(0o444)

    try:
        result = write_daily_ipo_from_hkipox(date(2026, 7, 7), [
            HKIPOxRow(
                stock_code="02523",
                company_name="永康控股",
                subscription_end_date=date(2026, 7, 8),
                expected_listing_date=date(2026, 7, 15),
                subscription_multiple=1850.46,
            )
        ])
    finally:
        path.chmod(0o644)

    assert result == path
    content = path.read_text(encoding="utf-8")
    assert "stale" not in content
    assert "02523" in content
    assert "永康控股" in content
