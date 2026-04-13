"""Shared utilities for ingestion workflows."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from typing import Iterable

# DB config from env (matches src/config/database.js)
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "database": os.environ.get("DB_NAME", "hospital_db"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
}


def get_version_year_from_filename(path: str | Path) -> int | None:
    """Extract version year from filename (e.g. icd10gm2025syst.xml -> 2025)."""
    name = Path(path).stem.lower()
    for i in range(len(name) - 3):
        if name[i : i + 4].isdigit():
            year = int(name[i : i + 4])
            if 1990 <= year <= 2100:
                return year
    return None


@dataclass
class IngestStats:
    """Counters emitted by each ingest phase."""

    read: int = 0
    accepted: int = 0
    skipped: int = 0
    inserted: int = 0
    updated: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "read": self.read,
            "accepted": self.accepted,
            "skipped": self.skipped,
            "inserted": self.inserted,
            "updated": self.updated,
            "errors": self.errors,
        }


def merge_stats(items: Iterable[IngestStats]) -> IngestStats:
    """Aggregate multiple phase counters."""
    merged = IngestStats()
    for item in items:
        merged.read += item.read
        merged.accepted += item.accepted
        merged.skipped += item.skipped
        merged.inserted += item.inserted
        merged.updated += item.updated
        merged.errors += item.errors
    return merged


def compute_file_signature(path: str | Path) -> dict[str, str]:
    """Compute deterministic file signature using metadata and checksum."""
    p = Path(path)
    stat = p.stat()
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "mtime_ns": str(stat.st_mtime_ns),
        "size_bytes": str(stat.st_size),
        "sha256": digest.hexdigest(),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
