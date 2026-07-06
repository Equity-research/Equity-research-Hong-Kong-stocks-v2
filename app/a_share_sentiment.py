import csv
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.config import DATA_DIR, DB_PATH


CN_TZ = ZoneInfo("Asia/Shanghai")
MARKET_URLS = [
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://90.push2.eastmoney.com/api/qt/clist/get",
    "https://31.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
]
MARKET_PARAMS = (
    "po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
    "&fltt=2&invt=2&fid=f2&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
    "&fields=f12,f14,f2,f3,f4,f5,f6"
)
GUBA_URLS = [
    ("东方财富股吧-上证指数", "https://guba.eastmoney.com/list,zssh000001.html"),
    ("东方财富股吧-深证成指", "https://guba.eastmoney.com/list,zssz399001.html"),
    ("东方财富股吧-创业板指", "https://guba.eastmoney.com/list,zssz399006.html"),
]
BOARD_PARAMS = (
    "po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
    "&fltt=2&invt=2&fid=f3&fs=m:90+t:2,m:90+t:3"
    "&fields=f12,f14,f2,f3,f4,f5,f6,f8,f62,f128,f140,f136"
)
FALLBACK_MARKET = [
    {"code": "000001", "name": "上证指数样本", "price": 0.0, "change_pct": 0.0, "change": 0.0, "volume": 0.0, "amount": 0.0},
]
FALLBACK_TITLES = [
    "市场震荡 资金观望 热点轮动",
    "成交活跃 题材分化 风险偏好修复",
    "权重企稳 低位补涨 谨慎追高",
]
WORD_WEIGHTS = {
    "上涨": 2,
    "涨停": 3,
    "大涨": 3,
    "反弹": 2,
    "突破": 2,
    "企稳": 1,
    "回暖": 2,
    "修复": 1,
    "机会": 1,
    "牛市": 3,
    "增量资金": 2,
    "主线": 1,
    "下跌": -2,
    "跌停": -3,
    "大跌": -3,
    "跳水": -3,
    "回调": -1,
    "杀跌": -3,
    "套牢": -2,
    "风险": -1,
    "谨慎": -1,
    "观望": -1,
    "震荡": 0,
    "分化": 0,
    "轮动": 0,
    "成交": 0,
    "热点": 1,
}


@dataclass(frozen=True)
class MarketRow:
    code: str
    name: str
    price: float
    change_pct: float
    change: float
    volume: float
    amount: float


@dataclass(frozen=True)
class HotWord:
    word: str
    count: int
    sentiment: str
    weight: int


@dataclass(frozen=True)
class HotSector:
    code: str
    name: str
    price: float
    change_pct: float
    turnover_rate: float
    amount: float
    main_inflow: float
    leading_stock: str
    leading_stock_code: str
    leading_stock_change_pct: float


def market_path(record_date: date) -> Path:
    return DATA_DIR / f"a_share_market_{record_date.isoformat()}.csv"


def hot_words_path(record_date: date) -> Path:
    return DATA_DIR / f"a_share_hot_words_{record_date.isoformat()}.csv"


def hot_sectors_path(record_date: date) -> Path:
    return DATA_DIR / f"a_share_hot_sectors_{record_date.isoformat()}.csv"


