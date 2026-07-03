import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

from app.config import DATA_DIR


HKIPOX_URL = "https://hkipox.com/"


@dataclass(frozen=True)
class SubscriptionRecord:
    record_date: date
    captured_at: str
    stock_code: str
    company_name: str
    subscription_multiple: float | None
    status: str
    subscription_end_date: date
    data_type: str
    data_source: str
    source_url: str

    @property
    def normalized_code(self) -> str:
        return f"{self.stock_code.zfill(5)}.HK"


@dataclass(frozen=True)
class HKIPOxRow:
    stock_code: str
    company_name: str
    subscription_end_date: date
    expected_listing_date: date | None
    subscription_multiple: float | None

    @property
    def normalized_code(self) -> str:
        return f"{self.stock_code.zfill(5)}.HK"


def subscription_path(record_date: date) -> Path:
    return DATA_DIR / f"ipo_subscription_{record_date.isoformat()}.csv"


def fetch_hkipox_today_rows() -> list[HKIPOxRow]:
    request = Request(HKIPOX_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        page = response.read().decode("utf-8", errors="replace")
    return parse_hkipox_today_rows(page)


def parse_hkipox_today_rows(page: str) -> list[HKIPOxRow]:
    today_section = re.search(
        r"<h2[^>]*>\s*今日申购\b.*?</thead>\s*<tbody>(?P<tbody>.*?)</tbody>",
        page,
        flags=re.S,
    )
    if not today_section:
        return []

    rows = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", today_section.group("tbody"), flags=re.S):
        cells = _row_cells(row_html)
        code = cells.get("代码", "").strip()
        name = cells.get("名称", "").strip()
        end_date = _parse_date(cells.get("招股结束日", ""))
        if not code or not name or end_date is None:
            continue
        rows.append(HKIPOxRow(
            stock_code=code.zfill(5),
            company_name=_clean_company_name(name),
            subscription_end_date=end_date,
            expected_listing_date=_parse_date(cells.get("上市日", "")),
            subscription_multiple=_parse_multiple(cells.get("认购倍数", "")),
        ))
    return rows


def write_daily_ipo_from_hkipox(record_date: date, rows: list[HKIPOxRow]) -> Path:
    path = DATA_DIR / f"daily_ipo_{record_date.isoformat()}.csv"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "record_date", "stock_code", "company_name", "status", "subscription_end_date",
            "expected_listing_date", "data_source", "source_url",
        ])
        writer.writeheader()
        for row in rows:
            if row.subscription_end_date <= record_date:
                continue
            if row.expected_listing_date is not None and row.expected_listing_date <= record_date:
                continue
            writer.writerow({
                "record_date": record_date.isoformat(),
                "stock_code": row.stock_code,
                "company_name": row.company_name,
                "status": "认购中",
                "subscription_end_date": row.subscription_end_date.isoformat(),
                "expected_listing_date": row.expected_listing_date.isoformat() if row.expected_listing_date else "",
                "data_source": "HKIPOx",
                "source_url": HKIPOX_URL,
            })
    return path


def write_subscription_records(record_date: date, rows: list[HKIPOxRow]) -> Path:
    captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S CST")
    records = [
        SubscriptionRecord(
            record_date=record_date,
            captured_at=captured_at,
            stock_code=row.stock_code,
            company_name=row.company_name,
            subscription_multiple=row.subscription_multiple,
            status="认购中" if row.subscription_end_date > record_date else "已截止",
            subscription_end_date=row.subscription_end_date,
            data_type="招股期实时推算值",
            data_source="HKIPOx",
            source_url=HKIPOX_URL,
        )
        for row in rows
    ]
    return write_subscription_csv(record_date, records)


def write_subscription_csv(record_date: date, records: list[SubscriptionRecord]) -> Path:
    path = subscription_path(record_date)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "record_date", "captured_at", "stock_code", "company_name", "subscription_multiple",
            "status", "subscription_end_date", "data_type", "data_source", "source_url",
        ])
        writer.writeheader()
        for record in records:
            writer.writerow({
                "record_date": record.record_date.isoformat(),
                "captured_at": record.captured_at,
                "stock_code": record.stock_code,
                "company_name": record.company_name,
                "subscription_multiple": "" if record.subscription_multiple is None else f"{record.subscription_multiple:.2f}",
                "status": record.status,
                "subscription_end_date": record.subscription_end_date.isoformat(),
                "data_type": record.data_type,
                "data_source": record.data_source,
                "source_url": record.source_url,
            })
    return path


def load_subscription_records(record_date: date) -> list[SubscriptionRecord]:
    path = subscription_path(record_date)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            SubscriptionRecord(
                record_date=date.fromisoformat(row["record_date"]),
                captured_at=row["captured_at"],
                stock_code=row["stock_code"].strip(),
                company_name=row["company_name"].strip(),
                subscription_multiple=_parse_optional_float(row.get("subscription_multiple")),
                status=row["status"].strip(),
                subscription_end_date=date.fromisoformat(row["subscription_end_date"]),
                data_type=row["data_type"].strip(),
                data_source=row["data_source"].strip(),
                source_url=row["source_url"].strip(),
            )
            for row in csv.DictReader(handle)
        ]


def latest_subscription_before(record_date: date) -> Path | None:
    candidates = []
    for path in DATA_DIR.glob("ipo_subscription_*.csv"):
        match = re.fullmatch(r"ipo_subscription_(\d{4}-\d{2}-\d{2})\.csv", path.name)
        if not match:
            continue
        candidate_date = date.fromisoformat(match.group(1))
        if candidate_date < record_date:
            candidates.append((candidate_date, path))
    return max(candidates, default=(None, None))[1]


def _row_cells(row_html: str) -> dict[str, str]:
    cells = {}
    pattern = r"<td\b(?P<attrs>[^>]*)>(?P<body>.*?)</td>"
    for match in re.finditer(pattern, row_html, flags=re.S):
        label_match = re.search(r'data-label="([^"]+)"', match.group("attrs"))
        if not label_match:
            continue
        cells[label_match.group(1)] = _text(match.group("body"))
    return cells


def _text(markup: str) -> str:
    text = re.sub(r"<[^>]+>", " ", markup)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _parse_date(value: str) -> date | None:
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return date.fromisoformat(match.group()) if match else None


def _clean_company_name(value: str) -> str:
    parts = [part for part in value.split() if part not in {"AH", "无鞋", "回拨"}]
    return " ".join(parts)


def _parse_multiple(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group()) if match else None


def _parse_optional_float(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None
