"""Pytest fixtures for ingestion tests."""

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
