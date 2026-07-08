import csv
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path


def write_csv_atomic(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> Path:
    """Write a CSV via same-directory replace so stale file ownership cannot block refreshes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.chmod(temp_name, 0o666)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return path