def build_a_share_sentiment(record_date: date | None = None, refresh: bool = False) -> dict:
    record_date = record_date or datetime.now(CN_TZ).date()
    generated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
    market_rows: list[MarketRow] = []
    hot_sectors: list[HotSector] = []
    hot_words: list[HotWord] = []
    market_source = "本地最近行情CSV"
    sector_source = "本地最近板块CSV"
    title_sources = ["本地最近热词CSV"]

    if not refresh:
        market_rows = load_latest_market_rows(record_date)
        hot_words = load_latest_hot_words(record_date)
        hot_sectors = load_latest_hot_sectors(record_date)

    if refresh or not market_rows:
        market_rows, market_source = fetch_market_rows()
    if refresh or not hot_sectors:
        hot_sectors, sector_source = fetch_hot_sectors()
    if refresh or not hot_words:
        titles, title_sources = fetch_discussion_titles()
        if not titles:
            titles = FALLBACK_TITLES
            title_sources = ["fallback"]
        hot_words = extract_hot_words(titles)

    if not market_rows:
        market_rows = load_latest_market_rows(record_date)
        market_source = "本地最近行情CSV" if market_rows else "fallback"
    if not hot_sectors:
        hot_sectors = load_latest_hot_sectors(record_date)
        sector_source = "本地最近板块CSV" if hot_sectors else "fallback"
    if not market_rows:
        market_rows = [MarketRow(**row) for row in FALLBACK_MARKET]
    if not hot_words:
        hot_words = extract_hot_words(FALLBACK_TITLES)
        title_sources = ["fallback"]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    market_file = write_market_rows(record_date, generated_at, market_rows, market_source)
    hot_words_file = write_hot_words(record_date, generated_at, hot_words, title_sources)
    hot_sectors_file = write_hot_sectors(record_date, generated_at, hot_sectors, sector_source)
    priced_rows = [row for row in market_rows if row.price > 0]
    average_price = round(sum(row.price for row in priced_rows) / max(1, len(priced_rows)), 2)
    average_change_pct = round(sum(row.change_pct for row in market_rows) / len(market_rows), 2)
    up_count = len([row for row in market_rows if row.change_pct > 0])
    down_count = len([row for row in market_rows if row.change_pct < 0])
    sentiment_score = calculate_sentiment_score(market_rows, hot_words)

    result = {
        "record_date": record_date.isoformat(),
        "generated_at": generated_at,
        "average_price": average_price,
        "average_change_pct": average_change_pct,
        "stock_count": len(market_rows),
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": len(market_rows) - up_count - down_count,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label(sentiment_score, len(priced_rows)),
        "market_source": market_source,
        "hot_word_sources": title_sources,
        "sector_source": sector_source,
        "market_file": str(market_file),
        "hot_words_file": str(hot_words_file),
        "hot_sectors_file": str(hot_sectors_file),
        "hot_words": [word.__dict__ for word in hot_words],
        "hot_sectors": [sector.__dict__ for sector in hot_sectors[:20]],
        "market_sample": [row.__dict__ for row in market_rows[:20]],
    }
    maybe_record_close_sentiment(result)
    return result


def latest_sentiment_history(limit: int = 15) -> list[dict]:
    ensure_history_table()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT * FROM a_share_sentiment_history
            ORDER BY record_date DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in reversed(rows)]


def maybe_record_close_sentiment(payload: dict) -> None:
    generated_at = datetime.fromisoformat(payload["generated_at"])
    valid_market = payload["stock_count"] >= 100 and payload["average_price"] > 0
    if generated_at.time().hour < 15 or not valid_market:
        return
    ensure_history_table()
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            INSERT INTO a_share_sentiment_history
              (record_date, generated_at, sentiment_score, sentiment_label, average_price,
               average_change_pct, stock_count, up_count, down_count, flat_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_date) DO UPDATE SET
              generated_at=excluded.generated_at,
              sentiment_score=excluded.sentiment_score,
              sentiment_label=excluded.sentiment_label,
              average_price=excluded.average_price,
              average_change_pct=excluded.average_change_pct,
              stock_count=excluded.stock_count,
              up_count=excluded.up_count,
              down_count=excluded.down_count,
              flat_count=excluded.flat_count
        """, (
            payload["record_date"], payload["generated_at"], payload["sentiment_score"], payload["sentiment_label"],
            payload["average_price"], payload["average_change_pct"], payload["stock_count"], payload["up_count"],
            payload["down_count"], payload["flat_count"],
        ))


def ensure_history_table() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS a_share_sentiment_history (
              record_date TEXT PRIMARY KEY, generated_at TEXT NOT NULL, sentiment_score INTEGER NOT NULL,
              sentiment_label TEXT NOT NULL, average_price REAL NOT NULL, average_change_pct REAL NOT NULL,
              stock_count INTEGER NOT NULL, up_count INTEGER NOT NULL, down_count INTEGER NOT NULL,
              flat_count INTEGER NOT NULL
            )
        """)


def fetch_market_rows() -> tuple[list[MarketRow], str]:
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
    for base_url in MARKET_URLS:
        rows: list[MarketRow] = []
        seen: set[str] = set()
        try:
            with httpx.Client(timeout=12, follow_redirects=True, headers=headers) as client:
                for page in range(1, 80):
                    response = client.get(f"{base_url}?pn={page}&pz=100&{MARKET_PARAMS}")
                    response.raise_for_status()
                    payload = response.json()
                    data = payload.get("data") or {}
                    items = data.get("diff") or []
                    if not items:
                        break
                    for item in items:
                        row = market_row_from_item(item)
                        if row and row.code not in seen:
                            rows.append(row)
                            seen.add(row.code)
                    total = int(data.get("total") or 0)
                    if total and len(rows) >= total:
                        break
            if rows:
                return rows, "东方财富行情快照"
        except Exception:
            continue
    return [], "fallback"


