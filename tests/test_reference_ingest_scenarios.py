"""
Integration tests for ICD and OPS reference ingest using shared fixtures.

Each fixture file under tests/fixtures/reference_ingest/ is built with
ten pipe-delimited rows (except subset files, which have five rows).
"""

from pathlib import Path

from ingest.icd_ingest import parse_icd_file, upsert_icd_rows
from ingest.ops_ingest import parse_ops_file, upsert_ops_rows

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "reference_ingest"
VERSION_YEAR = 2025


def _icd(path: str):
    return parse_icd_file(path, VERSION_YEAR)


def _ops(path: str):
    return parse_ops_file(path, VERSION_YEAR)


# --- ICD ---


def test_icd_load_single_file_ten_entries(db_conn):
    path = str(FIXTURES / "icd" / "icd_10_valid.txt")
    rows, c = _icd(path)
    assert c.read == 10
    assert c.accepted == 10
    assert c.skipped == 0
    assert len(rows) == 10

    with db_conn.cursor() as cur:
        ins, upd = upsert_icd_rows(cur, rows, batch_size=50)
    db_conn.commit()
    assert ins == 10
    assert upd == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM icd_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 10


def test_icd_load_two_nonoverlapping_files(db_conn):
    pa = str(FIXTURES / "icd" / "icd_nonoverlap_a.txt")
    pb = str(FIXTURES / "icd" / "icd_nonoverlap_b.txt")
    ra, ca = _icd(pa)
    rb, cb = _icd(pb)
    assert ca.accepted == 10 and cb.accepted == 10

    with db_conn.cursor() as cur:
        ins1, _ = upsert_icd_rows(cur, ra, batch_size=50)
        ins2, _ = upsert_icd_rows(cur, rb, batch_size=50)
    db_conn.commit()
    assert ins1 == 10 and ins2 == 10

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM icd_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 20


def test_icd_single_file_with_corrupt_entry(db_conn):
    path = str(FIXTURES / "icd" / "icd_one_corrupt.txt")
    rows, c = _icd(path)
    assert c.read == 10
    assert c.accepted == 9
    assert c.skipped == 1

    with db_conn.cursor() as cur:
        ins, upd = upsert_icd_rows(cur, rows, batch_size=50)
    db_conn.commit()
    assert ins == 9 and upd == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM icd_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 9


