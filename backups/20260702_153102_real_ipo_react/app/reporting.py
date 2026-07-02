from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from app.database import connect
from app.repository import list_ipos


def _markdown(report_date: date, version: int, items: list[dict]) -> str:
    counts = {label: sum(i["recommendation"] == label for i in items) for label in ("申购", "观望", "回避")}
    lines = [f"# 港股 IPO 分析日报（{report_date}，v{version}）", "", "> 本报告仅使用样例数据，仅供研究演示，不构成任何投资建议。", "",
             f"共 {len(items)} 个项目：申购 {counts['申购']}，观望 {counts['观望']}，回避 {counts['回避']}。", "",
             "| 公司 | 代码 | 行业 | 招股价(HKD) | 原始分 | 调整 | 最终分 | 建议 |",
             "|---|---|---|---:|---:|---:|---:|---|"]
    for item in items:
        lines.append(f"| {item['name']} | {item['code']} | {item['industry']} | {item['price_low']:.2f}-{item['price_high']:.2f} | {item['original_score']:.1f} | {item['adjustment']:+.1f} | {item['final_score']:.1f} | {item['recommendation']} |")
    lines += ["", "## 风险提示", "", "- 样例数据并非真实招股资料。", "- IPO 投资存在价格波动、流动性及信息不完整风险。"]
    return "\n".join(lines) + "\n"


def create_report(report_date: date | None = None) -> dict:
    report_date = report_date or date.today()
    items = list_ipos(page_size=100)["items"]
    with connect() as db:
        version = db.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM reports WHERE report_date=?", (report_date.isoformat(),)).fetchone()[0]
        markdown = _markdown(report_date, version, items)
        counts = {label: sum(i["recommendation"] == label for i in items) for label in ("申购", "观望", "回避")}
        cursor = db.execute("""INSERT INTO reports
            (report_date, version, created_at, markdown, item_count, buy_count, hold_count, avoid_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_date.isoformat(), version, datetime.now().isoformat(timespec="seconds"), markdown, len(items),
             counts["申购"], counts["观望"], counts["回避"]))
        report_id = cursor.lastrowid
    return get_report(report_id)


def list_reports() -> list[dict]:
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM reports ORDER BY report_date DESC, version DESC").fetchall()]


def get_report(report_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        return dict(row) if row else None


def _font() -> str:
    candidates = ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("CJK", candidate, subfontIndex=0))
                return "CJK"
            except Exception:
                continue
    return "Helvetica"


def report_pdf(report: dict) -> bytes:
    font = _font()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm,
                            title=f"港股IPO分析日报 {report['report_date']}")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("CJKTitle", parent=styles["Title"], fontName=font, fontSize=19, leading=25, textColor=colors.HexColor("#0B1739"))
    body = ParagraphStyle("CJKBody", parent=styles["BodyText"], fontName=font, fontSize=9, leading=14)
    story = [Paragraph(f"港股 IPO 分析日报", title), Paragraph(f"{report['report_date']} · 版本 {report['version']}", body), Spacer(1, 6*mm),
             Paragraph("本报告仅使用样例数据，仅供研究演示，不构成任何投资建议。", body), Spacer(1, 5*mm)]
    items = list_ipos(page_size=100)["items"]
    data = [["公司", "代码", "行业", "原始分", "调整", "最终分", "建议"]]
    data += [[i["name"], i["code"], i["industry"], f"{i['original_score']:.1f}", f"{i['adjustment']:+.1f}", f"{i['final_score']:.1f}", i["recommendation"]] for i in items]
    table = Table(data, colWidths=[47*mm, 23*mm, 29*mm, 18*mm, 17*mm, 18*mm, 17*mm], repeatRows=1)
    table.setStyle(TableStyle([("FONTNAME", (0,0), (-1,-1), font), ("FONTSIZE", (0,0), (-1,-1), 8),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B1739")), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ALIGN", (3,1), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#D9DEE8")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F9FC")]),
        ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
    story += [table, Spacer(1, 7*mm), Paragraph("风险提示", ParagraphStyle("H", parent=body, fontSize=12, leading=17, textColor=colors.HexColor("#0B1739"))),
              Spacer(1, 2*mm), Paragraph("样例数据并非真实招股资料。IPO 投资存在价格波动、流动性及信息不完整风险。", body)]
    doc.build(story)
    return buffer.getvalue()

