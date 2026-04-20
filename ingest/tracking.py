import hashlib
from pathlib import Path


def file_fingerprint(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return stat.st_size, stat.st_mtime_ns, sha.hexdigest()


def get_existing_tracking(cur, file_path: str):
    cur.execute(
        """
        SELECT file_size_bytes, file_mtime_ns, file_sha256, status
        FROM ingest_files
        WHERE file_path = %s
        """,
        (file_path,),
    )
    return cur.fetchone()


def should_process_file(cur, file_path: str, size_bytes: int, mtime_ns: int, sha256: str) -> bool:
    row = get_existing_tracking(cur, file_path)
    if row is None:
        return True
    old_size, old_mtime_ns, old_sha, old_status = row
    return not (
        old_size == size_bytes
        and old_mtime_ns == mtime_ns
        and old_sha == sha256
        and old_status == "success"
    )


def record_file_result(
    cur,
    file_path: str,
    size_bytes: int,
    mtime_ns: int,
    sha256: str,
    status: str,
    error_message: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO ingest_files (
          file_path, file_size_bytes, file_mtime_ns, file_sha256, last_ingested_at, status, error_message
        ) VALUES (%s, %s, %s, %s, NOW(), %s, %s)
        ON CONFLICT (file_path) DO UPDATE
        SET file_size_bytes = EXCLUDED.file_size_bytes,
            file_mtime_ns = EXCLUDED.file_mtime_ns,
            file_sha256 = EXCLUDED.file_sha256,
            last_ingested_at = NOW(),
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message
        """,
        (file_path, size_bytes, mtime_ns, sha256, status, error_message),
    )

