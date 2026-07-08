import json
from datetime import date, datetime
from app.database import connect, latest_adjustment
from app.grey_market import GreyMarketQuote as GreyMarketQuoteValue
from app.grey_market import fetch_grey_market_quote, quote_to_metrics
from app.scoring import recommendation


def _base(row, adjustment=None) -> dict:
    value = float(adjustment["value"]) if adjustment else 0.0
    final = round(float(row["original_score"]) + value, 1)
    metrics = json.loads(row["metrics_json"])
    return {"id": row["id"], "name": row["name"], "english_name": row["english_name"], "code": row["code"],
            "industry": row["industry"], "price_low": row["price_low"], "price_high": row["price_high"],
            "minimum_subscription_amount": metrics.get("minimum_subscription_amount"),
            "subscription_multiple": metrics.get("subscription_multiple"),
            "deadline": row["deadline"], "is_sample": bool(row["is_sample"]),
            "original_score": row["original_score"], "adjustment": value, "final_score": final,
            "recommendation": recommendation(final)}


def _report_insights(items: list[dict]) -> dict:
    names = {item["name"] for item in items}
    ranking_groups = [
        ["东方科脉"],
        ["三环集团", "普源精电", "鼎泰高科"],
        ["立讯精密", "滨化股份", "易控智驾"],
        ["同仁堂医养", "MOMENTA-W", "基本半导体", "瑞为技术"],
    ]
    ranking = [[name for name in group if name in names] for group in ranking_groups]
    ranking = [group for group in ranking if group]

    bands = [
        ("极难", 100, float("inf"), "百倍以上认购，预计中签率最低"),
        ("较难", 50, 100, "50至100倍认购"),
        ("中等", 10, 50, "10至50倍认购"),
        ("较易", 0, 10, "低于10倍认购；仍不代表一定获配"),
    ]
    difficulty = []
    for label, minimum, maximum, note in bands:
        companies = [item["name"] for item in items
                     if item.get("subscription_multiple") is not None
                     and minimum <= item["subscription_multiple"] < maximum]
        if companies:
            difficulty.append({"label": label, "companies": companies, "note": note})
    return {"fundamental_valuation_ranking": ranking, "allotment_difficulty": difficulty}


def list_ipos(industry=None, recommendation_filter=None, deadline=None, sort="final_score", order="desc", page=1, page_size=20,
              active_codes: set[str] | None = None):
    with connect() as db:
        rows = db.execute("SELECT * FROM ipos").fetchall()
        items = [_base(row, latest_adjustment(db, row["id"])) for row in rows]
    insights = _report_insights(items)
    if active_codes is not None:
        items = [item for item in items if item["code"] in active_codes]
    if industry:
        items = [item for item in items if item["industry"] == industry]
    if recommendation_filter:
        items = [item for item in items if item["recommendation"] == recommendation_filter]
    if deadline:
        items = [item for item in items if item["deadline"] == deadline]
    safe_sort = sort if sort in {"name", "code", "deadline", "original_score", "final_score"} else "final_score"
    items.sort(key=lambda item: item[safe_sort], reverse=order == "desc")
    total = len(items)
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size,
            "insights": insights}


