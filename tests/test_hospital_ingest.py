"""Tests for hospital/location JSON ingestion."""

from pathlib import Path

import pytest

from ingest.hospital_ingest import ingest_hospital_json_files, parse_hospital_json


class TestHospitalParser:
    def test_parse_filename_and_fields(self, hospital_sample_path):
        record = parse_hospital_json(hospital_sample_path)
        assert record["ik"] == "260100023"
        assert record["standortnummer"] == "773287000"
        assert record["report_year"] == 2024
        assert record["hospital_name"] == "Example Klinik"


class TestHospitalIngest:
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

    def test_upsert_by_composite_key(self, hospital_sample_path, tmp_path, db_conn):
        first = ingest_hospital_json_files([hospital_sample_path], db_conn)
        assert first.inserted == 1

        updated = tmp_path / "260100023-773287000-2024.json"
        updated.write_text(
            '{"Qualitaetsbericht":{"Krankenhaus":{"Mehrere_Standorte":{"Krankenhauskontaktdaten":{"Name":"Updated Klinik","Kontakt_Adresse":{"Ort":"Hamburg","Postleitzahl":"20095"}}}}}}',
            encoding="utf-8",
        )
        second = ingest_hospital_json_files([updated], db_conn)
        assert second.updated == 1
