"""Shared utilities for ICD/OPS ingestion."""

import os
from pathlib import Path

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