def market_row_from_item(item: dict) -> MarketRow | None:
    price = parse_float(item.get("f2"))
    if price is None or price <= 0:
        return None
    return MarketRow(
        code=str(item.get("f12", "")).strip(),
        name=str(item.get("f14", "")).strip(),
        price=price,
        change_pct=parse_float(item.get("f3")) or 0.0,
        change=parse_float(item.get("f4")) or 0.0,
        volume=parse_float(item.get("f5")) or 0.0,
        amount=parse_float(item.get("f6")) or 0.0,
    )


def load_latest_market_rows(record_date: date) -> list[MarketRow]:
    latest = latest_data_path("a_share_market_", record_date)
    if not latest:
        return []
    with latest.open(encoding="utf-8-sig", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            market_row = MarketRow(
                code=row.get("code", ""),
                name=row.get("name", ""),
                price=parse_float(row.get("price")) or 0.0,
                change_pct=parse_float(row.get("change_pct")) or 0.0,
                change=parse_float(row.get("change")) or 0.0,
                volume=parse_float(row.get("volume")) or 0.0,
                amount=parse_float(row.get("amount")) or 0.0,
            )
            if market_row.price > 0:
                rows.append(market_row)
        return rows


def load_latest_hot_words(record_date: date) -> list[HotWord]:
    latest = latest_data_path("a_share_hot_words_", record_date)
    if not latest:
        return []
    with latest.open(encoding="utf-8-sig", newline="") as handle:
        return [
            HotWord(
                word=row.get("word", ""),
                count=int(parse_float(row.get("count")) or 0),
                sentiment=row.get("sentiment", "neutral"),
                weight=int(parse_float(row.get("weight")) or 0),
            )
            for row in csv.DictReader(handle)
            if row.get("word")
        ]


def load_latest_hot_sectors(record_date: date) -> list[HotSector]:
    latest = latest_data_path("a_share_hot_sectors_", record_date)
    if not latest:
        return []
    with latest.open(encoding="utf-8-sig", newline="") as handle:
        sectors = []
        for row in csv.DictReader(handle):
            sector = HotSector(
                code=row.get("code", ""),
                name=row.get("name", ""),
                price=parse_float(row.get("price")) or 0.0,
                change_pct=parse_float(row.get("change_pct")) or 0.0,
                turnover_rate=parse_float(row.get("turnover_rate")) or 0.0,
                amount=parse_float(row.get("amount")) or 0.0,
                main_inflow=parse_float(row.get("main_inflow")) or 0.0,
                leading_stock=row.get("leading_stock", ""),
                leading_stock_code=row.get("leading_stock_code", ""),
                leading_stock_change_pct=parse_float(row.get("leading_stock_change_pct")) or 0.0,
            )
            if sector.code and sector.name:
                sectors.append(sector)
        return sectors


def latest_data_path(prefix: str, record_date: date) -> Path | None:
    candidates = []
    for path in DATA_DIR.glob(f"{prefix}*.csv"):
        try:
            candidate_date = date.fromisoformat(path.stem.removeprefix(prefix))
        except ValueError:
            continue
        if candidate_date <= record_date:
            candidates.append((candidate_date, path))
    return max(candidates, default=(None, None))[1]


def fetch_hot_sectors() -> tuple[list[HotSector], str]:
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/center/boardlist.html"}
    for base_url in MARKET_URLS:
        try:
            with httpx.Client(timeout=12, follow_redirects=True, headers=headers) as client:
                response = client.get(f"{base_url}?pn=1&pz=30&{BOARD_PARAMS}")
                response.raise_for_status()
                payload = response.json()
            sectors = []
            for item in (payload.get("data") or {}).get("diff") or []:
                sector = hot_sector_from_item(item)
                if sector:
                    sectors.append(sector)
            if sectors:
                return sectors, "东方财富板块行情"
        except Exception:
            continue
    return [], "fallback"


def hot_sector_from_item(item: dict) -> HotSector | None:
    code = str(item.get("f12", "")).strip()
    name = str(item.get("f14", "")).strip()
    if not code or not name:
        return None
    return HotSector(
        code=code,
        name=name,
        price=parse_float(item.get("f2")) or 0.0,
        change_pct=parse_float(item.get("f3")) or 0.0,
        turnover_rate=parse_float(item.get("f8")) or 0.0,
        amount=parse_float(item.get("f6")) or 0.0,
        main_inflow=parse_float(item.get("f62")) or 0.0,
        leading_stock=str(item.get("f128", "") or "").strip(),
        leading_stock_code=str(item.get("f140", "") or "").strip(),
        leading_stock_change_pct=parse_float(item.get("f136")) or 0.0,
    )


def fetch_discussion_titles() -> tuple[list[str], list[str]]:
    titles: list[str] = []
    sources: list[str] = []
    with httpx.Client(timeout=12, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for name, url in GUBA_URLS:
            try:
                response = client.get(url)
                response.raise_for_status()
            except Exception:
                continue
            page_titles = parse_titles(response.text)
            if page_titles:
                titles.extend(page_titles)
                sources.append(name)
    return titles, sources


def parse_titles(html: str) -> list[str]:
    html = unescape(html)
    matches = re.findall(r'title=["\']([^"\']{4,80})["\']', html)
    matches.extend(re.findall(r'class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]{4,80})<', html))
    matches.extend(re.findall(r'<div class=["\']title["\']>\s*<a[^>]*>([^<]{2,100})</a>', html))
    cleaned = []
    for title in matches:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title)).strip()
        if text and "东方财富" not in text and text not in cleaned:
            cleaned.append(text)
    return cleaned[:80]


