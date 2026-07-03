import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import DATA_DIR


class DailyIPODataMissingError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class DailyIPORecord:
    record_date: date
    stock_code: str
    company_name: str
    status: str
    subscription_end_date: date
    expected_listing_date: date | None
    data_source: str
    source_url: str

    @property
    def normalized_code(self) -> str:
        return f"{self.stock_code.zfill(5)}.HK"


def daily_ipo_path(record_date: date) -> Path:
    return DATA_DIR / f"daily_ipo_{record_date.isoformat()}.csv"


def load_daily_ipo_records(record_date: date) -> list[DailyIPORecord]:
    path = daily_ipo_path(record_date)
    if not path.exists():
        raise DailyIPODataMissingError(f"缺少当日 IPO 清单：{path.name}。请先重新拉取 {record_date.isoformat()} 的 IPO 数据。")

    records = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append(DailyIPORecord(
                record_date=date.fromisoformat(row["record_date"]),
                stock_code=row["stock_code"].strip(),
                company_name=row["company_name"].strip(),
                status=row["status"].strip(),
                subscription_end_date=date.fromisoformat(row["subscription_end_date"]),
                expected_listing_date=_parse_optional_date(row.get("expected_listing_date", "")),
                data_source=row.get("data_source", "").strip(),
                source_url=row.get("source_url", "").strip(),
            ))
    return records


def active_subscription_codes(record_date: date) -> set[str]:
    records = load_daily_ipo_records(record_date)
    return {
        record.normalized_code
        for record in records
        if record.subscription_end_date > record_date
        and (record.expected_listing_date is None or record.expected_listing_date > record_date)
    }


def _parse_optional_date(value: str | None) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None
