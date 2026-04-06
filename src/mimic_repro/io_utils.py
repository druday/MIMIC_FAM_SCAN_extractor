"""I/O and provenance helpers for reproducible pipeline execution."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    """Return a UTC timestamp suitable for run directory names."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def compute_sha256(path: Path) -> str:
    """Compute SHA256 checksum for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_csv_rows(path: Path) -> int:
    """Count data rows in a CSV file."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def ensure_dir(path: Path) -> None:
    """Create a directory and all missing parents."""
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON in a stable, human-readable format."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

