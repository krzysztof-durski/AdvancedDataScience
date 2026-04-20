import os
import uuid
from pathlib import Path

import psycopg2
import pytest

from ingest.common import get_connection
from ingest.schema import ensure_schema


@pytest.fixture(scope="session")
def db_available():
    try:
        conn = get_connection()
        conn.close()
        return True
    except psycopg2.Error:
        return False


@pytest.fixture()
def db_conn(db_available):
    if not db_available:
        pytest.skip("PostgreSQL is not available for integration tests")
    conn = get_connection()
    ensure_schema(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
              hospital_department_procedures,
              hospital_department_diagnoses,
              hospital_departments,
              hospital_locations,
              icd_reference,
              ops_reference,
              ingest_files
            RESTART IDENTITY CASCADE
            """
        )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def tmp_data_dir(tmp_path: Path):
    root = tmp_path / f"data-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(autouse=True)
def env_defaults(monkeypatch):
    monkeypatch.setenv("DB_HOST", os.getenv("DB_HOST", "localhost"))
    monkeypatch.setenv("DB_PORT", os.getenv("DB_PORT", "5432"))
    monkeypatch.setenv("DB_NAME", os.getenv("DB_NAME", "hospital_db"))
    monkeypatch.setenv("DB_USER", os.getenv("DB_USER", "postgres"))
    monkeypatch.setenv("DB_PASSWORD", os.getenv("DB_PASSWORD", "postgres"))

