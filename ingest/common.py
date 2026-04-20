import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import execute_values


@dataclass
class IngestCounters:
    read: int = 0
    accepted: int = 0
    skipped: int = 0
    inserted: int = 0
    updated: int = 0
    errors: int = 0

    def merge(self, other: "IngestCounters") -> None:
        self.read += other.read
        self.accepted += other.accepted
        self.skipped += other.skipped
        self.inserted += other.inserted
        self.updated += other.updated
        self.errors += other.errors


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def get_connection():
    return psycopg2.connect(
        host=env("DB_HOST", "localhost"),
        port=env("DB_PORT", "5432"),
        dbname=env("DB_NAME", "hospital_db"),
        user=env("DB_USER", "postgres"),
        password=env("DB_PASSWORD", "postgres"),
    )


def repo_root() -> Path:
    """Repository root (parent directory of the `ingest` package)."""
    return Path(__file__).resolve().parent.parent


def resolve_repo_relative(path: str | Path) -> str:
    """Resolve a path relative to the repo root; absolute paths are unchanged."""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str((repo_root() / p).resolve())


def chunked(rows: Iterable[Any], size: int):
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def execute_values_with_retry(
    cursor,
    sql: str,
    rows: list[tuple],
    retries: int = 3,
    base_delay_s: float = 0.2,
) -> None:
    for attempt in range(retries + 1):
        savepoint = f"sp_exec_values_{uuid.uuid4().hex}"
        aux = cursor.connection.cursor()
        try:
            aux.execute(f"SAVEPOINT {savepoint}")
            execute_values(cursor, sql, rows)
            aux.execute(f"RELEASE SAVEPOINT {savepoint}")
            return
        except Exception:
            aux.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            aux.execute(f"RELEASE SAVEPOINT {savepoint}")
            if attempt >= retries:
                raise
            time.sleep(base_delay_s * (2**attempt))
        finally:
            aux.close()