def test_icd_duplicate_key_in_one_file_last_wins(db_conn):
    path = str(FIXTURES / "icd" / "icd_duplicates_in_file.txt")
    rows, c = _icd(path)
    assert c.read == 10
    assert c.accepted == 10

    with db_conn.cursor() as cur:
        ins, upd = upsert_icd_rows(cur, rows, batch_size=50)
    db_conn.commit()
    assert ins == 9
    assert upd == 1

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM icd_reference WHERE code=%s AND version_year=%s",
            ("E01.4", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "ICD duplicate last wins E01.4"


def test_icd_two_overlapping_files(db_conn):
    pa = str(FIXTURES / "icd" / "icd_overlap_a.txt")
    pb = str(FIXTURES / "icd" / "icd_overlap_b.txt")
    ra, _ = _icd(pa)
    rb, _ = _icd(pb)

    with db_conn.cursor() as cur:
        ins_a, _ = upsert_icd_rows(cur, ra, batch_size=50)
        ins_b, upd_b = upsert_icd_rows(cur, rb, batch_size=50)
    db_conn.commit()
    assert ins_a == 10
    assert ins_b == 5
    assert upd_b == 5

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM icd_reference WHERE code=%s AND version_year=%s",
            ("F01.7", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "ICD overlapB F01.7"
        cur.execute("SELECT COUNT(*) FROM icd_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 15


def test_icd_load_same_file_twice(db_conn):
    path = str(FIXTURES / "icd" / "icd_10_valid.txt")
    rows1, _ = _icd(path)
    rows2, _ = _icd(path)

    with db_conn.cursor() as cur:
        ins1, upd1 = upsert_icd_rows(cur, rows1, batch_size=50)
        ins2, upd2 = upsert_icd_rows(cur, rows2, batch_size=50)
    db_conn.commit()
    assert ins1 == 10 and upd1 == 0
    assert ins2 == 0 and upd2 == 10

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM icd_reference WHERE code LIKE 'A01.%%' AND version_year=%s",
            (VERSION_YEAR,),
        )
        assert cur.fetchone()[0] == 10


def test_icd_two_files_same_keys_different_values(db_conn):
    pa = str(FIXTURES / "icd" / "icd_same_keys_values_a.txt")
    pb = str(FIXTURES / "icd" / "icd_same_keys_values_b.txt")
    ra, _ = _icd(pa)
    rb, _ = _icd(pb)

    with db_conn.cursor() as cur:
        upsert_icd_rows(cur, ra, batch_size=50)
        ins, upd = upsert_icd_rows(cur, rb, batch_size=50)
    db_conn.commit()
    assert ins == 0
    assert upd == 10

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM icd_reference WHERE code=%s AND version_year=%s",
            ("H01.3", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "ICD valueB H01.3"


def test_icd_subset_file_then_superset_file(db_conn):
    ps = str(FIXTURES / "icd" / "icd_subset_small.txt")
    pl = str(FIXTURES / "icd" / "icd_superset_large.txt")
    rs, cs = _icd(ps)
    rl, cl = _icd(pl)
    assert cs.accepted == 5
    assert cl.accepted == 10

    with db_conn.cursor() as cur:
        ins_s, _ = upsert_icd_rows(cur, rs, batch_size=50)
        ins_l, upd_l = upsert_icd_rows(cur, rl, batch_size=50)
    db_conn.commit()
    assert ins_s == 5 and ins_l == 5 and upd_l == 5

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM icd_reference WHERE code=%s AND version_year=%s",
            ("J01.2", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "ICD superset J01.2"
        cur.execute(
            "SELECT COUNT(*) FROM icd_reference WHERE code LIKE 'J01.%%' AND version_year=%s",
            (VERSION_YEAR,),
        )
        assert cur.fetchone()[0] == 10


# --- OPS ---


def test_ops_load_single_file_ten_entries(db_conn):
    path = str(FIXTURES / "ops" / "ops_10_valid.txt")
    rows, c = _ops(path)
    assert c.read == 10
    assert c.accepted == 10
    assert c.skipped == 0

    with db_conn.cursor() as cur:
        ins, upd = upsert_ops_rows(cur, rows, batch_size=50)
    db_conn.commit()
    assert ins == 10 and upd == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ops_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 10


def test_ops_load_two_nonoverlapping_files(db_conn):
    pa = str(FIXTURES / "ops" / "ops_nonoverlap_a.txt")
    pb = str(FIXTURES / "ops" / "ops_nonoverlap_b.txt")
    ra, _ = _ops(pa)
    rb, _ = _ops(pb)

    with db_conn.cursor() as cur:
        ins1, _ = upsert_ops_rows(cur, ra, batch_size=50)
        ins2, _ = upsert_ops_rows(cur, rb, batch_size=50)
    db_conn.commit()
    assert ins1 == 10 and ins2 == 10

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ops_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 20


def test_ops_single_file_with_corrupt_entry(db_conn):
    path = str(FIXTURES / "ops" / "ops_one_corrupt.txt")
    rows, c = _ops(path)
    assert c.read == 10
    assert c.accepted == 9
    assert c.skipped == 1

    with db_conn.cursor() as cur:
        ins, upd = upsert_ops_rows(cur, rows, batch_size=50)
    db_conn.commit()
    assert ins == 9 and upd == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ops_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 9


def test_ops_duplicate_key_in_one_file_last_wins(db_conn):
    path = str(FIXTURES / "ops" / "ops_duplicates_in_file.txt")
    rows, c = _ops(path)
    assert c.read == 10
    assert c.accepted == 10

    with db_conn.cursor() as cur:
        ins, upd = upsert_ops_rows(cur, rows, batch_size=50)
    db_conn.commit()
    assert ins == 9
    assert upd == 1

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM ops_reference WHERE code=%s AND version_year=%s",
            ("5-940.0", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "OPS duplicate last wins"


def test_ops_two_overlapping_files(db_conn):
    pa = str(FIXTURES / "ops" / "ops_overlap_a.txt")
    pb = str(FIXTURES / "ops" / "ops_overlap_b.txt")
    ra, _ = _ops(pa)
    rb, _ = _ops(pb)

    with db_conn.cursor() as cur:
        ins_a, _ = upsert_ops_rows(cur, ra, batch_size=50)
        ins_b, upd_b = upsert_ops_rows(cur, rb, batch_size=50)
    db_conn.commit()
    assert ins_a == 10
    assert ins_b == 5
    assert upd_b == 5

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM ops_reference WHERE code=%s AND version_year=%s",
            ("6-970.0", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "OPS oB 7"
        cur.execute("SELECT COUNT(*) FROM ops_reference WHERE version_year=%s", (VERSION_YEAR,))
        assert cur.fetchone()[0] == 15


def test_ops_load_same_file_twice(db_conn):
    path = str(FIXTURES / "ops" / "ops_10_valid.txt")
    rows1, _ = _ops(path)
    rows2, _ = _ops(path)

    with db_conn.cursor() as cur:
        ins1, upd1 = upsert_ops_rows(cur, rows1, batch_size=50)
        ins2, upd2 = upsert_ops_rows(cur, rows2, batch_size=50)
    db_conn.commit()
    assert ins1 == 10 and upd1 == 0
    assert ins2 == 0 and upd2 == 10

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM ops_reference WHERE code LIKE '1-9%%' AND version_year=%s",
            (VERSION_YEAR,),
        )
        assert cur.fetchone()[0] == 10


def test_ops_two_files_same_keys_different_values(db_conn):
    pa = str(FIXTURES / "ops" / "ops_same_keys_values_a.txt")
    pb = str(FIXTURES / "ops" / "ops_same_keys_values_b.txt")
    ra, _ = _ops(pa)
    rb, _ = _ops(pb)

    with db_conn.cursor() as cur:
        upsert_ops_rows(cur, ra, batch_size=50)
        ins, upd = upsert_ops_rows(cur, rb, batch_size=50)
    db_conn.commit()
    assert ins == 0
    assert upd == 10

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM ops_reference WHERE code=%s AND version_year=%s",
            ("8-930.0", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "OPS valueB 3"


def test_ops_subset_file_then_superset_file(db_conn):
    ps = str(FIXTURES / "ops" / "ops_subset_small.txt")
    pl = str(FIXTURES / "ops" / "ops_superset_large.txt")
    rs, cs = _ops(ps)
    rl, cl = _ops(pl)
    assert cs.accepted == 5
    assert cl.accepted == 10

    with db_conn.cursor() as cur:
        ins_s, _ = upsert_ops_rows(cur, rs, batch_size=50)
        ins_l, upd_l = upsert_ops_rows(cur, rl, batch_size=50)
    db_conn.commit()
    assert ins_s == 5 and ins_l == 5 and upd_l == 5

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT description_de FROM ops_reference WHERE code=%s AND version_year=%s",
            ("9-920.0", VERSION_YEAR),
        )
        assert cur.fetchone()[0] == "OPS superset 2"
        cur.execute(
            "SELECT COUNT(*) FROM ops_reference WHERE code LIKE '9-9%%' AND version_year=%s",
            (VERSION_YEAR,),
        )
        assert cur.fetchone()[0] == 10
