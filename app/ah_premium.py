import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

from app.config import DATA_DIR


@dataclass(frozen=True)
class AHPremiumRecord:
    record_date: date
    hk_code: str
    company_name: str
    a_ticker: str
    h_offer_price_hkd: float
    a_close_cny: float | None
    cny_hkd: float | None
    ah_premium: float | None
    source: str
    notes: str


AH_MAPPINGS = {
    "00537.HK": ("普源精电", "688337.SS"),
    "02475.HK": ("立讯精密", "002475.SZ"),
    "06951.HK": ("三环集团", "300408.SZ"),
    "01377.HK": ("鼎泰高科", "301377.SZ"),
    "02249.HK": ("晶合集成", "688249.SS"),
    "06745.HK": ("滨化股份", "601678.SS"),
}


def ah_premium_path(record_date: date) -> Path:
    return DATA_DIR / f"ah_premium_{record_date.isoformat()}.csv"


def load_ah_premium_records(record_date: date) -> list[AHPremiumRecord]:
    path = ah_premium_path(record_date)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [_record_from_row(row) for row in csv.DictReader(handle)]


def write_ah_premium_records(record_date: date, records: list[AHPremiumRecord]) -> Path:
    path = ah_premium_path(record_date)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "record_date", "hk_code", "company_name", "a_ticker", "h_offer_price_hkd",
            "a_close_cny", "cny_hkd", "ah_premium", "source", "notes",
        ])
        writer.writeheader()
        for record in records:
            writer.writerow({
                "record_date": record.record_date.isoformat(),
                "hk_code": record.hk_code,
                "company_name": record.company_name,
                "a_ticker": record.a_ticker,
                "h_offer_price_hkd": record.h_offer_price_hkd,
                "a_close_cny": _format_optional(record.a_close_cny),
                "cny_hkd": _format_optional(record.cny_hkd),
                "ah_premium": _format_optional(record.ah_premium),
                "source": record.source,
                "notes": record.notes,
            })
    return path


def fetch_ah_premium_records(record_date: date, offer_prices: dict[str, float]) -> list[AHPremiumRecord]:
    cny_hkd = fetch_latest_close("CNYHKD=X")
    records = []
    for hk_code, (company_name, a_ticker) in AH_MAPPINGS.items():
        if hk_code not in offer_prices:
            continue
        a_close = fetch_latest_close(a_ticker)
        premium = None
        if a_close is not None and cny_hkd is not None:
            premium = round((a_close * cny_hkd / offer_prices[hk_code] - 1) * 100, 1)
        records.append(AHPremiumRecord(
            record_date=record_date,
            hk_code=hk_code,
            company_name=company_name,
            a_ticker=a_ticker,
            h_offer_price_hkd=offer_prices[hk_code],
            a_close_cny=a_close,
            cny_hkd=cny_hkd,
            ah_premium=premium,
            source="Yahoo Finance chart API",
            notes="A股最新日线收盘价按 CNY/HKD 转港币后与H股招股价比较",
        ))
    return records


def fetch_latest_close(symbol: str) -> float | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        for value in reversed(closes):
            if value is not None:
                return float(value)
    except Exception:
        return None
    return None


def latest_ah_premium_before(record_date: date) -> Path | None:
    candidates = []
    for path in DATA_DIR.glob("ah_premium_*.csv"):
        try:
            candidate_date = date.fromisoformat(path.stem.removeprefix("ah_premium_"))
        except ValueError:
            continue
        if candidate_date < record_date:
            candidates.append((candidate_date, path))
    return max(candidates, default=(None, None))[1]


def _record_from_row(row: dict[str, str]) -> AHPremiumRecord:
    return AHPremiumRecord(
        record_date=date.fromisoformat(row["record_date"]),
        hk_code=row["hk_code"].strip(),
        company_name=row["company_name"].strip(),
        a_ticker=row["a_ticker"].strip(),
        h_offer_price_hkd=float(row["h_offer_price_hkd"]),
        a_close_cny=_parse_optional_float(row.get("a_close_cny")),
        cny_hkd=_parse_optional_float(row.get("cny_hkd")),
        ah_premium=_parse_optional_float(row.get("ah_premium")),
        source=row.get("source", "").strip(),
        notes=row.get("notes", "").strip(),
    )


def _parse_optional_float(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.4f}".rstrip("0").rstrip(".")