def get_ipo(ipo_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM ipos WHERE id=?", (ipo_id,)).fetchone()
        if not row:
            return None
        latest = latest_adjustment(db, ipo_id)
        result = _base(row, latest)
        metrics = json.loads(row["metrics_json"])
        history = db.execute("SELECT * FROM adjustments WHERE ipo_id=? ORDER BY id DESC", (ipo_id,)).fetchall()
        result.update({"dimensions": json.loads(row["dimensions_json"]), "risks": json.loads(row["risks_json"]),
                       "metrics": metrics, "adjustments": [dict(item) for item in history],
                       "issuance_shares": metrics.get("issuance_shares"), "lot_size": metrics.get("lot_size"),
                       "greenshoe": metrics.get("greenshoe"),
                       "cornerstone_investors": metrics.get("cornerstone_investors", []),
                       "cornerstone_ratio": metrics.get("cornerstone_ratio"),
                       "sponsors": metrics.get("sponsors", []), "company_quality": metrics.get("company_quality", [])})
        return result


def add_adjustment(ipo_id: int, value: float, reason: str, operator: str):
    with connect() as db:
        row = db.execute("SELECT * FROM ipos WHERE id=?", (ipo_id,)).fetchone()
        if not row:
            return None
        final = round(float(row["original_score"]) + value, 1)
        cursor = db.execute("""INSERT INTO adjustments
            (ipo_id, value, reason, operator, created_at, original_score, final_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ipo_id, value, reason, operator, datetime.now().isoformat(timespec="seconds"), row["original_score"], final))
        adjustment_id = cursor.lastrowid
    return next(item for item in get_ipo(ipo_id)["adjustments"] if item["id"] == adjustment_id)


def fetch_and_save_grey_market_price(ipo_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM ipos WHERE id=?", (ipo_id,)).fetchone()
        if not row:
            return None
        quote = fetch_grey_market_quote(row["code"])
        metrics = quote_to_metrics(row["metrics_json"], quote, float(row["price_high"]))
        final_offer_price = final_offer_price_from_quote(quote)
        if final_offer_price is None:
            db.execute("UPDATE ipos SET metrics_json=? WHERE id=?", (json.dumps(metrics, ensure_ascii=False), ipo_id))
        else:
            db.execute(
                "UPDATE ipos SET price_low=?, price_high=?, metrics_json=? WHERE id=?",
                (final_offer_price, final_offer_price, json.dumps(metrics, ensure_ascii=False), ipo_id),
            )
    return {
        "ipo_id": ipo_id,
        "code": row["code"],
        "price": quote.price,
        "change_pct": metrics.get("grey_market_change_pct"),
        "reference_price": metrics.get("grey_market_reference_price"),
        "reference_label": metrics.get("grey_market_reference_label"),
        "fetched_at": quote.fetched_at,
        "source": quote.source,
    }


def refresh_grey_market_prices(target_date: date) -> dict:
    refreshed = []
    skipped = []
    failed = []
    with connect() as db:
        rows = db.execute("SELECT * FROM ipos WHERE deadline <= ? ORDER BY deadline, code", (target_date.isoformat(),)).fetchall()
        for row in rows:
            metrics = json.loads(row["metrics_json"])
            if metrics.get("grey_market_finalized") is True:
                skipped.append(row["code"])
                continue
            try:
                quote = fetch_grey_market_quote(row["code"])
            except ValueError as exc:
                failed.append({"code": row["code"], "reason": str(exc)})
                continue
            if metrics.get("grey_market_source") == "手动输入" and metrics.get("grey_market_price") is not None:
                quote = GreyMarketQuoteValue(
                    price=float(metrics["grey_market_price"]),
                    fetched_at=quote.fetched_at,
                    source="手动输入",
                    offer_price=quote.offer_price,
                    reference_label=quote.reference_label,
                )
            metrics = quote_to_metrics(row["metrics_json"], quote, float(row["price_high"]))
            final_offer_price = final_offer_price_from_quote(quote)
            if final_offer_price is None:
                db.execute("UPDATE ipos SET metrics_json=? WHERE id=?", (json.dumps(metrics, ensure_ascii=False), row["id"]))
            else:
                db.execute(
                    "UPDATE ipos SET price_low=?, price_high=?, metrics_json=? WHERE id=?",
                    (final_offer_price, final_offer_price, json.dumps(metrics, ensure_ascii=False), row["id"]),
                )
            refreshed.append({
                "code": row["code"],
                "price": quote.price,
                "reference_price": metrics.get("grey_market_reference_price"),
                "reference_label": metrics.get("grey_market_reference_label"),
                "change_pct": metrics.get("grey_market_change_pct"),
            })
    return {"refreshed": refreshed, "skipped": skipped, "failed": failed}


def save_manual_grey_market_price(ipo_id: int, price: float, finalized: bool = False):
    with connect() as db:
        row = db.execute("SELECT * FROM ipos WHERE id=?", (ipo_id,)).fetchone()
        if not row:
            return None
        offer_price = None
        reference_label = None
        try:
            fetched_quote = fetch_grey_market_quote(row["code"])
            offer_price = fetched_quote.offer_price
            reference_label = fetched_quote.reference_label
        except ValueError:
            pass
        quote = GreyMarketQuoteValue(
            price=price,
            fetched_at=datetime.now(),
            source="手动输入",
            offer_price=offer_price,
            reference_label=reference_label,
        )
        metrics = quote_to_metrics(row["metrics_json"], quote, float(row["price_high"]), finalized=finalized)
        final_offer_price = final_offer_price_from_quote(quote)
        if final_offer_price is None:
            db.execute("UPDATE ipos SET metrics_json=? WHERE id=?", (json.dumps(metrics, ensure_ascii=False), ipo_id))
        else:
            db.execute(
                "UPDATE ipos SET price_low=?, price_high=?, metrics_json=? WHERE id=?",
                (final_offer_price, final_offer_price, json.dumps(metrics, ensure_ascii=False), ipo_id),
            )
    return {
        "ipo_id": ipo_id,
        "code": row["code"],
        "price": quote.price,
        "change_pct": metrics.get("grey_market_change_pct"),
        "reference_price": metrics.get("grey_market_reference_price"),
        "reference_label": metrics.get("grey_market_reference_label"),
        "fetched_at": quote.fetched_at,
        "source": quote.source,
    }


def finalize_grey_market_price(ipo_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM ipos WHERE id=?", (ipo_id,)).fetchone()
        if not row:
            return None
        metrics = json.loads(row["metrics_json"])
        if metrics.get("grey_market_price") is None:
            raise ValueError("请先录入暗盘价格")
        metrics["grey_market_finalized"] = True
        db.execute("UPDATE ipos SET metrics_json=? WHERE id=?", (json.dumps(metrics, ensure_ascii=False), ipo_id))
    return get_ipo(ipo_id)


def final_offer_price_from_quote(quote: GreyMarketQuoteValue) -> float | None:
    if quote.reference_label != "昨日收盘价":
        return None
    if quote.offer_price is None or quote.offer_price <= 0:
        return None
    return quote.offer_price
