from pathlib import Path

from ingest.tracking import (
    file_fingerprint,
    record_file_result,
    should_process_file,
)


def test_tracking_new_unchanged_changed(db_conn, tmp_data_dir: Path):
    f = tmp_data_dir / "260100023-773287000-2024.json"
    f.write_text('{"hello":"world"}', encoding="utf-8")
    size_b, mtime_ns, sha = file_fingerprint(f)

    with db_conn.cursor() as cur:
        assert should_process_file(cur, str(f), size_b, mtime_ns, sha) is True
        record_file_result(cur, str(f), size_b, mtime_ns, sha, "success", None)
    db_conn.commit()

    with db_conn.cursor() as cur:
        assert should_process_file(cur, str(f), size_b, mtime_ns, sha) is False
    db_conn.commit()

    f.write_text('{"hello":"world2"}', encoding="utf-8")
    size_b2, mtime_ns2, sha2 = file_fingerprint(f)
    with db_conn.cursor() as cur:
        assert should_process_file(cur, str(f), size_b2, mtime_ns2, sha2) is True

