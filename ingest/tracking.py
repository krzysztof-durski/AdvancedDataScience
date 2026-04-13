"""Processed file tracking helpers for deterministic reruns."""

from pathlib import Path

from .common import compute_file_signature


def should_process_file(path: str | Path, phase: str, conn) -> bool:
    """Return True when file metadata/hash differs from last processed state."""
    signature = compute_file_signature(path)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT mtime_ns::text, size_bytes::text, sha256
            FROM ingest_files
            WHERE phase = %s AND file_path = %s
            """,
            (phase, str(path)),
        )
        row = cur.fetchone()
        if not row:
            return True
        return row[0] != signature["mtime_ns"] or row[1] != signature["size_bytes"] or row[2] != signature["sha256"]
    finally:
        cur.close()


def mark_processed_file(path: str | Path, phase: str, conn) -> None:
    """Persist processed-file state after a successful phase run."""
    signature = compute_file_signature(path)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ingest_files (phase, file_path, mtime_ns, size_bytes, sha256)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (phase, file_path) DO UPDATE SET
                mtime_ns = EXCLUDED.mtime_ns,
                size_bytes = EXCLUDED.size_bytes,
                sha256 = EXCLUDED.sha256,
                ingested_at = NOW()
            """,
            (
                phase,
                str(path),
                int(signature["mtime_ns"]),
                int(signature["size_bytes"]),
                signature["sha256"],
            ),
        )
    finally:
        cur.close()
