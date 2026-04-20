from pathlib import Path

from ingest.icd_ingest import parse_icd_file, upsert_icd_rows


def test_parse_and_upsert_icd_single_file(db_conn, tmp_data_dir: Path):
    icd_file = tmp_data_dir / "icd.txt"
    icd_file.write_text(
        "\n".join(
            [
                "1|90016|1|A00.0||||Cholera",
                "5|97691|1|||B96.5!||Acinetobacter",
                "0|86498|1|||||Abnorm - s. Art der Krankheit",
                "1|x|1|||||",  # malformed/empty code
            ]
        ),
        encoding="utf-8",
    )

    rows, counters = parse_icd_file(str(icd_file), 2025)
    assert counters.read == 4
    assert counters.accepted == 2
    assert counters.skipped == 2

    with db_conn.cursor() as cur:
        inserted, updated = upsert_icd_rows(cur, rows, batch_size=10)
    db_conn.commit()
    assert inserted == 2
    assert updated == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM icd_reference")
        assert cur.fetchone()[0] == 2


def test_icd_same_keys_different_values_updates(db_conn, tmp_data_dir: Path):
    f1 = tmp_data_dir / "icd1.txt"
    f2 = tmp_data_dir / "icd2.txt"
    f1.write_text("1|1|1|F14.1||||Old label\n", encoding="utf-8")
    f2.write_text("1|2|1|F14.1||||New label\n", encoding="utf-8")

    rows1, _ = parse_icd_file(str(f1), 2025)
    rows2, _ = parse_icd_file(str(f2), 2025)
    with db_conn.cursor() as cur:
        upsert_icd_rows(cur, rows1)
        inserted, updated = upsert_icd_rows(cur, rows2)
    db_conn.commit()
    assert inserted == 0
    assert updated == 1

    with db_conn.cursor() as cur:
        cur.execute("SELECT description_de FROM icd_reference WHERE code='F14.1' AND version_year=2025")
        assert cur.fetchone()[0] == "New label"

