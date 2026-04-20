from pathlib import Path

from ingest.ops_ingest import parse_ops_file, upsert_ops_rows


def test_parse_and_upsert_ops_single_file(db_conn, tmp_data_dir: Path):
    ops_file = tmp_data_dir / "ops.txt"
    ops_file.write_text(
        "\n".join(
            [
                "1|10573|1-100||Klinische Untersuchung",
                "1|6120|8-200.2#||Geschlossene Reposition",
                "0|10422|||Abnorm - s. jeweiliger Eingriff",
            ]
        ),
        encoding="utf-8",
    )

    rows, counters = parse_ops_file(str(ops_file), 2025)
    assert counters.read == 3
    assert counters.accepted == 2
    assert counters.skipped == 1

    with db_conn.cursor() as cur:
        inserted, updated = upsert_ops_rows(cur, rows)
    db_conn.commit()
    assert inserted == 2
    assert updated == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ops_reference")
        assert cur.fetchone()[0] == 2


def test_ops_duplicate_in_one_file(db_conn, tmp_data_dir: Path):
    ops_file = tmp_data_dir / "ops_dupe.txt"
    ops_file.write_text(
        "\n".join(
            [
                "1|1|5-868.0||Alpha",
                "1|2|5-868.0||Beta",
            ]
        ),
        encoding="utf-8",
    )
    rows, _ = parse_ops_file(str(ops_file), 2025)
    with db_conn.cursor() as cur:
        inserted, updated = upsert_ops_rows(cur, rows)
    db_conn.commit()
    assert inserted == 1
    assert updated == 1

    with db_conn.cursor() as cur:
        cur.execute("SELECT description_de FROM ops_reference WHERE code='5-868.0' AND version_year=2025")
        assert cur.fetchone()[0] == "Beta"

