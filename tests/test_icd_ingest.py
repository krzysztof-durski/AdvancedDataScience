"""Tests for ICD-10-GM ingestion from pipe-delimited TXT."""

import tempfile
from pathlib import Path

import pytest

from ingest.icd_ingest import parse_icd_txt, ingest_icd_to_db
from ingest.common import get_version_year_from_filename


class TestParseIcdTxt:
    """Tests for parse_icd_txt."""

    def test_parses_sample_txt(self, icd_sample_path):
        records = list(parse_icd_txt(icd_sample_path))
        assert len(records) >= 5
        codes = {r["code"] for r in records}
        assert "A00" in codes
        assert "A00.0" in codes
        assert "A00.1" in codes
        assert "D27" in codes
        assert "U61.2!" in codes

    def test_skips_level_zero_rows(self, icd_sample_path):
        """Level 0 rows (index/cross-ref) should be skipped."""
        records = list(parse_icd_txt(icd_sample_path))
        # "Abnorm - s. Art der Krankheit" is level 0, should not appear
        labels = [r["label"] for r in records]
        assert "Abnorm - s. Art der Krankheit" not in labels

    def test_record_schema(self, icd_sample_path):
        records = list(parse_icd_txt(icd_sample_path))
        for r in records:
            assert "code" in r
            assert "label" in r
            assert "category3" in r
            assert "parent_code" in r
            assert "level" in r
            assert "version_year" in r
            assert "is_terminal" in r
            assert "code_type" in r

    def test_labels_extracted(self, icd_sample_path):
        records = {r["code"]: r for r in parse_icd_txt(icd_sample_path)}
        assert records["A00"]["label"] == "Cholera"
        assert "Cholera durch Vibrio" in records["A00.0"]["label"]
        assert "Benigne Neubildung" in records["D27"]["label"]

    def test_category3_extraction(self, icd_sample_path):
        records = {r["code"]: r for r in parse_icd_txt(icd_sample_path)}
        assert records["A00"]["category3"] == "A00"
        assert records["A00.0"]["category3"] == "A00"
        assert records["D27"]["category3"] == "D27"
        assert records["U61.2!"]["category3"] == "U61"

    def test_level_inference(self, icd_sample_path):
        records = {r["code"]: r for r in parse_icd_txt(icd_sample_path)}
        assert records["A00"]["level"] == 3
        assert records["A00.0"]["level"] in (4, 5)
        assert records["D27"]["level"] == 3

    def test_code_type_exclamation(self, icd_sample_path):
        records = {r["code"]: r for r in parse_icd_txt(icd_sample_path)}
        assert records["U61.2!"]["code_type"] == "exclamation"

    def test_version_year_from_filename(self, icd_sample_path):
        records = list(parse_icd_txt(icd_sample_path))
        assert all(r["version_year"] == 2025 for r in records)

    def test_version_year_explicit(self, icd_sample_path):
        records = list(parse_icd_txt(icd_sample_path, version_year=2024))
        assert all(r["version_year"] == 2024 for r in records)

    def test_version_year_from_path(self):
        with tempfile.NamedTemporaryFile(
            suffix="icd10gm2023syst.txt", delete=False, mode="w"
        ) as f:
            f.write("5|1|1|||A00||Cholera\n")
        try:
            records = list(parse_icd_txt(f.name))
            assert records[0]["version_year"] == 2023
        finally:
            Path(f.name).unlink()


class TestParseIcdFromDataFolder:
    """Tests against real DATA/ICD-diagnoses.txt."""

    @pytest.fixture
    def data_icd_path(self):
        p = Path(__file__).resolve().parent.parent / "DATA" / "ICD-diagnoses.txt"
        if not p.exists():
            pytest.skip("DATA/ICD-diagnoses.txt not found")
        return p

    def test_parses_real_file(self, data_icd_path):
        records = list(parse_icd_txt(data_icd_path))
        assert len(records) > 100
        codes = {r["code"] for r in records}
        assert "U61.2!" in codes or "B96.5!" in codes

    def test_all_have_labels(self, data_icd_path):
        records = list(parse_icd_txt(data_icd_path))
        for r in records:
            assert r["label"], f"Empty label for code {r['code']}"


class TestGetVersionYearFromFilename:
    """Tests for get_version_year_from_filename."""

    def test_extracts_2025(self):
        assert get_version_year_from_filename("icd10gm2025syst.txt") == 2025

    def test_extracts_2024(self):
        assert get_version_year_from_filename("/data/ops2024claml.txt") == 2024

    def test_returns_none_for_no_year(self):
        assert get_version_year_from_filename("icd.txt") is None


class TestIngestIcdToDb:
    """Tests for ingest_icd_to_db (requires PostgreSQL)."""

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

    def test_ingest_creates_records(self, icd_sample_path, db_conn):
        try:
            count = ingest_icd_to_db(icd_sample_path, db_conn)
            assert count >= 5
        finally:
            db_conn.rollback()
            db_conn.close()


class TestIcdFixturePath:
    """Ensure fixture points to TXT file."""

    def test_icd_fixture_is_txt(self, icd_sample_path):
        assert icd_sample_path.suffix == ".txt"
        assert icd_sample_path.exists()
