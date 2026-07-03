import argparse
import csv
import html
import json
import re
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.ah_premium import (
    AHPremiumRecord,
    fetch_ah_premium_records,
    latest_ah_premium_before,
    write_ah_premium_records,
)
from app.config import DATA_DIR, ROOT
from app.daily_ipo import active_subscription_codes, daily_ipo_path
from app.database import apply_ah_premiums, apply_daily_ipo_records, apply_subscription_multiples, initialize
from app.prospectus import prune_prospectus_dirs, sync_prospectuses_for_date
from app.reporting import create_report, report_pdf
from app.repository import get_ipo, list_ipos
from app.subscription import (
    SubscriptionRecord,
    fetch_hkipox_today_rows,
    latest_subscription_before,
    load_subscription_records,
    write_daily_ipo_from_hkipox,
    write_subscription_csv,
    write_subscription_records,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh daily IPO data and generate Markdown/PDF/HTML reports.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Report date, YYYY-MM-DD.")
    parser.add_argument(
        "--wait",
        type=float,
        default=2.0,
        help="Seconds to wait between dependent data steps. Use 0 to run without pauses.",
    )
    args = parser.parse_args()
    report_date = date.fromisoformat(args.date)

    progress = Progress(total=11, wait_seconds=max(args.wait, 0))
    progress.info(f"开始跑全量数据，日期={report_date.isoformat()}")

    with progress.step("抓取 HKIPOx 今日申购表，生成 IPO 清单和申购倍数"):
        source_path, subscription_source_path = refresh_daily_inputs(report_date)

    with progress.step("同步当日招股书 PDF"):
        prospectus_result = sync_prospectuses_for_date(report_date)
        deleted_prospectus_dirs = prune_prospectus_dirs(report_date)

    with progress.step("初始化 SQLite 数据库和基础评分数据"):
        initialize()

    with progress.step("同步当日 IPO 截止日到数据库"):
        apply_daily_ipo_records(report_date)

    with progress.step("写入申购倍数到数据库"):
        apply_subscription_multiples(report_date)

    with progress.step("校验申购倍数字段完整性"):
        validate_subscription_fields(report_date)

    with progress.step("校验发行结构字段完整性"):
        validate_issuance_fields()

    with progress.step("抓取或回退 A/H 溢价数据"):
        ah_path = ensure_ah_premium_file(report_date)

    with progress.step("写入 A/H 溢价到数据库"):
        apply_ah_premiums(report_date)

    with progress.step("生成日报 Markdown/PDF 数据"):
        report = create_report(report_date)

    with progress.step("生成前端 HTML 报告"):
        active_codes = active_subscription_codes(report_date)
        items = list_ipos(page_size=100, active_codes=active_codes)["items"]
        details = [get_ipo(item["id"]) for item in items]

    stem = ROOT / "ipo_daily_analysis"
    md_path = stem.with_suffix(".md")
    pdf_path = stem.with_suffix(".pdf")
    html_path = stem.with_suffix(".html")

    md_path.write_text(report["markdown"], encoding="utf-8")
    pdf_path.write_bytes(report_pdf(report))
    html_path.write_text(render_html(report_date, report, details, source_path), encoding="utf-8")

    print(f"daily_ipo={source_path}")
    print(f"subscription={subscription_source_path}")
    print(
        "prospectuses="
        f"{prospectus_result.directory} "
        f"kept={len(prospectus_result.kept)} "
        f"reused={len(prospectus_result.reused)} "
        f"downloaded={len(prospectus_result.downloaded)} "
        f"deleted={len(prospectus_result.deleted)} "
        f"deleted_old_dirs={len(deleted_prospectus_dirs)}"
    )
    print(f"ah_premium={ah_path}")
    print(f"markdown={md_path}")
    print(f"pdf={pdf_path}")
    print(f"html={html_path}")
    print(f"report_id={report['id']} items={report['item_count']}")
    progress.done()


class Progress:
    def __init__(self, total: int, wait_seconds: float) -> None:
        self.total = total
        self.wait_seconds = wait_seconds
        self.current = 0
        self.started_at = time.monotonic()

    def info(self, message: str) -> None:
        print(f"[{self._clock()}] {message}", flush=True)

    @contextmanager
    def step(self, title: str):
        self.current += 1
        step_started_at = time.monotonic()
        print(f"[{self._clock()}] [{self.current}/{self.total}] 开始：{title}", flush=True)
        try:
            yield
        except Exception:
            elapsed = time.monotonic() - step_started_at
            print(f"[{self._clock()}] [{self.current}/{self.total}] 失败：{title}（耗时 {elapsed:.1f}s）", flush=True)
            raise
        elapsed = time.monotonic() - step_started_at
        print(f"[{self._clock()}] [{self.current}/{self.total}] 完成：{title}（耗时 {elapsed:.1f}s）", flush=True)
        if self.current < self.total and self.wait_seconds > 0:
            print(f"[{self._clock()}] 等待 {self.wait_seconds:g}s 后继续下一个依赖步骤...", flush=True)
            time.sleep(self.wait_seconds)

    def done(self) -> None:
        elapsed = time.monotonic() - self.started_at
        print(f"[{self._clock()}] 全部数据流程完成，总耗时 {elapsed:.1f}s", flush=True)

    @staticmethod
    def _clock() -> str:
        return datetime.now().strftime("%H:%M:%S")


def refresh_daily_inputs(report_date: date) -> tuple[Path, Path]:
    try:
        rows = fetch_hkipox_today_rows()
    except Exception as exc:
        latest = latest_subscription_before(report_date)
        if latest is None:
            raise RuntimeError(f"未能全量抓取 HKIPOx 今日申购表，且不存在历史申购倍数快照：{exc}") from exc
        daily_path = ensure_daily_ipo_file(report_date)
        subscription_records = fallback_subscription_records(report_date, latest)
        subscription_file = write_subscription_csv(report_date, subscription_records)
        return daily_path, subscription_file

    if not rows:
        raise RuntimeError("HKIPOx 今日申购表为空，已停止生成日报，避免写入不完整股票池。")

    daily_path = write_daily_ipo_from_hkipox(report_date, rows)
    subscription_file = write_subscription_records(report_date, rows)
    return daily_path, subscription_file


def ensure_daily_ipo_file(report_date: date) -> Path:
    path = daily_ipo_path(report_date)
    if path.exists():
        normalize_daily_ipo_file(path, report_date)
        return path

    latest = latest_daily_ipo_before(report_date)
    if latest is None:
        raise FileNotFoundError(f"No prior daily IPO CSV found under {DATA_DIR}")

    with latest.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []

    refreshed = []
    for row in rows:
        subscription_end = date.fromisoformat(row["subscription_end_date"])
        expected_listing = parse_optional_date(row.get("expected_listing_date"))
        if subscription_end <= report_date:
            continue
        if expected_listing is not None and expected_listing <= report_date:
            continue
        next_row = dict(row)
        next_row["record_date"] = report_date.isoformat()
        next_row["status"] = "认购中"
        refreshed.append(next_row)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(refreshed)
    return path


def fallback_subscription_records(report_date: date, latest: Path) -> list[SubscriptionRecord]:
    records = []
    with latest.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append(SubscriptionRecord(
                record_date=report_date,
                captured_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
                stock_code=row["stock_code"],
                company_name=row["company_name"],
                subscription_multiple=parse_optional_float(row.get("subscription_multiple")),
                status=f"fallback from {latest.name}",
                subscription_end_date=date.fromisoformat(row["subscription_end_date"]),
                data_type=row.get("data_type", "招股期实时推算值"),
                data_source=f"fallback from {latest.name}",
                source_url=row.get("source_url", ""),
            ))
    return records


def ensure_ah_premium_file(report_date: date) -> Path:
    offer_prices = ah_offer_prices()
    records = fetch_ah_premium_records(report_date, offer_prices)
    if records and all(record.ah_premium is not None for record in records):
        return write_ah_premium_records(report_date, records)

    latest = latest_ah_premium_before(report_date)
    if latest is not None:
        fallback_records = []
        with latest.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                fallback_records.append(AHPremiumRecord(
                    record_date=report_date,
                    hk_code=row["hk_code"],
                    company_name=row["company_name"],
                    a_ticker=row["a_ticker"],
                    h_offer_price_hkd=float(row["h_offer_price_hkd"]),
                    a_close_cny=parse_optional_float(row.get("a_close_cny")),
                    cny_hkd=parse_optional_float(row.get("cny_hkd")),
                    ah_premium=parse_optional_float(row.get("ah_premium")),
                    source=f"fallback from {latest.name}",
                    notes="当日行情抓取失败，沿用最近一次A/H溢价；需人工复核",
                ))
        return write_ah_premium_records(report_date, fallback_records)

    raise RuntimeError("未能抓取完整 A/H 溢价数据，且不存在可回退的历史 ah_premium_YYYY-MM-DD.csv")


def ah_offer_prices() -> dict[str, float]:
    from app.sample_data import SAMPLE_IPOS

    return {
        item["code"]: float(item["price_high"])
        for item in SAMPLE_IPOS
        if item["metrics"].get("is_ah")
    }


def normalize_daily_ipo_file(path: Path, report_date: date) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []

    active_rows = []
    for row in rows:
        subscription_end = date.fromisoformat(row["subscription_end_date"])
        expected_listing = parse_optional_date(row.get("expected_listing_date"))
        if subscription_end <= report_date:
            continue
        if expected_listing is not None and expected_listing <= report_date:
            continue
        next_row = dict(row)
        next_row["record_date"] = report_date.isoformat()
        next_row["status"] = "认购中"
        active_rows.append(next_row)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(active_rows)


def latest_daily_ipo_before(report_date: date) -> Path | None:
    candidates = []
    for path in DATA_DIR.glob("daily_ipo_*.csv"):
        match = re.fullmatch(r"daily_ipo_(\d{4}-\d{2}-\d{2})\.csv", path.name)
        if not match:
            continue
        candidate_date = date.fromisoformat(match.group(1))
        if candidate_date < report_date:
            candidates.append((candidate_date, path))
    return max(candidates, default=(None, None))[1]


def parse_optional_date(value: str | None) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None


def parse_optional_float(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def validate_issuance_fields() -> None:
    from app.database import connect

    errors = []
    with connect() as db:
        rows = db.execute("SELECT code, name, metrics_json FROM ipos ORDER BY code").fetchall()
    for row in rows:
        metrics = json.loads(row["metrics_json"])
        prefix = f"{row['code']} {row['name']}"
        if metrics.get("has_cornerstone") is None:
            errors.append(f"{prefix}: has_cornerstone 未补全")
        if metrics.get("greenshoe") is None:
            errors.append(f"{prefix}: greenshoe 未补全")
        if metrics.get("has_cornerstone") is True:
            if not metrics.get("cornerstone_investors"):
                errors.append(f"{prefix}: 有基石但缺少 cornerstone_investors")
            if metrics.get("cornerstone_ratio") is None:
                errors.append(f"{prefix}: 有基石但缺少 cornerstone_ratio")
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise RuntimeError(f"发行结构字段未跑全，已停止生成日报：\n{joined}")


def validate_subscription_fields(report_date: date) -> None:
    active_codes = active_subscription_codes(report_date)
    records = {record.normalized_code: record for record in load_subscription_records(report_date)}
    missing = [
        code for code in sorted(active_codes)
        if code not in records or records[code].subscription_multiple is None
    ]
    if missing:
        joined = "\n".join(f"- {code}" for code in missing)
        raise RuntimeError(f"申购倍数字段未跑全，已停止生成日报：\n{joined}")


def render_html(report_date: date, report: dict, details: list[dict], source_path: Path) -> str:
    generated_at = datetime.now().strftime("%H:%M CST")
    data = [html_item(detail) for detail in details if detail]
    counts = {
        "申购": sum(item["tier"] == "申购" for item in data),
        "观望": sum(item["tier"] == "观望" for item in data),
        "回避": sum(item["tier"] == "回避" for item in data),
    }
    average = sum(item["total"] for item in data) / len(data) if data else 0
    funds = allocation_plan(data)
    fund_text = " · ".join(f"{item['name']}{item['allocation'] // 1000}k" for item in funds) or "暂无建议资金分配"
    fund_bars = "".join(f"<i style=\"width:{item['allocation'] / 500:.2f}%\"></i>" for item in funds)
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return render_home_html(report_date, generated_at, source_path, data, counts, average, data_json)


def render_home_html(report_date: date, generated_at: str, source_path: Path, data: list[dict],
                     counts: dict[str, int], average: float, data_json: str) -> str:
    display_data = [item for item in data if item["tier"] != "回避"]
    display_data_json = json.dumps(display_data, ensure_ascii=False, separators=(",", ":"))
    ranking = " > ".join(item["name"] for item in sorted(display_data, key=lambda item: (item["total"], item["sub"] or 0), reverse=True)[:10])
    difficulty = allotment_difficulty(display_data)
    difficulty_html = "".join(
        f"<div><dt>{html.escape(group['label'])}</dt><dd>{html.escape(' + '.join(group['companies']))}<small>{html.escape(group['note'])}</small></dd></div>"
        for group in difficulty
    )
    funding_conflict_html = funding_conflict(data)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>港股 IPO 分析｜{report_date.isoformat()}</title><style>
:root{{font-family:"PingFang SC","Microsoft YaHei",Inter,system-ui,sans-serif;color:#0b1739;background:#f4f6f9;--navy:#0b1739;--red:#e10d15;--border:#dce2eb;--muted:#586380;--green:#0b9f61;--amber:#e58200}}*{{box-sizing:border-box}}body{{margin:0;min-width:320px;background:#f4f6f9}}button,select{{font:inherit}}button{{cursor:pointer}}.topbar{{height:58px;background:#fff;border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 18px;gap:14px;position:sticky;top:0;z-index:20}}.brand{{font-size:19px;font-weight:800;color:var(--navy)}}.menu{{margin-left:auto;border:0;background:none;color:#17233d;font-size:25px;line-height:1}}.page{{max-width:1180px;margin:0 auto;padding:24px 18px 48px}}.page-title{{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:22px}}.page-title h1{{font-family:Georgia,"Songti SC",serif;font-size:31px;margin:0 0 7px;color:var(--navy)}}.page-title p{{margin:0;color:#697590;font-size:13px;font-weight:650}}.primary{{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:0;border-radius:7px;background:var(--red);color:#fff;font-weight:800;padding:12px 18px;text-decoration:none;box-shadow:0 5px 14px rgba(225,13,21,.18);white-space:nowrap}}.summary{{background:#fff;border:1px solid var(--border);border-radius:10px;margin-bottom:14px;overflow:hidden}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);padding:14px 8px 0}}.stat{{text-align:center;padding:0 8px 15px;border-right:1px solid var(--border)}}.stat:last-child{{border-right:0}}.stat span{{display:block;color:var(--muted);font-size:13px;font-weight:700;margin-bottom:8px}}.stat strong{{font-size:26px;line-height:1}}.green{{color:var(--green)}}.amber{{color:var(--amber)}}.red{{color:var(--red)}}.insights{{border-top:1px solid var(--border);padding:16px 18px 19px}}.insights section+section{{border-top:1px solid var(--border);margin-top:16px;padding-top:16px}}.insights h3{{font-size:14px;margin:0 0 11px;color:#15203a}}.ranking{{margin:0;color:#34405a;font-size:13px;line-height:1.8;font-weight:650}}.difficulty{{display:grid;gap:10px;margin:0}}.difficulty div{{display:grid;grid-template-columns:58px 1fr;gap:9px;color:#34405a;font-size:13px;line-height:1.65}}.difficulty dt{{color:var(--muted);font-weight:700}}.difficulty dt:after{{content:"："}}.difficulty dd{{margin:0;font-weight:650}}.difficulty small{{display:block;color:var(--muted);font-weight:500}}.funding-conflict{{background:#fff;border:1px solid var(--border);border-radius:9px;margin:0 0 18px;padding:14px 16px;display:grid;gap:12px}}.funding-conflict h3{{font-size:14px;margin:0;color:#15203a}}.funding-conflict-summary{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;color:#34405a;font-size:13px;font-weight:650}}.funding-conflict-summary strong{{font-size:18px;color:var(--red)}}.funding-conflict dl{{display:grid;gap:8px;margin:0}}.funding-conflict dl div{{display:grid;grid-template-columns:82px 1fr;gap:10px;color:#34405a;font-size:13px;line-height:1.55}}.funding-conflict dt{{color:var(--muted);font-weight:800}}.funding-conflict dd{{margin:0;font-weight:650}}.funding-conflict small{{display:block;color:var(--muted);font-weight:500}}.filters{{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px;margin-bottom:18px}}.filters label{{display:block;color:#4c5770;font-size:13px;font-weight:650}}.filters select{{display:block;width:100%;margin-top:7px;background:#fff;border:1px solid var(--border);border-radius:7px;padding:11px 38px 11px 12px;color:var(--navy)}}.reset{{grid-column:1/-1;height:46px;border:1px solid var(--border);background:#fff;border-radius:7px;color:#34405a;font-weight:800}}.cards{{display:grid;gap:12px}}.ipo-card{{background:#fff;border:1px solid var(--border);border-radius:9px;padding:17px 16px;display:grid;gap:13px;text-align:left}}.ipo-card:hover{{border-color:#c9d2df;box-shadow:0 8px 20px rgba(11,23,57,.06)}}.ipo-top{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}.ipo-title{{display:flex;align-items:center;gap:7px;flex-wrap:wrap}}.ipo-top strong{{font-size:16px;color:var(--navy)}}.ipo-top small{{display:block;margin-top:4px;color:var(--muted);font-size:11px}}.ah-badge{{display:inline-flex;align-items:center;height:20px;padding:0 7px;border-radius:4px;background:#eef4ff;color:#2454a6;border:1px solid #cbdcf8;font-size:11px;font-weight:800;line-height:1}}.tier{{display:inline-block;padding:6px 10px;border-radius:5px;font-weight:800;font-size:13px;white-space:nowrap}}.tier.buy{{background:#e7f7ef;color:#0b9f61}}.tier.hold{{background:#fff3e3;color:#cc7400}}.tier.avoid{{background:#feecee;color:#d20e15}}.metrics{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px;border-top:1px solid #edf0f5;padding-top:12px}}.metrics span{{min-width:0;color:#34405a;font-size:12px;line-height:1.4}}.metrics b{{display:block;margin-bottom:4px;color:var(--muted);font-size:10px;font-weight:600}}.empty{{display:none;background:#fff;border:1px solid var(--border);border-radius:9px;padding:44px;text-align:center;color:var(--muted)}}.source-note{{margin:16px 2px 0;color:#7c8598;font-size:11px;line-height:1.6}}.drawer-backdrop{{position:fixed;inset:0;background:rgba(11,23,57,.28);z-index:40;display:none}}.drawer-backdrop.open{{display:block}}.drawer{{position:fixed;right:0;top:0;bottom:0;width:min(430px,100vw);background:#fff;z-index:41;box-shadow:-12px 0 30px rgba(11,23,57,.18);transform:translateX(100%);transition:transform .18s ease;overflow:auto;padding:22px}}.drawer.open{{transform:translateX(0)}}.drawer-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;border-bottom:1px solid var(--border);padding-bottom:15px;margin-bottom:14px}}.drawer-title{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}.drawer h2{{font-size:20px;margin:0 0 7px}}.drawer-code{{color:var(--muted);font-size:12px;margin-right:8px}}.close{{border:0;background:none;font-size:28px;line-height:1;color:#17233d}}.detail-meta{{color:var(--muted);font-size:12px;line-height:1.7;margin:0 0 18px}}.detail-section{{border-top:1px solid var(--border);padding-top:17px;margin-top:17px}}.detail-section h3{{font-size:14px;margin:0 0 12px}}.issue-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.issue-grid div{{border:1px solid #edf0f5;border-radius:7px;padding:10px;background:#fafbfe;min-width:0}}.issue-grid dt{{color:var(--muted);font-size:11px;font-weight:700;margin-bottom:5px}}.issue-grid dd{{margin:0;color:#25324d;font-size:13px;line-height:1.45;font-weight:650;overflow-wrap:anywhere}}.dims{{display:grid;gap:11px}}.dim{{display:grid;grid-template-columns:92px 1fr 34px;gap:8px;align-items:center;font-size:12px}}.dim span{{color:#39455e}}.bar{{height:6px;background:#e8ecf2;border-radius:5px;overflow:hidden}}.bar i{{display:block;height:100%;background:var(--navy)}}.quality,.risks{{margin:0;padding-left:18px;color:#34405a;font-size:13px;line-height:1.75}}.summary-text{{margin:0;color:#34405a;font-size:13px;line-height:1.7}}footer{{font-size:11px;color:#7c8598;padding:14px 18px;background:#fff;border-top:1px solid var(--border)}}@media(min-width:760px){{.topbar{{height:64px;padding:0 28px}}.menu{{display:none}}.page{{padding:30px 28px 56px}}.page-title h1{{font-size:34px}}.summary{{margin-bottom:14px}}.insights{{display:grid;grid-template-columns:1fr 1fr;gap:0;padding:0}}.insights section{{padding:18px 22px}}.insights section+section{{border-top:0;border-left:1px solid var(--border);margin-top:0;padding-top:18px}}.funding-conflict{{grid-template-columns:230px 1fr;align-items:start;padding:15px 20px}}.funding-conflict dl{{grid-template-columns:repeat(2,minmax(0,1fr));column-gap:18px}}.filters{{grid-template-columns:220px 220px 160px;align-items:end}}.reset{{grid-column:auto}}.cards{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:520px){{.page{{padding-left:14px;padding-right:14px}}.primary{{padding:11px 13px;font-size:12px}}.page-title h1{{font-size:28px}}.page-title p{{font-size:12px}}.stats{{padding-left:4px;padding-right:4px}}.stat{{padding-left:4px;padding-right:4px}}.stat span{{font-size:12px}}.stat strong{{font-size:25px}}.funding-conflict dl div{{grid-template-columns:1fr}}.drawer{{top:auto;height:82vh;border-radius:14px 14px 0 0;width:100%;transform:translateY(100%)}}.drawer.open{{transform:translateY(0)}}}}
</style></head><body><header class="topbar"><div class="brand">港股IPO分析</div><button class="menu" aria-label="菜单">☰</button></header><main class="page"><div class="page-title"><div><h1>今日 IPO 分析</h1><p>{len(data)} 只真实 IPO · 透明评分 · 数据截至 {report_date.isoformat()} {html.escape(generated_at)}</p></div><a class="primary" href="ipo_daily_analysis.md" download>▣ 生成今日日报</a></div><section class="summary"><div class="stats"><div class="stat"><span>今日项目数</span><strong>{len(data)}</strong></div><div class="stat"><span>建议申购</span><strong class="green">{counts['申购']}</strong></div><div class="stat"><span>建议观望</span><strong class="amber">{counts['观望']}</strong></div><div class="stat"><span>建议回避</span><strong class="red">{counts['回避']}</strong></div></div><div class="insights"><section><h3>1）按“基本面和估值”来看</h3><p class="ranking">{html.escape(ranking) if ranking else '暂无申购/观望项目'}</p></section><section><h3>2）中签难度初判</h3><dl class="difficulty">{difficulty_html}</dl></section></div></section>{funding_conflict_html}<div class="filters"><label>行业<select id="industry"><option value="">全部</option></select></label><label>推荐<select id="tier"><option value="">全部</option><option>申购</option><option>观望</option><option>回避</option></select></label><button class="reset" id="reset">↻ 重置</button></div><section class="cards" id="cards"></section><div class="empty" id="empty">没有符合条件的 IPO</div><p class="source-note">数据源：{html.escape(source_path.name)} · A/H 溢价：ah_premium_{report_date.isoformat()}.csv · 上方分析已排除回避项目。</p></main><div class="drawer-backdrop" id="backdrop"></div><aside class="drawer" id="drawer" aria-label="个股详情" aria-hidden="true"><div class="drawer-head"><div><div class="drawer-title"><h2 id="d-name"></h2><span class="ah-badge" id="d-ah-badge">A+H</span></div><span class="drawer-code" id="d-code"></span><span id="d-tier"></span></div><button class="close" id="close" aria-label="关闭">×</button></div><p class="detail-meta" id="d-meta"></p><section class="detail-section"><h3>发行资料</h3><dl class="issue-grid" id="d-issue"></dl></section><section class="detail-section"><h3>评分维度</h3><div class="dims" id="d-dims"></div></section><section class="detail-section"><h3>A/H 溢价</h3><p class="summary-text" id="d-ah"></p></section><section class="detail-section"><h3>公司质地</h3><ol class="quality" id="d-quality"></ol></section><section class="detail-section"><h3>风险提示</h3><ul class="risks" id="d-risks"></ul></section><section class="detail-section"><h3>研究结论</h3><p class="summary-text" id="d-summary"></p></section></aside><footer>免责声明：数据来自本地招股书及结构化资料，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。</footer><script>const DATA={data_json};const $=id=>document.getElementById(id);const weights=[1,1,1,3,3,1],labels=['基石投资者','基石质量','绿鞋机制','公开申购倍数','估值吸引力','保荐人'];function tierClass(t){{return t==='申购'?'buy':t==='观望'?'hold':'avoid'}}function ahBadge(x){{return x.isAh?'<span class="ah-badge">A+H</span>':''}}function yesNo(v){{return v==null?'待补充':v?'有':'无'}}function numText(v,suffix=''){{return v==null?'待补充':v.toLocaleString('zh-HK')+suffix}}function render(){{const ind=$('industry').value,tier=$('tier').value;const list=DATA.filter(x=>(!ind||x.industry===ind)&&(!tier||x.tier===tier));$('cards').innerHTML=list.map(x=>`<button class="ipo-card" type="button" data-code="${{x.code}}"><div class="ipo-top"><div><div class="ipo-title"><strong>${{x.name}}</strong>${{ahBadge(x)}}</div><small>${{x.code}}.HK · ${{x.industry}}</small></div><span class="tier ${{tierClass(x.tier)}}">${{x.tier}}</span></div><div class="metrics"><span><b>招股价</b>${{x.price}} HKD</span><span><b>最小申购金额</b>${{x.minimum==null?'待补充':x.minimum.toLocaleString('zh-HK')+' HKD'}}</span><span><b>市场申购倍数</b>${{x.sub==null?'待补充':x.sub.toFixed(2)+' 倍'}}</span></div></button>`).join('');$('empty').style.display=list.length?'none':'block';$('cards').querySelectorAll('.ipo-card').forEach(card=>card.onclick=()=>openDetail(DATA.find(x=>x.code===card.dataset.code)))}}function openDetail(x){{if(!x)return;$('d-name').textContent=x.name;$('d-ah-badge').style.display=x.isAh?'inline-flex':'none';$('d-code').textContent=x.code+'.HK';$('d-tier').className='tier '+tierClass(x.tier);$('d-tier').textContent=x.tier;$('d-meta').textContent=`港股招股价区间 ${{x.price}} HKD　截止 ${{x.end}}　最小申购 ${{x.minimum==null?'待补充':x.minimum.toLocaleString('zh-HK')+' HKD'}}　认购倍数 ${{x.sub==null?'待补充':x.sub.toFixed(2)+' 倍'}}`;$('d-issue').innerHTML=[['港股招股价区间',x.price+' HKD'],['绿鞋',yesNo(x.greenshoe)],['基石投资者',x.cornerstoneInvestors?.length?x.cornerstoneInvestors.join('、'):'待补充'],['基石占比',x.cornerstoneRatio==null?'待补充':x.cornerstoneRatio.toFixed(2)+'%'],['发行数量',numText(x.issuanceShares,' 股')],['每手股数',numText(x.lotSize,' 股')],['保荐人',x.sponsors?.length?x.sponsors.join('、'):'待补充']].map(([k,v])=>`<div><dt>${{k}}</dt><dd>${{v}}</dd></div>`).join('');$('d-dims').innerHTML=x.scores.map((v,i)=>`<div class="dim"><span>${{labels[i]}}</span><div class="bar"><i style="width:${{Math.max(0,Math.min(100,v/weights[i]*100))}}%"></i></div><b>${{v}}</b></div>`).join('');$('d-ah').textContent='港股招股价区间 '+x.price+' HKD。'+(x.ahPremium==null?'非 A+H 或数据待补充':`A股 ${{x.aTicker}} 最新收盘 ${{x.aClose==null?'待补充':x.aClose.toFixed(2)+' CNY'}}，CNY/HKD ${{x.cnyHkd==null?'待补充':x.cnyHkd.toFixed(4)}}，A/H 溢价 ${{x.ahPremium.toFixed(1)}}%`);$('d-quality').innerHTML=(x.quality||[]).map(q=>`<li>${{q}}</li>`).join('')||'<li>待补充</li>';$('d-risks').innerHTML=(x.risks||[]).map(r=>`<li>${{r}}</li>`).join('')||'<li>待补充</li>';$('d-summary').textContent=x.summary;$('drawer').classList.add('open');$('backdrop').classList.add('open');$('drawer').setAttribute('aria-hidden','false')}}function closeDetail(){{$('drawer').classList.remove('open');$('backdrop').classList.remove('open');$('drawer').setAttribute('aria-hidden','true')}}const industries=[...new Set(DATA.map(x=>x.industry))].sort();$('industry').innerHTML+=industries.map(x=>`<option>${{x}}</option>`).join('');$('industry').onchange=render;$('tier').onchange=render;$('reset').onclick=()=>{{$('industry').value='';$('tier').value='';render()}};$('close').onclick=closeDetail;$('backdrop').onclick=closeDetail;document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeDetail()}});render();</script></body></html>"""


def allotment_difficulty(data: list[dict]) -> list[dict]:
    bands = [
        ("极难", 100, float("inf"), "百倍以上认购，预计中签率最低"),
        ("较难", 50, 100, "50至100倍认购"),
        ("中等", 10, 50, "10至50倍认购"),
        ("较易", 0, 10, "低于10倍认购；仍不代表一定获配"),
    ]
    groups = []
    for label, minimum, maximum, note in bands:
        companies = [item["name"] for item in data if item.get("sub") is not None and minimum <= item["sub"] < maximum]
        if companies:
            groups.append({"label": label, "companies": companies, "note": note})
    return groups


def funding_conflict(data: list[dict]) -> str:
    active = [item for item in data if item["tier"] in {"申购", "观望"}]
    by_date: dict[str, list[dict]] = {}
    avoid_by_date: dict[str, list[dict]] = {}
    for item in data:
        target = avoid_by_date if item["tier"] == "回避" else by_date
        target.setdefault(item["end"], []).append(item)

    rows = []
    for end, items in sorted(by_date.items()):
        total = sum(float(item.get("minimum") or 0) for item in items)
        names = " + ".join(item["name"] for item in sorted(items, key=lambda x: (x["tier"] != "申购", -x["total"])))
        avoid_names = " + ".join(item["name"] for item in avoid_by_date.get(end, []))
        note = f"最低一手合计 HK${total:,.0f}"
        if avoid_names:
            note += f"；回避票若参与另占用：{avoid_names}"
        rows.append({"end": end[5:], "count": len(items), "total": total, "names": names, "note": note})

    if not rows:
        return ""

    peak = max(rows, key=lambda item: (item["total"], item["count"]))
    row_html = "".join(
        f"<div><dt>{html.escape(row['end'])}</dt><dd>{html.escape(row['names'])}<small>{html.escape(row['note'])}</small></dd></div>"
        for row in rows
    )
    total_active = sum(float(item.get("minimum") or 0) for item in active)
    return (
        '<section class="funding-conflict" aria-label="资金冲突情况">'
        '<div>'
        '<h3>3）资金冲突情况</h3>'
        f'<p class="funding-conflict-summary"><span>压力最高</span><strong>{html.escape(peak["end"])}</strong>'
        f'<span>{peak["count"]} 只，最低一手约 HK${peak["total"]:,.0f}</span></p>'
        f'<p class="summary-text">申购/观望票最低一手合计约 HK${total_active:,.0f}，同日截止需预留现金。</p>'
        '</div>'
        f'<dl>{row_html}</dl>'
        '</section>'
    )

def html_item(detail: dict) -> dict:
    dimensions = {item["key"]: item for item in detail["dimensions"]}
    scores = [
        dimensions.get("cornerstone_presence", {}).get("score", 0),
        dimensions.get("cornerstone_quality", {}).get("score", 0),
        dimensions.get("greenshoe", {}).get("score", 0),
        dimensions.get("subscription", {}).get("score", 0),
        dimensions.get("valuation", {}).get("score", 0),
        dimensions.get("sponsor", {}).get("score", 0),
    ]
    return {
        "code": detail["code"].replace(".HK", ""),
        "name": detail["name"],
        "industry": detail["industry"],
        "price": price_text(detail["price_low"], detail["price_high"]),
        "end": detail["deadline"],
        "minimum": detail.get("minimum_subscription_amount"),
        "sub": detail.get("subscription_multiple"),
        "issuanceShares": detail.get("issuance_shares"),
        "lotSize": detail.get("lot_size"),
        "greenshoe": detail.get("greenshoe"),
        "cornerstoneInvestors": detail.get("cornerstone_investors", []),
        "cornerstoneRatio": detail.get("cornerstone_ratio"),
        "sponsors": detail.get("sponsors", []),
        "scores": scores,
        "total": detail["final_score"],
        "tier": detail["recommendation"],
        "summary": summary_text(detail),
        "isAh": bool(detail["metrics"].get("is_ah")),
        "ahPremium": detail["metrics"].get("ah_premium"),
        "aTicker": detail["metrics"].get("a_ticker"),
        "aClose": detail["metrics"].get("a_close_cny"),
        "cnyHkd": detail["metrics"].get("cny_hkd"),
        "quality": detail.get("company_quality", []),
        "risks": detail.get("risks", []),
        "allocation": 0,
        "result": "待公布",
    }


def price_text(low: float, high: float) -> str:
    return f"{low:.2f}" if low == high else f"{low:.2f}–{high:.2f}"


def summary_text(detail: dict) -> str:
    multiple = detail.get("subscription_multiple")
    prefix = f"规则{detail['final_score']:.0f}分"
    if detail["recommendation"] == "观望":
        return f"{prefix}；仍可申购，认购热度{'待补充' if multiple is None else f'{multiple:.2f}倍'}，建议结合估值和中签率谨慎观察。"
    if detail["recommendation"] == "申购":
        return f"{prefix}；评分达到申购区间，但仍需控制单票仓位。"
    return f"{prefix}；当前规则分偏低，暂不纳入优先申购。"


def allocation_plan(data: list[dict]) -> list[dict]:
    candidates = [item for item in data if item["tier"] in {"申购", "观望"}]
    candidates.sort(key=lambda item: (item["total"], item["sub"] or 0), reverse=True)
    plan = []
    remaining = 50_000
    for item in candidates[:5]:
        amount = min(10_000, remaining)
        if amount <= 0:
            break
        item["allocation"] = amount
        plan.append(item)
        remaining -= amount
    return plan


if __name__ == "__main__":
    main()
