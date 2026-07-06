import json
import re
from json import JSONDecodeError
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

import httpx

from app.config import DATA_DIR


CN_TZ = ZoneInfo("Asia/Shanghai")
NEWS_TIMEOUT = 10
ARTICLE_TIMEOUT = 6
NEWS_LIMIT = 5
GOOGLE_NEWS_RSS_CN = "https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=US&ceid=US:zh-Hans"
GOOGLE_NEWS_RSS_EN = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
QQQ_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?range=1mo&interval=1d"

MODULES = [
    {
        "key": "semiconductors",
        "name": "半导体",
        "query": "美股 半导体 芯片 英伟达 台积电 博通 人工智能 资本开支",
        "query_en": "semiconductor chips Nvidia TSMC Broadcom market stocks AI capex",
        "focus": "人工智能算力、晶圆代工、先进封装和设备订单",
    },
    {
        "key": "optical_modules",
        "name": "光模块",
        "query": "美股 光模块 光通信 数据中心 人工智能 800G 1.6T",
        "query_en": "optical transceiver module datacenter AI 800G 1.6T market stocks",
        "focus": "人工智能数据中心带动 800G/1.6T 光模块需求",
    },
    {
        "key": "memory_chips",
        "name": "内存芯片",
        "query": "美股 DRAM HBM 美光 三星 SK海力士 CXMT 内存芯片 存储芯片 -ETF -基金",
        "query_en": "\"DRAM\" \"HBM\" Micron Samsung \"SK Hynix\" CXMT memory chip stocks -ETF -fund",
        "focus": "高带宽内存、DRAM 合约价、人工智能服务器内存需求和存储厂库存周期",
    },
    {
        "key": "aerospace",
        "name": "航天",
        "query": "美股 航天 国防 商业发射 卫星 股票",
        "query_en": "aerospace defense space launch satellite stocks market",
        "focus": "国防预算、商业航天发射和卫星链路需求",
    },
    {
        "key": "robotics",
        "name": "机器人",
        "query": "美股 机器人 人形机器人 自动化 特斯拉 英伟达 股票",
        "query_en": "robotics humanoid automation Tesla Nvidia market stocks",
        "focus": "人形机器人、工厂自动化和人工智能边缘控制器",
    },
    {
        "key": "dollar",
        "name": "美元",
        "query": "美元指数 美联储 美债收益率 全球市场",
        "query_en": "US dollar DXY Federal Reserve yields global markets",
        "focus": "美联储路径、美国收益率和全球风险偏好",
    },
    {
        "key": "gold",
        "name": "黄金",
        "query": "黄金价格 美联储 美元 地缘政治 市场",
        "query_en": "gold price Federal Reserve dollar geopolitical market",
        "focus": "实际利率、美元方向和避险需求",
    },
]

POSITIVE_WORDS = {
    "rise",
    "rises",
    "rally",
    "surge",
    "surges",
    "gain",
    "gains",
    "strong",
    "record",
    "beat",
    "upgrade",
    "growth",
    "demand",
    "deal",
    "launch",
    "optimism",
}
NEGATIVE_WORDS = {
    "fall",
    "falls",
    "drop",
    "drops",
    "slump",
    "loss",
    "losses",
    "weak",
    "warning",
    "downgrade",
    "risk",
    "tariff",
    "probe",
    "delay",
    "cuts",
    "concern",
}


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    url: str
    published_at: str | None
    title_zh: str | None = None
    source_zh: str | None = None
    article_title_zh: str | None = None
    article_summary_zh: str | None = None
    article_body_zh: str | None = None
    article_key_points_zh: list[str] | None = None
    original_url: str | None = None
    original_title: str | None = None
    original_body: str | None = None
    original_saved_at: str | None = None


def cache_path(record_date: date) -> Path:
    return DATA_DIR / f"us_market_news_{record_date.isoformat()}.json"