def extract_hot_words(titles: list[str]) -> list[HotWord]:
    text = " ".join(titles)
    counter: Counter[str] = Counter()
    for word in WORD_WEIGHTS:
        count = text.count(word)
        if count:
            counter[word] += count
    for token in re.findall(r"[\u4e00-\u9fa5]{2,6}", text):
        if token in WORD_WEIGHTS:
            continue
        if token in {"股吧", "东方", "财富", "上证", "指数", "深证", "创业板"}:
            continue
        if any(key in token for key in ("涨", "跌", "资金", "主力", "市场", "热点", "风险", "震荡", "成交")):
            counter[token] += 1
    if not counter:
        counter.update({"震荡": 3, "观望": 2, "热点": 2, "修复": 1})
    return [
        HotWord(word=word, count=count, sentiment=word_sentiment(word), weight=WORD_WEIGHTS.get(word, 0))
        for word, count in counter.most_common(16)
    ]


def write_market_rows(record_date: date, generated_at: str, rows: list[MarketRow], source: str) -> Path:
    path = market_path(record_date)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["record_date", "generated_at", "code", "name", "price", "change_pct", "change", "volume", "amount", "source"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"record_date": record_date.isoformat(), "generated_at": generated_at, **row.__dict__, "source": source})
    return path


def write_hot_words(record_date: date, generated_at: str, hot_words: list[HotWord], sources: list[str]) -> Path:
    path = hot_words_path(record_date)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["record_date", "generated_at", "word", "count", "sentiment", "weight", "sources"])
        writer.writeheader()
        for word in hot_words:
            writer.writerow({"record_date": record_date.isoformat(), "generated_at": generated_at, **word.__dict__, "sources": ";".join(sources)})
    return path


def write_hot_sectors(record_date: date, generated_at: str, sectors: list[HotSector], source: str) -> Path:
    path = hot_sectors_path(record_date)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "record_date", "generated_at", "code", "name", "price", "change_pct", "turnover_rate",
            "amount", "main_inflow", "leading_stock", "leading_stock_code", "leading_stock_change_pct", "source",
        ])
        writer.writeheader()
        for sector in sectors:
            writer.writerow({"record_date": record_date.isoformat(), "generated_at": generated_at, **sector.__dict__, "source": source})
    return path


def calculate_sentiment_score(market_rows: list[MarketRow], hot_words: list[HotWord]) -> int:
    priced_rows = [row for row in market_rows if row.price > 0]
    if len(priced_rows) < 100:
        return 50

    average_change_pct = sum(row.change_pct for row in priced_rows) / len(priced_rows)
    up_count = len([row for row in priced_rows if row.change_pct > 0])
    down_count = len([row for row in priced_rows if row.change_pct < 0])
    breadth = (up_count - down_count) / len(priced_rows)
    market_score = 50 + max(-5, min(5, average_change_pct)) * 6 + breadth * 25

    positive = sum(word.count * max(0, word.weight) for word in hot_words)
    negative = sum(word.count * abs(min(0, word.weight)) for word in hot_words)
    if positive + negative:
        hot_word_score = 50 + ((positive - negative) / (positive + negative)) * 20
    else:
        hot_word_score = 50

    return round(max(0, min(100, market_score * 0.75 + hot_word_score * 0.25)))


def sentiment_label(score: int, valid_market_count: int = 0) -> str:
    if valid_market_count < 100:
        return "数据不足"
    if score >= 70:
        return "偏热"
    if score >= 55:
        return "回暖"
    if score >= 45:
        return "中性"
    if score >= 30:
        return "谨慎"
    return "低迷"


def word_sentiment(word: str) -> str:
    weight = WORD_WEIGHTS.get(word, 0)
    if weight > 0:
        return "positive"
    if weight < 0:
        return "negative"
    return "neutral"


def parse_float(value: object) -> float | None:
    try:
        if value in (None, "-", ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
