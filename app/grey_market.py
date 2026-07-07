import json
import os
import re
from dataclasses import dataclass
from datetime import datetime

import httpx


FUTU_WEBAPI_URL = os.getenv("FUTU_WEBAPI_URL", "http://127.0.0.1:11111").rstrip("/")
FUTU_CLIENT_NNID = os.getenv("FUTU_CLIENT_NNID", "76879657")


@dataclass
class GreyMarketQuote:
    price: float
    fetched_at: datetime
    source: str
    offer_price: float | None = None
    reference_label: str | None = None


def fetch_grey_market_quote(code: str) -> GreyMarketQuote:
    normalized = code.replace(".HK", "").zfill(5)
    sources = (
        fetch_futu_dark_quote,
        fetch_tencent_hk_quote,
        fetch_yahoo_hk_quote,
    )
    for fetcher in sources:
        quote = fetcher(normalized)
        if quote is not None:
            return quote
    raise ValueError("富途、腾讯、Yahoo 暂未返回可用港股行情，请稍后再试")


def fetch_futu_dark_quote(code: str) -> GreyMarketQuote | None:
    symbol = f"HK.{code}"
    url = f"{FUTU_WEBAPI_URL}/v1/quote/{symbol}/rt-data"
    try:
        response = httpx.get(
            url,
            params={"request_section": "HK_DARK"},
            timeout=8,
            follow_redirects=True,
            headers={"X-Futu-Client-Nnid": FUTU_CLIENT_NNID},
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    if payload.get("ret_code") not in (0, "0", None):
        return None
    section = next(
        (
            item for item in ((payload.get("data") or {}).get("section_list") or [])
            if item.get("trade_section") == "HK_DARK"
        ),
        None,
    )
    if not section:
        return None
    points = [point for point in (section.get("point_list") or []) if parse_float(point.get("cur_price"))]
    if not points:
        return None
    latest = points[-1]
    price = parse_float(latest.get("cur_price"))
    timestamp = parse_float(latest.get("time"))
    if price is None or price <= 0:
        return None
    offer_price = find_first_valid_float(
        payload,
        {
            "offer_price",
            "offerPrice",
            "issue_price",
            "issuePrice",
            "ipo_price",
            "ipoPrice",
            "final_offer_price",
            "finalOfferPrice",
            "listing_price",
            "listingPrice",
        },
    )
    fetched_at = datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now()
    return GreyMarketQuote(
        price=round(price, 3),
        fetched_at=fetched_at,
        source="富途暗盘行情",
        offer_price=round(offer_price, 3) if offer_price and offer_price > 0 else None,
        reference_label="最新招股价" if offer_price and offer_price > 0 else None,
    )


def fetch_tencent_hk_quote(code: str) -> GreyMarketQuote | None:
    url = f"https://qt.gtimg.cn/q=hk{code}"
    try:
        response = httpx.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}, trust_env=False)
        response.raise_for_status()
    except Exception:
        return None
    match = re.search(r'="([^"]+)"', response.text)
    if not match:
        return None
    fields = match.group(1).split("~")
    candidates = []
    for index in (3, 6, 4):
        if index < len(fields):
            candidates.append(fields[index])
    price = next((value for value in (parse_float(item) for item in candidates) if value and value > 0), None)
    if price is None:
        return None
    previous_close = parse_float(fields[4]) if len(fields) > 4 else None
    quote_time = next((item for item in fields if re.match(r"^20\d{2}[-/]\d{2}[-/]\d{2} \d{2}:\d{2}", item)), "")
    return GreyMarketQuote(
        price=round(price, 3),
        fetched_at=parse_quote_time(quote_time),
        source="腾讯港股行情",
        offer_price=round(previous_close, 3) if previous_close and previous_close > 0 else None,
        reference_label="昨日收盘价" if previous_close and previous_close > 0 else None,
    )


def fetch_yahoo_hk_quote(code: str) -> GreyMarketQuote | None:
    symbol = f"{code}.HK"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m"
    try:
        response = httpx.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, trust_env=False)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    results = (((payload.get("chart") or {}).get("result") or []))
    if not results:
        return None
    meta = results[0].get("meta") or {}
    price = parse_float(meta.get("regularMarketPrice"))
    previous_close = parse_float(meta.get("regularMarketPreviousClose"))
    if previous_close is None:
        previous_close = parse_float(meta.get("chartPreviousClose"))
    timestamp = meta.get("regularMarketTime")
    if price is None or price <= 0:
        return None
    fetched_at = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
    return GreyMarketQuote(
        price=round(price, 3),
        fetched_at=fetched_at,
        source="Yahoo Finance 港股行情",
        offer_price=round(previous_close, 3) if previous_close and previous_close > 0 else None,
        reference_label="昨日收盘价" if previous_close and previous_close > 0 else None,
    )


def quote_to_metrics(metrics_json: str, quote: GreyMarketQuote, offer_price: float, finalized: bool | None = None) -> dict:
    metrics = json.loads(metrics_json)
    reference_price = quote.offer_price if quote.offer_price and quote.offer_price > 0 else offer_price
    metrics["grey_market_price"] = quote.price
    metrics["grey_market_offer_price"] = quote.offer_price
    metrics["grey_market_reference_price"] = reference_price
    metrics["grey_market_reference_label"] = (quote.reference_label or "最新招股价") if quote.offer_price else "招股价上限"
    metrics["grey_market_fetched_at"] = quote.fetched_at.isoformat(timespec="seconds")
    metrics["grey_market_source"] = quote.source
    metrics["grey_market_change_pct"] = None if reference_price <= 0 else round((quote.price / reference_price - 1) * 100, 2)
    if finalized is not None:
        metrics["grey_market_finalized"] = finalized
    return metrics


def parse_float(value) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def find_first_valid_float(payload, keys: set[str]) -> float | None:
    if isinstance(payload, dict):
        for key, raw_value in payload.items():
            if key in keys:
                value = parse_float(raw_value)
                if value is not None and value > 0:
                    return value
        for raw_value in payload.values():
            value = find_first_valid_float(raw_value, keys)
            if value is not None:
                return value
    if isinstance(payload, list):
        for item in payload:
            value = find_first_valid_float(item, keys)
            if value is not None:
                return value
    return None


def parse_quote_time(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.now()
