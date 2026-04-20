from ingest.common import get_connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS icd_reference (
  code TEXT NOT NULL,
  version_year INTEGER NOT NULL,
  description_de TEXT NOT NULL,
  row_type SMALLINT NOT NULL,
  source_file TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (code, version_year)
);

CREATE TABLE IF NOT EXISTS ops_reference (
  code TEXT NOT NULL,
  version_year INTEGER NOT NULL,
  description_de TEXT NOT NULL,
  row_type SMALLINT NOT NULL,
  source_file TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (code, version_year)
);

CREATE TABLE IF NOT EXISTS hospital_locations (
  ik TEXT NOT NULL,
  standortnummer TEXT NOT NULL,
  report_year INTEGER NOT NULL,
  hospital_name TEXT NOT NULL,
  street TEXT,
  house_number TEXT,
  postal_code TEXT,
  city TEXT,
  beds_count INTEGER,
  inpatient_case_count INTEGER,
  partial_inpatient_case_count INTEGER,
  outpatient_case_count INTEGER,
  source_file TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (ik, standortnummer, report_year)
);

CREATE TABLE IF NOT EXISTS hospital_departments (
  department_id BIGSERIAL PRIMARY KEY,
  ik TEXT NOT NULL,
  standortnummer TEXT NOT NULL,
  report_year INTEGER NOT NULL,
  department_code TEXT NOT NULL,
  department_name TEXT,
  source_file TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (ik, standortnummer, report_year, department_code),
  FOREIGN KEY (ik, standortnummer, report_year)
    REFERENCES hospital_locations (ik, standortnummer, report_year)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hospital_department_diagnoses (
  department_id BIGINT NOT NULL,
  icd_code TEXT NOT NULL,
  case_count INTEGER,
  source_file TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (department_id, icd_code),
  FOREIGN KEY (department_id)
    REFERENCES hospital_departments (department_id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hospital_department_procedures (
  department_id BIGINT NOT NULL,
  ops_code TEXT NOT NULL,
  case_count INTEGER,
  source_file TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (department_id, ops_code),
  FOREIGN KEY (department_id)
    REFERENCES hospital_departments (department_id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ingest_files (
  file_path TEXT PRIMARY KEY,
  file_size_bytes BIGINT NOT NULL,
  file_mtime_ns BIGINT NOT NULL,
  file_sha256 TEXT NOT NULL,
  last_ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT NOT NULL,
  error_message TEXT
);
"""


def ensure_schema(conn=None) -> None:
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()

