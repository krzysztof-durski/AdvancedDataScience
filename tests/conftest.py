"""Pytest fixtures for ingestion tests."""

import json
from pathlib import Path

import pytest

# Ensure we can import from project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def icd_sample_path():
    """Path to sample ICD pipe-delimited TXT."""
    return FIXTURES_DIR / "icd_sample.txt"


@pytest.fixture
def ops_sample_path():
    """Path to sample OPS pipe-delimited TXT."""
    return FIXTURES_DIR / "ops_sample.txt"


@pytest.fixture
def db_config():
    """Database config from env (for integration tests)."""
    from ingest.common import DB_CONFIG
    return DB_CONFIG


@pytest.fixture
def hospital_sample_path(tmp_path):
    payload = {
        "Qualitaetsbericht": {
            "Krankenhaus": {
                "Mehrere_Standorte": {
                    "Krankenhauskontaktdaten": {
                        "Name": "Example Klinik",
                        "Kontakt_Adresse": {"Ort": "Berlin", "Postleitzahl": "10115"},
                    }
                }
            }
        }
    }
    p = tmp_path / "260100023-773287000-2024.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p
