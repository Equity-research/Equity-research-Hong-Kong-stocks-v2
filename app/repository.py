import json
from datetime import date, datetime
from app.database import connect, latest_adjustment
from app.scoring import recommendation


def _base(row, adjustment=None) -> dict:
    value = float(adjustment["value"]) if adjustment else 0.0
    final = round(float(row["original_score"]) + value, 1)
    return {"id": row["id"], "name": row["name"], "english_name": row["english_name"], "code": row["code"],
            "industry": row["industry"], "price_low": row["price_low"], "price_high": row["price_high"],
            "deadline": row["deadline"], "is_sample": bool(row["is_sample"]),
            "original_score": row["original_score"], "adjustment": value, "final_score": final,
            "recommendation": recommendation(final)}


def list_ipos(industry=None, recommendation_filter=None, deadline=None, sort="final_score", order="desc", page=1, page_size=20):
    with connect() as db:
        rows = db.execute("SELECT * FROM ipos").fetchall()
        items = [_base(row, latest_adjustment(db, row["id"])) for row in rows]
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
    return {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size}


def get_ipo(ipo_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM ipos WHERE id=?", (ipo_id,)).fetchone()
        if not row:
            return None
        latest = latest_adjustment(db, ipo_id)
        result = _base(row, latest)
        history = db.execute("SELECT * FROM adjustments WHERE ipo_id=? ORDER BY id DESC", (ipo_id,)).fetchall()
        result.update({"dimensions": json.loads(row["dimensions_json"]), "risks": json.loads(row["risks_json"]),
                       "metrics": json.loads(row["metrics_json"]), "adjustments": [dict(item) for item in history]})
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

