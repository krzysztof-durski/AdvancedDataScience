"""Tests for OPS ingestion from pipe-delimited TXT."""

import tempfile
from pathlib import Path

import pytest

from ingest.ops_ingest import parse_ops_txt, ingest_ops_to_db
from ingest.common import get_version_year_from_filename


class TestParseOpsTxt:
    """Tests for parse_ops_txt."""

    def test_parses_sample_txt(self, ops_sample_path):
        records = list(parse_ops_txt(ops_sample_path))
        assert len(records) >= 8
        codes = {r["code"] for r in records}
        assert "1-100" in codes
        assert "1-202.00" in codes
        assert "1-204.0" in codes
        assert "1-205" in codes
        assert "1-207.0" in codes

    def test_skips_level_zero_rows(self, ops_sample_path):
        """Level 0 rows (index/cross-ref) should be skipped."""
        records = list(parse_ops_txt(ops_sample_path))
        labels = [r["label"] for r in records]
        assert "4/5-Resektion des Magens" not in labels
        assert "Abnorm - s. jeweiliger durchgeführter Eingriff" not in labels

    def test_record_schema(self, ops_sample_path):
        records = list(parse_ops_txt(ops_sample_path))
        for r in records:
            assert "code" in r
            assert "label" in r
            assert "chapter" in r
            assert "parent_code" in r
            assert "level" in r
            assert "version_year" in r
            assert "is_terminal" in r

    def test_labels_extracted(self, ops_sample_path):
        records = {r["code"]: r for r in parse_ops_txt(ops_sample_path)}
        assert "Klinische Untersuchung" in records["1-100"]["label"]
        assert "Messung des Hirndruckes" in records["1-204.0"]["label"]

    def test_parent_hierarchy(self, ops_sample_path):
        records = {r["code"]: r for r in parse_ops_txt(ops_sample_path)}
        # 1-202.00 parent should be 1-202.0
        assert records["1-202.00"]["parent_code"] == "1-202.0"
        # 1-202.01 parent should be 1-202.0
        assert records["1-202.01"]["parent_code"] == "1-202.0"

    def test_chapter_extraction(self, ops_sample_path):
        records = {r["code"]: r for r in parse_ops_txt(ops_sample_path)}
        assert records["1-100"]["chapter"] == 1
        assert records["1-204.0"]["chapter"] == 1

    def test_level_inference(self, ops_sample_path):
        records = {r["code"]: r for r in parse_ops_txt(ops_sample_path)}
        # 1-100 (block) = 4, 1-202.0 = 5, 1-202.00 = 6
        assert records["1-100"]["level"] == 4
        assert records["1-202.0"]["level"] == 5
        assert records["1-202.00"]["level"] == 6

    def test_version_year_from_filename(self, ops_sample_path):
        records = list(parse_ops_txt(ops_sample_path))
        assert all(r["version_year"] == 2025 for r in records)

    def test_version_year_explicit(self, ops_sample_path):
        records = list(parse_ops_txt(ops_sample_path, version_year=2024))
        assert all(r["version_year"] == 2024 for r in records)


class TestParseOpsFromDataFolder:
    """Tests against real DATA/OPS-procedures.txt."""

    @pytest.fixture
    def data_ops_path(self):
        p = Path(__file__).resolve().parent.parent / "DATA" / "OPS-procedures.txt"
        if not p.exists():
            pytest.skip("DATA/OPS-procedures.txt not found")
        return p

    def test_parses_real_file(self, data_ops_path):
        records = list(parse_ops_txt(data_ops_path))
        assert len(records) > 100
        codes = {r["code"] for r in records}
        assert "1-100" in codes
        assert "1-204.0" in codes

    def test_all_have_labels(self, data_ops_path):
        records = list(parse_ops_txt(data_ops_path))
        for r in records:
            assert r["label"], f"Empty label for code {r['code']}"


class TestIngestOpsToDb:
    """Tests for ingest_ops_to_db (requires PostgreSQL)."""

    @pytest.fixture
    def db_conn(self, db_config):
        try:
            import psycopg2
            from ingest.schema import ensure_schema
            conn = psycopg2.connect(**db_config)
            ensure_schema(conn)
            return conn
        except Exception:
            pytest.skip("PostgreSQL not available")

    def test_ingest_creates_records(self, ops_sample_path, db_conn):
        try:
            count = ingest_ops_to_db(ops_sample_path, db_conn)
            assert count >= 8
        finally:
            db_conn.rollback()
            db_conn.close()


class TestOpsFixturePath:
    """Ensure fixture points to TXT file."""

    def test_ops_fixture_is_txt(self, ops_sample_path):
        assert ops_sample_path.suffix == ".txt"
        assert ops_sample_path.exists()
