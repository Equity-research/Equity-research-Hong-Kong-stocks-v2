from datetime import date
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from app.config import load_rules
from app.daily_ipo import DailyIPODataMissingError
from app.database import initialize
from app.repository import list_ipos, get_ipo, add_adjustment
from app.reporting import create_report, list_reports, get_report, report_pdf
from app.schemas import IPOList, IPODetail, AdjustmentCreate, Adjustment, ReportDetail, ReportSummary

app = FastAPI(title="港股 IPO 分析 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    initialize()


@app.get("/api/health")
def health():
    return {"status": "ok", "sample_data": False}


@app.get("/api/ipos", response_model=IPOList)
def ipos(industry: str | None = None, recommendation: str | None = None, deadline: date | None = None,
         sort: str = "final_score", order: str = Query("desc", pattern="^(asc|desc)$"),
         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return list_ipos(industry, recommendation, deadline.isoformat() if deadline else None, sort, order, page, page_size)


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
    filename = f"hk-ipo-{report['report_date']}-v{report['version']}"
    if format == "md":
        return Response(report["markdown"].encode("utf-8"), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'})
    return Response(report_pdf(report), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})
