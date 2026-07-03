import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.config import ROOT
from app.daily_ipo import DailyIPORecord, load_daily_ipo_records
from app.subscription import HKIPOX_URL


@dataclass(frozen=True)
class ProspectusSyncResult:
    directory: Path
    kept: list[Path] = field(default_factory=list)
    reused: list[Path] = field(default_factory=list)
    downloaded: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def prospectus_dir(record_date: date, root: Path = ROOT) -> Path:
    return root / "prospectuses" / record_date.isoformat()


def sync_prospectuses_for_date(record_date: date, root: Path = ROOT) -> ProspectusSyncResult:
    records = _active_records(load_daily_ipo_records(record_date), record_date)
    target_dir = prospectus_dir(record_date, root)
    target_dir.mkdir(parents=True, exist_ok=True)

    active_by_code = {_plain_code(record.stock_code): record for record in records}
    deleted = _delete_stale_pdfs(target_dir, set(active_by_code))

    kept = []
    reused = []
    downloaded = []
    missing = []
    existing = _pdfs_by_code(target_dir)
    for code, record in sorted(active_by_code.items()):
        current = existing.get(code)
        if current is not None:
            kept.append(current)
            continue

        destination = target_dir / prospectus_filename(record)
        source = _find_existing_prospectus(code, target_dir, root)
        if source is not None:
            shutil.copy2(source, destination)
            reused.append(destination)
            existing[code] = destination
            continue

        try:
            url = fetch_prospectus_url(code)
            if url is None:
                missing.append(f"{code} {record.company_name}: 未找到招股书链接")
                continue
            download_prospectus(url, destination)
        except Exception as exc:
            missing.append(f"{code} {record.company_name}: {exc}")
            continue
        downloaded.append(destination)
        existing[code] = destination

    result = ProspectusSyncResult(
        directory=target_dir,
        kept=kept,
        reused=reused,
        downloaded=downloaded,
        deleted=deleted,
        missing=missing,
    )
    if missing:
        joined = "\n".join(f"- {item}" for item in missing)
        raise RuntimeError(f"招股书同步未完成：\n{joined}")
    return result


def fetch_prospectus_url(stock_code: str) -> str | None:
    code = _plain_code(stock_code)
    request = Request(urljoin(HKIPOX_URL, f"/stock/{code}"), headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        page = response.read().decode("utf-8", errors="replace")
    return parse_prospectus_url(page, HKIPOX_URL)


def parse_prospectus_url(page: str, base_url: str = HKIPOX_URL) -> str | None:
    for anchor in re.finditer(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", page, flags=re.S | re.I):
        attrs = anchor.group("attrs")
        body = re.sub(r"<[^>]+>", "", anchor.group("body"))
        if "招股书" not in body and "pdf-link" not in attrs:
            continue
        href = re.search(r"""href=["'](?P<href>[^"']+)["']""", attrs, flags=re.I)
        if href:
            return urljoin(base_url, href.group("href"))
    return None


def download_prospectus(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        content = response.read()
    if not content.startswith(b"%PDF"):
        raise RuntimeError(f"下载内容不是 PDF：{url}")

    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_bytes(content)
    temp.replace(destination)


def prospectus_filename(record: DailyIPORecord) -> str:
    return f"{_plain_code(record.stock_code)}_{_safe_filename_part(record.company_name)}_招股书.pdf"


def _active_records(records: list[DailyIPORecord], record_date: date) -> list[DailyIPORecord]:
    return [
        record for record in records
        if record.subscription_end_date > record_date
        and (record.expected_listing_date is None or record.expected_listing_date > record_date)
    ]


def _delete_stale_pdfs(directory: Path, active_codes: set[str]) -> list[Path]:
    deleted = []
    for path in directory.glob("*.pdf"):
        code = _code_from_filename(path.name)
        if code is None or code in active_codes:
            continue
        path.unlink()
        deleted.append(path)
    return deleted


def _find_existing_prospectus(code: str, target_dir: Path, root: Path) -> Path | None:
    base = root / "prospectuses"
    if not base.exists():
        return None
    candidates = [
        path for path in base.glob(f"*/{code}_*_招股书.pdf")
        if path.parent != target_dir and path.is_file()
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def _pdfs_by_code(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.glob("*.pdf"):
        code = _code_from_filename(path.name)
        if code is not None:
            result[code] = path
    return result


def _code_from_filename(filename: str) -> str | None:
    match = re.match(r"(?P<code>\d{5})_", filename)
    return match.group("code") if match else None


def _plain_code(stock_code: str) -> str:
    return stock_code.removesuffix(".HK").zfill(5)


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", value.strip())
    return cleaned or "unknown"
