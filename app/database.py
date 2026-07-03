import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from app.ah_premium import load_ah_premium_records
from app.config import DATA_DIR, DB_PATH
from app.sample_data import SAMPLE_IPOS
from app.scoring import normalize_metrics, score_ipo
from app.subscription import load_subscription_records


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS ipos (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, english_name TEXT NOT NULL, code TEXT UNIQUE NOT NULL,
          industry TEXT NOT NULL, price_low REAL NOT NULL, price_high REAL NOT NULL, deadline TEXT NOT NULL,
          metrics_json TEXT NOT NULL, risks_json TEXT NOT NULL, dimensions_json TEXT NOT NULL,
          original_score REAL NOT NULL, is_sample INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS adjustments (
          id INTEGER PRIMARY KEY, ipo_id INTEGER NOT NULL REFERENCES ipos(id), value REAL NOT NULL,
          reason TEXT NOT NULL, operator TEXT NOT NULL, created_at TEXT NOT NULL, original_score REAL NOT NULL,
          final_score REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reports (
          id INTEGER PRIMARY KEY, report_date TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL,
          markdown TEXT NOT NULL, item_count INTEGER NOT NULL, buy_count INTEGER NOT NULL,
          hold_count INTEGER NOT NULL, avoid_count INTEGER NOT NULL,
          UNIQUE(report_date, version)
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM ipos").fetchone()[0]
        if count == 0:
            for item in SAMPLE_IPOS:
                metrics = normalize_metrics(item["metrics"])
                dimensions, score = score_ipo(metrics)
                db.execute("""INSERT INTO ipos
                    (name, english_name, code, industry, price_low, price_high, deadline, metrics_json,
                     risks_json, dimensions_json, original_score, is_sample)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item["name"], item["english_name"], item["code"], item["industry"], item["price_low"],
                     item["price_high"], item["deadline"], json.dumps(metrics, ensure_ascii=False),
                     json.dumps(item["risks"], ensure_ascii=False),
                     json.dumps([d.model_dump() for d in dimensions], ensure_ascii=False), score,
                     int(item.get("is_sample", False))))
        else:
            rows = db.execute("SELECT id, code, is_sample, metrics_json FROM ipos").fetchall()
            sample_items = {item["code"]: item for item in SAMPLE_IPOS}
            for row in rows:
                metrics = json.loads(row["metrics_json"])
                sample_item = sample_items.get(row["code"])
                if sample_item:
                    metrics.update(sample_item["metrics"])
                metrics = normalize_metrics(metrics)
                dimensions, score = score_ipo(metrics)
                if sample_item:
                    db.execute("""UPDATE ipos SET
                        name=?, english_name=?, industry=?, price_low=?, price_high=?, deadline=?,
                        metrics_json=?, risks_json=?, dimensions_json=?, original_score=?, is_sample=?
                        WHERE id=?""",
                        (sample_item["name"], sample_item["english_name"], sample_item["industry"],
                         sample_item["price_low"], sample_item["price_high"], sample_item["deadline"],
                         json.dumps(metrics, ensure_ascii=False),
                         json.dumps(sample_item["risks"], ensure_ascii=False),
                         json.dumps([d.model_dump() for d in dimensions], ensure_ascii=False),
                         score, int(sample_item.get("is_sample", False)), row["id"]))
                else:
                    db.execute("UPDATE ipos SET metrics_json=?, dimensions_json=?, original_score=? WHERE id=?",
                               (json.dumps(metrics, ensure_ascii=False),
                                json.dumps([d.model_dump() for d in dimensions], ensure_ascii=False),
                                score, row["id"]))


def latest_adjustment(db: sqlite3.Connection, ipo_id: int):
    return db.execute("SELECT * FROM adjustments WHERE ipo_id=? ORDER BY id DESC LIMIT 1", (ipo_id,)).fetchone()


def apply_ah_premiums(record_date) -> None:
    records = {record.hk_code: record for record in load_ah_premium_records(record_date)
               if record.ah_premium is not None}
    if not records:
        return
    with connect() as db:
        rows = db.execute("SELECT id, code, metrics_json FROM ipos").fetchall()
        for row in rows:
            record = records.get(row["code"])
            if record is None:
                continue
            metrics = json.loads(row["metrics_json"])
            metrics["is_ah"] = True
            metrics["ah_premium"] = record.ah_premium
            metrics["ah_premium_source"] = record.source
            metrics["ah_premium_record_date"] = record.record_date.isoformat()
            metrics["a_ticker"] = record.a_ticker
            metrics["a_close_cny"] = record.a_close_cny
            metrics["cny_hkd"] = record.cny_hkd
            metrics = normalize_metrics(metrics)
            dimensions, score = score_ipo(metrics)
            db.execute("UPDATE ipos SET metrics_json=?, dimensions_json=?, original_score=? WHERE id=?",
                       (json.dumps(metrics, ensure_ascii=False),
                        json.dumps([item.model_dump() for item in dimensions], ensure_ascii=False),
                        score, row["id"]))


def apply_subscription_multiples(record_date) -> None:
    records = {record.normalized_code: record for record in load_subscription_records(record_date)}
    with connect() as db:
        rows = db.execute("SELECT id, code, metrics_json FROM ipos").fetchall()
        for row in rows:
            record = records.get(row["code"])
            if record is None or record.subscription_multiple is None:
                continue
            metrics = json.loads(row["metrics_json"])
            metrics["subscription_multiple"] = record.subscription_multiple
            metrics["subscription_source"] = record.data_source
            metrics["subscription_record_date"] = record.record_date.isoformat()
            metrics["subscription_captured_at"] = record.captured_at
            metrics = normalize_metrics(metrics)
            dimensions, score = score_ipo(metrics)
            db.execute("UPDATE ipos SET metrics_json=?, dimensions_json=?, original_score=? WHERE id=?",
                       (json.dumps(metrics, ensure_ascii=False),
                        json.dumps([item.model_dump() for item in dimensions], ensure_ascii=False),
                        score, row["id"]))
