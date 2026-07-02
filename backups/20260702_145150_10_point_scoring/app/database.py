import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from app.config import DATA_DIR, DB_PATH
from app.sample_data import SAMPLE_IPOS
from app.scoring import score_ipo


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
                dimensions, score = score_ipo(item["metrics"])
                db.execute("""INSERT INTO ipos
                    (name, english_name, code, industry, price_low, price_high, deadline, metrics_json,
                     risks_json, dimensions_json, original_score, is_sample)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (item["name"], item["english_name"], item["code"], item["industry"], item["price_low"],
                     item["price_high"], item["deadline"], json.dumps(item["metrics"], ensure_ascii=False),
                     json.dumps(item["risks"], ensure_ascii=False),
                     json.dumps([d.model_dump() for d in dimensions], ensure_ascii=False), score))


def latest_adjustment(db: sqlite3.Connection, ipo_id: int):
    return db.execute("SELECT * FROM adjustments WHERE ipo_id=? ORDER BY id DESC LIMIT 1", (ipo_id,)).fetchone()

