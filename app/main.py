from datetime import date, datetime
import re
import subprocess
import sys
from threading import Lock, Thread
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from app.a_share_sentiment import build_a_share_sentiment, latest_sentiment_history
from app.config import load_rules
from app.config import ROOT
from app.daily_ipo import DailyIPODataMissingError, active_subscription_codes
from app.database import initialize
from app.repository import list_ipos, get_ipo, add_adjustment
from app.reporting import create_report, list_reports, get_report, report_pdf
from app.schemas import IPOList, IPODetail, AdjustmentCreate, Adjustment, ReportDetail, ReportSummary, AShareSentiment, AShareSentimentHistoryPoint, DataRefreshStart, DataRefreshStatus, USMarketDashboard
from app.us_market import build_us_market_dashboard

app = FastAPI(title="港股 IPO 分析 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://www.equity-research-hong-kong-stocks.cn",
    "https://equity-research-hong-kong-stocks.cn",
],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

refresh_jobs: dict[str, dict] = {}
refresh_lock = Lock()
REFRESH_PROGRESS_PATTERN = re.compile(r"\[(\d+)/(\d+)\]\s*(开始|完成|失败)：(.+?)(?:（|$)")


@app.on_event("startup")
def startup():
    initialize()


@app.get("/api/health")
def health():
    return {"status": "ok", "sample_data": False}


@app.get("/api/ipos", response_model=IPOList)
def ipos(industry: str | None = None, recommendation: str | None = None, deadline: date | None = None,
         sort: str = "final_score", order: str = Query("desc", pattern="^(asc|desc)$"),
         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
         active: bool = False, report_date: date | None = None):
    active_codes = None
    if active:
        try:
            active_codes = active_subscription_codes(report_date or date.today())
        except DailyIPODataMissingError as exc:
            raise HTTPException(409, str(exc)) from exc
    return list_ipos(industry, recommendation, deadline.isoformat() if deadline else None, sort, order, page, page_size, active_codes)


@app.get("/api/ipos/{ipo_id}", response_model=IPODetail)
def ipo_detail(ipo_id: int):
    result = get_ipo(ipo_id)
    if not result:
        raise HTTPException(404, "IPO 不存在")
    return result


@app.post("/api/ipos/{ipo_id}/adjustments", response_model=Adjustment, status_code=201)
def adjust(ipo_id: int, payload: AdjustmentCreate):
    result = add_adjustment(ipo_id, payload.value, payload.reason, payload.operator)
    if not result:
        raise HTTPException(404, "IPO 不存在")
    return result


@app.get("/api/scoring-rules")
def scoring_rules():
    return load_rules()


@app.post("/api/data-refresh", response_model=DataRefreshStart, status_code=202)
def start_data_refresh(report_date: date | None = None):
    job_id = uuid4().hex
    target_date = report_date or date.today()
    job = {
        "job_id": job_id,
        "status": "running",
        "started_at": datetime.now(),
        "finished_at": None,
        "report_date": target_date,
        "detail": None,
        "progress_current": 0,
        "progress_total": 11,
        "progress_percent": 0,
        "progress_label": "等待开始",
    }
    with refresh_lock:
        refresh_jobs[job_id] = job
    Thread(target=run_data_refresh_job, args=(job_id, target_date), daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/data-refresh/{job_id}", response_model=DataRefreshStatus)
def data_refresh_status(job_id: str):
    with refresh_lock:
        job = refresh_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "刷新任务不存在")
    return job


def run_data_refresh_job(job_id: str, report_date: date) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_daily_report.py"),
        "--date",
        report_date.isoformat(),
        "--wait",
        "0",
    ]
    output_lines: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        if process.stdout is None:
            raise RuntimeError("刷新任务未返回进度输出")
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            output_lines.append(line)
            update_refresh_progress(job_id, line, "\n".join(output_lines)[-4000:])
        return_code = process.wait()
        detail = "\n".join(output_lines).strip()[-4000:] or None
        status = "succeeded" if return_code == 0 else "failed"
    except Exception as exc:
        detail = str(exc)
        status = "failed"
    with refresh_lock:
        job = refresh_jobs[job_id]
        job["status"] = status
        job["finished_at"] = datetime.now()
        job["detail"] = detail
        if status == "succeeded":
            job["progress_current"] = job.get("progress_total", 11)
            job["progress_percent"] = 100
            job["progress_label"] = "全部完成"


def update_refresh_progress(job_id: str, line: str, detail: str | None) -> None:
    match = REFRESH_PROGRESS_PATTERN.search(line)
    with refresh_lock:
        job = refresh_jobs.get(job_id)
        if not job:
            return
        job["detail"] = detail
        if not match:
            return
        step = int(match.group(1))
        total = int(match.group(2))
        phase = match.group(3)
        label = match.group(4).strip()
        completed = step if phase == "完成" else max(step - 1, 0)
        job["progress_current"] = completed
        job["progress_total"] = total
        job["progress_percent"] = round(completed / total * 100)
        job["progress_label"] = f"{phase}：{label}"


@app.get("/api/a-shares/sentiment", response_model=AShareSentiment)
def a_share_sentiment(record_date: date | None = None, refresh: bool = False):
    return build_a_share_sentiment(record_date, refresh)


@app.get("/api/a-shares/sentiment/history", response_model=list[AShareSentimentHistoryPoint])
def a_share_sentiment_history(limit: int = Query(15, ge=1, le=60)):
    return latest_sentiment_history(limit)


@app.get("/api/us-market/dashboard", response_model=USMarketDashboard)
def us_market_dashboard(record_date: date | None = None, refresh: bool = False):
    return build_us_market_dashboard(record_date, refresh)


@app.post("/api/reports", response_model=ReportDetail, status_code=201)
def generate_report(report_date: date | None = None):
    try:
        return create_report(report_date)
    except DailyIPODataMissingError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/reports", response_model=list[ReportSummary])
def reports():
    return list_reports()


@app.get("/api/reports/{report_id}", response_model=ReportDetail)
def report_detail(report_id: int):
    report = get_report(report_id)
    if not report:
        raise HTTPException(404, "日报不存在")
    return report


@app.get("/api/reports/{report_id}/download")
def download_report(report_id: int, format: str = Query(pattern="^(md|pdf)$")):
    report = get_report(report_id)
    if not report:
        raise HTTPException(404, "日报不存在")
    filename = "hk-ipo-analysis"
    if format == "md":
        return Response(report["markdown"].encode("utf-8"), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'})
    return Response(report_pdf(report), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})


FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


    @app.get("/{path:path}", include_in_schema=False)
    def frontend_app(path: str):
        target = FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