def build_us_market_dashboard(record_date: date | None = None, refresh: bool = False) -> dict:
    record_date = record_date or datetime.now(CN_TZ).date()
    path = cache_path(record_date)
    if not refresh and path.exists():
        try:
            return normalize_dashboard(json.loads(path.read_text(encoding="utf-8")))
        except JSONDecodeError:
            pass

    generated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
    modules = [build_module(module) for module in MODULES]
    qqq_quote = fetch_qqq_quote()
    qqq_history = fetch_qqq_history()
    qqq_news = fetch_news_items("纳指100 ETF QQQ 科技股 美股 市场", NEWS_LIMIT, "QQQ Nasdaq 100 ETF technology stocks market")
    qqq = build_qqq_section(qqq_quote, qqq_history, qqq_news)
    highlights = build_highlights(modules, qqq)
    payload = {
        "record_date": record_date.isoformat(),
        "generated_at": generated_at,
        "source": "谷歌新闻 RSS / 雅虎财经 QQQ",
        "cache_file": str(path),
        "modules": modules,
        "qqq": qqq,
        "highlights": highlights,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return payload


def build_module(module: dict) -> dict:
    news = fetch_news_items(module["query"], NEWS_LIMIT, module.get("query_en"))
    news = filter_module_news(module["key"], news)
    score = score_news(news)
    trend = trend_label(score)
    return {
        "key": module["key"],
        "name": module["name"],
        "focus": module["focus"],
        "sentiment_score": score,
        "trend": trend,
        "analysis": module_analysis(module["name"], module["focus"], score, news),
        "news": [news_item_dict(item) for item in news],
    }


def filter_module_news(module_key: str, news: list[NewsItem]) -> list[NewsItem]:
    if module_key not in {"memory_chips", "ram"}:
        return news
    filtered = [item for item in news if is_memory_chip_news(item.title)]
    return filtered or news


def is_memory_chip_news(title: str) -> bool:
    lower = title.lower()
    if any(term in lower for term in ("etf", "fund", "random access memory etf", "ram etf")):
        return False
    memory_terms = (
        "dram",
        "hbm",
        "memory",
        "micron",
        "samsung",
        "sk hynix",
        "cxmt",
        "changxin",
        "存储",
        "内存",
        "美光",
        "三星",
        "海力士",
        "长鑫",
        "高带宽内存",
    )
    return any(term in lower for term in memory_terms)


def build_qqq_section(quote: dict, history: list[dict], news: list[NewsItem]) -> dict:
    change_pct = quote.get("change_pct")
    news_score = score_news(news)
    price_score = 0 if change_pct is None else max(-2, min(2, round(change_pct)))
    score = news_score + price_score
    return {
        "symbol": "QQQ",
        "price": quote.get("price"),
        "change": quote.get("change"),
        "change_pct": change_pct,
        "quote_time": quote.get("quote_time"),
        "trend": trend_label(score),
        "analysis": qqq_analysis(change_pct, score, news),
        "history": history[-15:],
        "news": [news_item_dict(item) for item in news],
    }


def fetch_news_items(query: str, limit: int = NEWS_LIMIT, fallback_query: str | None = None) -> list[NewsItem]:
    items = fetch_news_items_from_rss(GOOGLE_NEWS_RSS_CN.format(query=quote_plus(query)), limit)
    if not items and fallback_query:
        items = fetch_news_items_from_rss(GOOGLE_NEWS_RSS_EN.format(query=quote_plus(fallback_query)), limit)
    return items


def fetch_news_items_from_rss(url: str, limit: int) -> list[NewsItem]:
    try:
        response = httpx.get(url, timeout=NEWS_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return []
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return []
    items: list[NewsItem] = []
    for item in root.findall("./channel/item")[:limit]:
        title = clean_text(item.findtext("title") or "")
        source = clean_text(item.findtext("source") or infer_source(title) or "Google News")
        link = item.findtext("link") or ""
        published = item.findtext("pubDate")
        if title:
            article = fetch_article_digest(link, title)
            items.append(NewsItem(
                title=title,
                source=source,
                url=link,
                published_at=published,
                title_zh=chinese_news_title(title),
                source_zh=chinese_source_name(source),
                article_title_zh=article["title_zh"],
                article_summary_zh=article["summary_zh"],
                article_body_zh=article["body_zh"],
                article_key_points_zh=article["key_points_zh"],
                original_url=article["original_url"],
                original_title=article["original_title"],
                original_body=article["original_body"],
                original_saved_at=article["original_saved_at"],
            ))
    return items


def fetch_qqq_quote() -> dict:
    chart = fetch_qqq_chart()
    if not chart:
        return {}
    meta = chart.get("meta") or {}
    price = parse_float(meta.get("regularMarketPrice"))
    previous = parse_float(meta.get("chartPreviousClose") or meta.get("previousClose"))
    change = None if price is None or previous is None else round(price - previous, 2)
    change_pct = None if change is None or previous in (None, 0) else round(change / previous * 100, 2)
    quote_time = meta.get("regularMarketTime")
    return {
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "quote_time": datetime.fromtimestamp(quote_time, CN_TZ).isoformat(timespec="minutes") if quote_time else None,
    }


def fetch_qqq_history(limit: int = 15) -> list[dict]:
    chart = fetch_qqq_chart()
    if not chart:
        return []
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    history = []
    for index, timestamp in enumerate(timestamps[-limit:]):
        source_index = len(timestamps) - len(timestamps[-limit:]) + index
        close = parse_float(closes[source_index] if source_index < len(closes) else None)
        open_price = parse_float(opens[source_index] if source_index < len(opens) else None)
        high = parse_float(highs[source_index] if source_index < len(highs) else None)
        low = parse_float(lows[source_index] if source_index < len(lows) else None)
        change_pct = None if close is None or open_price in (None, 0) else round((close - open_price) / open_price * 100, 2)
        history.append({
            "date": datetime.fromtimestamp(timestamp, CN_TZ).date().isoformat(),
            "open": None if open_price is None else round(open_price, 2),
            "high": None if high is None else round(high, 2),
            "low": None if low is None else round(low, 2),
            "close": None if close is None else round(close, 2),
            "change_pct": change_pct,
        })
    return history


def fetch_qqq_chart() -> dict:
    try:
        response = httpx.get(QQQ_CHART_URL, timeout=NEWS_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        data = response.json()
    except Exception:
        return {}
    results = ((data.get("chart") or {}).get("result") or [])
    return results[0] if results else {}


def score_news(news: list[NewsItem]) -> int:
    score = 0
    for item in news:
        words = set(re.findall(r"[a-zA-Z]+", item.title.lower()))
        score += len(words & POSITIVE_WORDS)
        score -= len(words & NEGATIVE_WORDS)
    return max(-8, min(8, score))


def trend_label(score: int) -> str:
    if score >= 3:
        return "偏强"
    if score <= -3:
        return "承压"
    return "震荡观察"


def module_analysis(name: str, focus: str, score: int, news: list[NewsItem]) -> str:
    if not news:
        return f"{name}暂无可用新闻，先按中性处理；后续重点看{focus}。"
    if score >= 3:
        return f"{name}新闻偏正面，短线关注风险偏好延续；核心变量是{focus}。"
    if score <= -3:
        return f"{name}新闻偏负面，短线可能继续消化压力；需要等待{focus}出现改善信号。"
    return f"{name}消息面分化，后续大概率围绕{focus}做区间震荡和轮动。"


def qqq_analysis(change_pct: float | None, score: int, news: list[NewsItem]) -> str:
    move = "暂无最新行情" if change_pct is None else f"最新日内变动约 {change_pct:.2f}%"
    if score >= 3:
        return f"QQQ {move}，新闻与价格信号偏强，纳指科技权重仍有上行动能，但需要观察利率和龙头财报兑现。"
    if score <= -3:
        return f"QQQ {move}，新闻与价格信号偏弱，短线更容易受估值、利率或大型科技股波动压制。"
    return f"QQQ {move}，当前信号中性，后续重点看大型科技股新闻、美元利率和成交量能否配合。"


def build_highlights(modules: list[dict], qqq: dict) -> list[str]:
    strong = [item["name"] for item in modules if item["trend"] == "偏强"]
    weak = [item["name"] for item in modules if item["trend"] == "承压"]
    highlights = []
    if strong:
        highlights.append(f"偏强模块：{'、'.join(strong)}，短线更适合关注顺势延续。")
    if weak:
        highlights.append(f"承压模块：{'、'.join(weak)}，先等利空钝化或资金回流。")
    if not highlights:
        highlights.append("行业新闻整体分化，美股风险偏好仍处在观察区间。")
    highlights.append(f"QQQ 当前判断：{qqq['trend']}。{qqq['analysis']}")
    return highlights


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalize_dashboard(payload: dict) -> dict:
    for module in payload.get("modules", []):
        if module.get("key") == "ram":
            module["key"] = "memory_chips"
        if module.get("key") == "memory_chips":
            module["name"] = "内存芯片"
        module["focus"] = localize_market_text(module.get("focus", ""))
        module["analysis"] = localize_market_text(module.get("analysis", ""))
        module["news"] = [normalize_news_dict(item) for item in module.get("news", [])]
    qqq = payload.get("qqq") or {}
    qqq["analysis"] = localize_market_text(qqq.get("analysis", ""))
    qqq["history"] = [normalize_history_point(item) for item in qqq.get("history", [])]
    qqq["news"] = [normalize_news_dict(item) for item in qqq.get("news", [])]
    payload["qqq"] = qqq
    payload["highlights"] = [localize_market_text(text) for text in payload.get("highlights", [])]
    payload["source"] = "谷歌新闻 RSS / 雅虎财经 QQQ"
    return payload


def normalize_news_dict(item: dict) -> dict:
    title = item.get("title", "")
    source = item.get("source", "")
    item["title_zh"] = chinese_news_title(title) if title else item.get("title_zh") or "美股新闻动态"
    item["source_zh"] = item.get("source_zh") or chinese_source_name(source)
    article = normalize_article_digest(item)
    item["article_title_zh"] = article["title_zh"] if is_generic_article_text(item.get("article_title_zh")) else item.get("article_title_zh") or article["title_zh"]
    item["article_summary_zh"] = article["summary_zh"] if is_generic_article_text(item.get("article_summary_zh")) else item.get("article_summary_zh") or article["summary_zh"]
    item["article_body_zh"] = article["body_zh"] if is_generic_article_text(item.get("article_body_zh")) else item.get("article_body_zh") or article["body_zh"]
    item["article_key_points_zh"] = item.get("article_key_points_zh") or article["key_points_zh"]
    item["original_url"] = item.get("original_url") or item.get("url")
    item["original_title"] = item.get("original_title") or ""
    item["original_body"] = item.get("original_body") or ""
    item["original_saved_at"] = item.get("original_saved_at")
    return item


def is_generic_article_text(value: str | None) -> bool:
    if not value:
        return False
    compact = value.replace(" ", "")
    markers = (
        "Google新闻",
        "谷歌新闻",
        "美股相关资产",
        "市场交易线索",
        "消息倾向偏中性",
        "链接页正文暂未提取",
        "链接页暂未提取",
    )
    return any(marker in compact for marker in markers)


def news_item_dict(item: NewsItem) -> dict:
    return normalize_news_dict(item.__dict__.copy())


def normalize_history_point(item: dict) -> dict:
    close = item.get("close")
    item["open"] = item.get("open", close)
    item["high"] = item.get("high", max(value for value in [item.get("open"), close] if value is not None) if close is not None else None)
    item["low"] = item.get("low", min(value for value in [item.get("open"), close] if value is not None) if close is not None else None)
    return item


def localize_market_text(value: str) -> str:
    replacements = {
        "RAM": "内存芯片",
        "AI": "人工智能",
        "Google News RSS / Yahoo Finance QQQ": "谷歌新闻 RSS / 雅虎财经 QQQ",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def chinese_news_title(title: str) -> str:
    title = clean_text(title)
    if re.search(r"[\u4e00-\u9fff]", title):
        return translate_title_fragment(strip_source_suffix(title))
    title = strip_english_source_tail(title)
    literal = literal_chinese_title(title)
    if literal:
        return literal
    lower = title.lower()
    subjects = []
    company_terms = {
        "nvidia": "英伟达",
        "tsmc": "台积电",
        "broadcom": "博通",
        "qualcomm": "高通",
        "micron": "美光",
        "samsung": "三星",
        "sk hynix": "SK海力士",
        "tesla": "特斯拉",
        "qqq": "纳指100ETF",
        "nasdaq 100": "纳指100",
        "nasdaq": "纳斯达克",
    }
    for term, label in company_terms.items():
        if term in lower and label not in subjects:
            subjects.append(label)
    theme_terms = {
        "semiconductor": "半导体",
        "chip": "芯片",
        "memory": "内存",
        "dram": "DRAM",
        "hbm": "高带宽内存",
        "robot": "机器人",
        "space": "航天",
        "satellite": "卫星",
        "defense": "国防",
        "dollar": "美元",
        "gold": "黄金",
        "etf": "ETF",
        "stock": "股票",
        "market": "市场",
    }
    themes = [label for term, label in theme_terms.items() if term in lower]
    if not subjects:
        subjects = themes[:2] or ["美股相关资产"]
    subject = "、".join(subjects[:3])
    if any(word in lower for word in ("rise", "rises", "surge", "surges", "gain", "gains", "rally", "jumps", "up")):
        action = "走强"
    elif any(word in lower for word in ("fall", "falls", "drop", "drops", "slump", "loss", "down", "fell")):
        action = "承压"
    elif any(word in lower for word in ("demand", "growth", "boost", "optimism")):
        action = "需求改善"
    elif any(word in lower for word in ("risk", "concern", "warning", "lawsuit", "probe")):
        action = "风险升温"
    elif any(word in lower for word in ("best", "top", "buy", "picks")):
        return f"{subject}投资线索更新，关注{'、'.join(themes[:3]) or '美股市场'}"
    else:
        action = "出现新动态"
    suffix = f"，关注{'、'.join(themes[:3])}" if themes else ""
    return f"{subject}{action}{suffix}"


def literal_chinese_title(title: str) -> str:
    patterns = [
        (r"^(\d+)\s+Best\s+(.+?)\s+Stocks\s+for\s+(\d{4})$", lambda m: f"{m.group(3)}年{m.group(1)}只最佳{translate_title_fragment(m.group(2))}股票"),
        (r"^Best\s+(.+?)\s+Stocks\s+for\s+(\d{4}):\s+(.+)$", lambda m: f"{m.group(2)}年最佳{translate_title_fragment(m.group(1))}股票：{translate_title_fragment(m.group(3))}"),
        (r"^(.+?)\s+Fell\s+([\d.]+)%\s+Today\.\s+Here.?s\s+Where\s+the\s+Stock\s+Could\s+Head\s+in\s+(\d{4})$", lambda m: f"{translate_title_fragment(m.group(1))}今日下跌{m.group(2)}%，关注{m.group(3)}年股价可能走向"),
        (r"^China\s+Is\s+Coming\s+for\s+Micron.?s\s+Thick\s+Margins$", lambda m: "中国厂商正在冲击美光的高利润率"),
        (r"^Samsung,\s+SK\s+Hynix,?\s+and\s+Micron\s+sued\s+over\s+alleged\s+DRAM\s+price\s+fixing\s+amid\s+record\s+memory\s+costs\s+—\s+lawsuit\s+claims\s+coordinated\s+HBM\s+shift\s+was\s+cover\s+to\s+curtail\s+DDR3\s+and\s+DDR4\s+production$", lambda m: "三星、SK海力士与美光被控操纵DRAM价格：诉讼称三家公司以转向高带宽内存为名削减DDR3和DDR4产量"),
        (r"^DRAM\s+Prices\s+surge\s+700%\s+in\s+Four\s+Years:\s+Micron,\s+Samsung,\s+SK\s+Hynix\s+Hit\s+with\s+US\s+Class-Action\s+Lawsuit\s+Alleging\s+'RAMpocalypse'\s+Conspiracy$", lambda m: "DRAM价格四年上涨700%：美光、三星、SK海力士遭美国集体诉讼，被指合谋推高内存价格"),
        (r"^ChangXin\s+Memory\s+Technologies\s+Inks\s+4\.5\s+Trillion\s+Won\s+DRAM\s+Deal\s+with\s+Tencent$", lambda m: "长鑫存储与腾讯签署4.5万亿韩元DRAM交易"),
        (r"^Global\s+DRAM\s+and\s+HBM\s+Market\s+Share:\s+Quarterly$", lambda m: "全球DRAM与高带宽内存市场份额季度追踪"),
        (r"^Micron\s+maintains\s+edge\s+as\s+Apple\s+sources\s+cheap\s+DRAM\s+from\s+CXMT$", lambda m: "苹果从长鑫存储采购低价DRAM，美光仍保持优势"),
        (r"^Rocket\s+Lab\s+News\s+Has\s+Investors\s+Rethinking\s+Aerospace\s+And\s+Satellite\s+Communication\s+Stocks$", lambda m: "Rocket Lab消息令投资者重新评估航天与卫星通信股票"),
        (r"^The\s+First\s+Major\s+Robotics\s+IPO\s+Is\s+Here:\s+(\d+)\s+Robotics\s+Stocks\s+That\s+Could\s+Run\s+in\s+the\s+Second\s+Half\s+of\s+(\d{4})$", lambda m: f"首个大型机器人IPO来了：{m.group(2)}年下半年可能走强的{m.group(1)}只机器人股票"),
        (r"^US\s+Dollar\s+climbs\s+for\s+fifth\s+straight\s+day\s+as\s+Treasury\s+yields\s+surge$", lambda m: "美元连续第五天上涨，美债收益率大涨"),
        (r"^Tariff\s+shocks,\s+AI\s+frenzy,\s+and\s+'roller-coaster-like\s+volatility'!\s+Six\s+charts\s+review\s+'wild\s+(\d{4})'\s+of\s+U\.S\.\s+stock\s+market\.?$", lambda m: f"关税冲击、人工智能热潮与剧烈波动：六张图回顾{m.group(1)}年美股市场"),
        (r"^Forget\s+(.+?),\s+These\s+Are\s+the\s+(\d+)\s+Best\s+Stocks\s+for\s+(.+)$", lambda m: f"不只看{translate_title_fragment(m.group(1))}：这{m.group(2)}只股票更值得关注，主题是{translate_title_fragment(m.group(3))}"),
        (r"^(.+?)\s+surges?\s+([\d.]+)%:\s+(.+)$", lambda m: f"{translate_title_fragment(m.group(1))}上涨{m.group(2)}%：{translate_title_fragment(m.group(3))}"),
        (r"^(.+?)\s+to\s+emerge\s+as\s+big\s+winners\s+in\s+(.+)$", lambda m: f"{translate_title_fragment(m.group(1))}有望成为{translate_title_fragment(m.group(2))}的大赢家"),
        (r"^(.+?)\s+and\s+(.+?)\s+Expand\s+Partnership\s+to\s+Deliver\s+(.+)$", lambda m: f"{translate_title_fragment(m.group(1))}与{translate_title_fragment(m.group(2))}扩大合作，交付{translate_title_fragment(m.group(3))}"),
    ]
    for pattern, builder in patterns:
        match = re.match(pattern, title, flags=re.I)
        if match:
            return builder(match)
    translated = translate_title_fragment(title)
    return translated if translated != title else ""


def translate_title_fragment(value: str) -> str:
    phrase_replacements = [
        (r"Top\s+(\d+)\s+Ranking,\s+Picks\s+&\s+Risks", r"\1只排名、选择与风险"),
        (r"custom\s+AI\s+chip\s+boom", "定制人工智能芯片热潮"),
        (r"AI.?s\s+Bandwidth\s+Bottleneck", "人工智能带宽瓶颈"),
    ]
    result = value
    for pattern, replacement in phrase_replacements:
        result = re.sub(pattern, replacement, result, flags=re.I)
    replacements = [
        (r"\bNvidia\b", "英伟达"),
        (r"\bApplied Optoelectronics\b", "应用光电"),
        (r"\bRocket Lab\b", "Rocket Lab"),
        (r"\bJensen Huang\b", "黄仁勋"),
        (r"\bTSMC\b", "台积电"),
        (r"\bBroadcom\b", "博通"),
        (r"\bQualcomm\b", "高通"),
        (r"\bMicron\b", "美光"),
        (r"\bSamsung\b", "三星"),
        (r"\bSK Hynix\b", "SK海力士"),
        (r"\bTesla\b", "特斯拉"),
        (r"\bNasdaq 100\b", "纳指100"),
        (r"\bQQQ\b", "QQQ"),
        (r"\bAI\b", "人工智能"),
        (r"\bSemiconductor\b", "半导体"),
        (r"\bSemiconductors\b", "半导体"),
        (r"\bChip\b", "芯片"),
        (r"\bChips\b", "芯片"),
        (r"\bStock\b", "股票"),
        (r"\bStocks\b", "股票"),
        (r"\bETF\b", "ETF"),
        (r"\bETFs\b", "ETF"),
        (r"\bMemory\b", "内存"),
        (r"\bDRAM\b", "DRAM"),
        (r"\bHBM\b", "高带宽内存"),
        (r"\bOptical Transceivers\b", "光模块"),
        (r"\bOptical Module\b", "光模块"),
        (r"\bDatacenter\b", "数据中心"),
        (r"\bData Center\b", "数据中心"),
        (r"\bBandwidth Bottleneck\b", "带宽瓶颈"),
        (r"\bRobotics\b", "机器人"),
        (r"\bHumanoid Robots\b", "人形机器人"),
        (r"\bSpace\b", "航天"),
        (r"\bSatellite\b", "卫星"),
        (r"\bDefense\b", "国防"),
        (r"\bGold\b", "黄金"),
        (r"\bDollar\b", "美元"),
        (r"\bMarket\b", "市场"),
        (r"\bMarkets\b", "市场"),
        (r"\bDemand\b", "需求"),
        (r"\bImproves\b", "改善"),
        (r"\bImprove\b", "改善"),
        (r"\bGrowth\b", "增长"),
        (r"\bRises\b", "上涨"),
        (r"\bRise\b", "上涨"),
        (r"\bGains\b", "上涨"),
        (r"\bGain\b", "上涨"),
        (r"\bSurges\b", "大涨"),
        (r"\bSurge\b", "大涨"),
        (r"\bFalls\b", "下跌"),
        (r"\bFall\b", "下跌"),
        (r"\bRisks\b", "风险"),
        (r"\bRisk\b", "风险"),
        (r"\bRanking\b", "排名"),
        (r"\bPicks\b", "选择"),
        (r"\bTop\b", "前列"),
        (r"\bBest\b", "最佳"),
        (r"\bBuy\b", "买入"),
        (r"\bWhy\b", "为何"),
        (r"\bWhat\b", "什么"),
        (r"\bCould\b", "可能"),
        (r"\bHead\b", "走向"),
        (r"\bInvestors\b", "投资者"),
        (r"\bRethinking\b", "重新评估"),
        (r"\bCommunication\b", "通信"),
        (r"\bFirst Major\b", "首个大型"),
        (r"\bHere\b", "来了"),
        (r"\bRun\b", "走强"),
        (r"\bSecond Half\b", "下半年"),
        (r"\bClimbs\b", "上涨"),
        (r"\bFifth Straight Day\b", "连续第五天"),
        (r"\bTreasury Yields\b", "美债收益率"),
        (r"\bTariff Shocks\b", "关税冲击"),
        (r"\bFrenzy\b", "热潮"),
        (r"\bRoller-Coaster-Like Volatility\b", "剧烈波动"),
        (r"\bSix Charts Review\b", "六张图回顾"),
        (r"\bWild\b", "剧烈波动的"),
        (r"\bU\.S\.\b", "美国"),
        (r"\bWall Street\b", "华尔街"),
        (r"\bPhysical AI\b", "物理人工智能"),
        (r"\bCapex\b", "资本开支"),
        (r"\bSpend\b", "支出"),
        (r"\bBig Tech\b", "大型科技公司"),
        (r"\bUnsung Heroes\b", "低调赢家"),
        (r"\bCustom\b", "定制"),
        (r"\bBoom\b", "热潮"),
        (r"\bNews\b", "新闻"),
        (r"\band\b", "和"),
        (r"\bthe\b", ""),
        (r"\bfor\b", "面向"),
    ]
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.I)
    result = result.replace("'s", "的").replace("’s", "的")
    result = result.replace("&", "与")
    result = re.sub(r"\s*:\s*", "：", result)
    result = re.sub(r"\s*,\s*", "、", result)
    result = re.sub(r"\s+", " ", result).strip()
    result = result.replace("人工智能 热潮", "人工智能热潮")
    result = result.replace("、和 ", "与")
    result = result.replace("和 '剧烈波动'!", "与剧烈波动：")
    result = result.replace("与'剧烈波动'!", "与剧烈波动：")
    result = result.replace("'剧烈波动的 2025'", "2025年")
    result = result.replace("2025年 美股市场", "2025年美股市场")
    result = result.replace("of U.S. 股票 市场.", "美股市场")
    result = result.replace("of U.S. 股票 市场", "美股市场")
    result = re.sub(r"\s*：\s*", "：", result)
    result = re.sub(r"(\d{4}年)\s+", r"\1", result)
    result = re.sub(r"回顾\s+(\d{4}年)", r"回顾\1", result)
    return result


def strip_english_source_tail(title: str) -> str:
    title = re.split(r"\s+\|\s+", title, maxsplit=1)[0].strip()
    title = re.sub(r"\s+-\s+[^-]{2,60}$", "", title).strip()
    return title


def normalize_article_digest(item: dict) -> dict:
    if any(is_generic_article_text(item.get(key)) for key in ("article_title_zh", "article_summary_zh", "article_body_zh")):
        return article_digest_payload(item.get("title", ""), "")
    text = "。".join(filter(None, [
        item.get("article_title_zh") or item.get("title_zh") or item.get("title", ""),
        item.get("article_summary_zh", ""),
        item.get("article_body_zh", ""),
    ]))
    if text and re.search(r"[\u4e00-\u9fff]", text):
        title = strip_source_suffix(item.get("article_title_zh") or item.get("title_zh") or item.get("title", ""))
        return {
            "title_zh": title,
            "summary_zh": compact_chinese_summary(text),
            "body_zh": item.get("article_body_zh") or chinese_article_body(title, text),
            "key_points_zh": item.get("article_key_points_zh") or chinese_key_points(text),
        }
    title = item.get("title", "")
    return {
        "title_zh": chinese_news_title(title),
        "summary_zh": chinese_article_summary(title, ""),
        "body_zh": chinese_article_body(title, ""),
        "key_points_zh": chinese_key_points(title),
    }


def fetch_article_digest(url: str, fallback_title: str) -> dict:
    if not url:
        return article_digest_payload(fallback_title, "")
    try:
        response = httpx.get(url, timeout=ARTICLE_TIMEOUT, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception:
        return article_digest_payload(fallback_title, "")
    article_url = str(response.url)
    extracted = ArticleTextExtractor()
    extracted.feed(response.text)
    if is_google_news_url(article_url):
        resolved_url = extracted.first_external_link(article_url)
        if resolved_url:
            try:
                response = httpx.get(resolved_url, timeout=ARTICLE_TIMEOUT, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                article_url = str(response.url)
                extracted = ArticleTextExtractor()
                extracted.feed(response.text)
            except Exception:
                article_url = resolved_url
    title = extracted.title or extracted.meta_title or fallback_title
    body = " ".join(extracted.meta_descriptions + extracted.paragraphs[:8])
    return article_digest_payload(title, body, article_url)


def article_digest_payload(title: str, body: str, original_url: str | None = None) -> dict:
    title = clean_text(title)
    body = clean_text(body)
    return {
        "title_zh": chinese_news_title(title),
        "summary_zh": chinese_article_summary(title, body),
        "body_zh": chinese_article_body(title, body),
        "key_points_zh": chinese_key_points(f"{title} {body}"),
        "original_url": original_url,
        "original_title": title,
        "original_body": body,
        "original_saved_at": datetime.now(CN_TZ).isoformat(timespec="seconds") if body else None,
    }


def is_google_news_url(url: str) -> bool:
    return urlparse(url).netloc.endswith("news.google.com")


class ArticleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_title = ""
        self.meta_descriptions: list[str] = []
        self.paragraphs: list[str] = []
        self.links: list[str] = []
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._capture = "title"
            self._buffer = []
        elif tag == "p":
            self._capture = "p"
            self._buffer = []
        elif tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = clean_text(attrs_dict.get("content") or "")
            if not content:
                return
            if name in {"description", "og:description", "twitter:description"}:
                self.meta_descriptions.append(content)
            if name in {"og:title", "twitter:title"}:
                self.meta_title = content
        elif tag == "a":
            href = attrs_dict.get("href") or ""
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "title":
            self.title = clean_text(" ".join(self._buffer))
            self._capture = None
        elif self._capture == "p" and tag == "p":
            paragraph = clean_text(" ".join(self._buffer))
            if len(paragraph) >= 40 and len(self.paragraphs) < 8:
                self.paragraphs.append(paragraph)
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def first_external_link(self, base_url: str) -> str | None:
        for href in self.links:
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc.endswith("google.com") or parsed.netloc.endswith("news.google.com"):
                continue
            return absolute
        return None


def chinese_article_summary(title: str, body: str) -> str:
    text = clean_text(f"{title} {body}")
    if re.search(r"[\u4e00-\u9fff]", text):
        return compact_chinese_summary(text)
    lower = text.lower()
    subjects = []
    for term, label in {
        "nvidia": "英伟达",
        "micron": "美光",
        "tsmc": "台积电",
        "broadcom": "博通",
        "qualcomm": "高通",
        "tesla": "特斯拉",
        "qqq": "纳指100ETF",
        "nasdaq": "纳斯达克",
        "dollar": "美元",
        "gold": "黄金",
    }.items():
        if term in lower:
            subjects.append(label)
    themes = []
    for term, label in {
        "chip": "芯片",
        "semiconductor": "半导体",
        "memory": "内存",
        "hbm": "高带宽内存",
        "dram": "DRAM",
        "ai": "人工智能",
        "robot": "机器人",
        "satellite": "卫星",
        "defense": "国防",
        "yield": "美债收益率",
        "federal reserve": "美联储",
        "earnings": "财报",
    }.items():
        if term in lower:
            themes.append(label)
    action = "偏中性"
    if any(word in lower for word in ("rise", "surge", "gain", "strong", "growth", "beat", "upgrade", "demand")):
        action = "偏正面"
    if any(word in lower for word in ("fall", "drop", "loss", "risk", "concern", "warning", "lawsuit", "probe", "downgrade")):
        action = "偏谨慎"
    theme = "、".join(themes[:4]) or "市场交易线索"
    subject = "、".join(subjects[:3])
    if not subject and themes:
        subject = f"{themes[0]}板块"
    if not subject and "stock" in lower:
        subject = "相关股票"
    subject = subject or "美股相关资产"
    return f"文章总结：内容围绕{subject}展开，核心关注{theme}；从标题和页面摘要看，消息倾向{action}。"


def chinese_article_body(title: str, body: str) -> str:
    text = clean_text(f"{title} {body}")
    if not text:
        return "中文编译：链接页暂未提取到可用正文。"
    if title and not clean_text(body):
        return f"中文编译：{chinese_news_title(title)}。"
    if re.search(r"[\u4e00-\u9fff]", text):
        sentences = chinese_sentences(text, limit=8)
        return "中文编译：" + "。".join(sentences) + ("。" if sentences else "")
    sentences = english_sentences(text, limit=8)
    translated = [translate_sentence(sentence) for sentence in sentences]
    translated = [sentence for sentence in translated if sentence]
    if not translated:
        return chinese_article_summary(title, body).replace("链接页摘要：", "中文编译：").replace("文章总结：", "中文编译：")
    return "中文编译：" + "。".join(translated) + "。"


def chinese_key_points(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return ["链接页暂未提取到可用正文。"]
    sentences = chinese_sentences(text, limit=4) if re.search(r"[\u4e00-\u9fff]", text) else [translate_sentence(sentence) for sentence in english_sentences(text, limit=4)]
    points = [sentence.rstrip("。") for sentence in sentences if sentence]
    return points or [chinese_article_summary(text, "").replace("链接页摘要：", "").replace("文章总结：", "")]


def chinese_sentences(text: str, limit: int) -> list[str]:
    sentences = [clean_text(part) for part in re.split(r"[。！？!?]\s*", text) if clean_text(part)]
    return sentences[:limit]


def english_sentences(text: str, limit: int) -> list[str]:
    sentences = [clean_text(part) for part in re.split(r"(?<=[.!?])\s+", text) if clean_text(part)]
    return sentences[:limit]


def translate_sentence(sentence: str) -> str:
    sentence = strip_english_source_tail(clean_text(sentence))
    translated = literal_chinese_title(sentence) or translate_title_fragment(sentence)
    translated = translated.strip(" .")
    if translated == sentence:
        return ""
    return translated


def compact_chinese_summary(text: str) -> str:
    sentences = [clean_text(part) for part in re.split(r"[。！？!?]\s*", text) if clean_text(part)]
    summary = "；".join(sentences[:3])
    if len(summary) > 180:
        summary = summary[:180].rstrip("，；、 ") + "..."
    return f"文章总结：{summary}" if summary else "文章总结：已抓取链接页，但暂无可用正文摘要。"


def strip_source_suffix(title: str) -> str:
    return re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip()


def chinese_source_name(source: str) -> str:
    mapping = {
        "Google News": "谷歌新闻",
        "Yahoo Finance": "雅虎财经",
        "Reuters": "路透社",
        "Bloomberg": "彭博社",
        "MarketWatch": "市场观察",
        "CNBC": "CNBC财经",
        "Investopedia": "Investopedia财经",
        "Seeking Alpha": "Seeking Alpha财经",
        "The Motley Fool": "Motley Fool财经",
        "U.S. News - Money": "美国新闻财经",
    }
    return mapping.get(source, source if re.search(r"[\u4e00-\u9fff]", source) else "海外媒体")


def infer_source(title: str) -> str | None:
    if " - " not in title:
        return None
    return title.rsplit(" - ", 1)[-1].strip()


def parse_float(value: str | None) -> float | None:
    if value in (None, "", "N/D"):
        return None
    try:
        return float(value)
    except ValueError:
        return None
