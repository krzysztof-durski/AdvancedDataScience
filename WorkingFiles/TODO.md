# TODO (ingestion + ingestion testing)

Rule: finished tasks must be marked with `✅`.

## 1) Schema decisions finalized
- ✅ Database target finalized: PostgreSQL (local Docker setup).
- ✅ Ingestion scope finalized: ICD + OPS + hospital location + department-level ICD/OPS counts.
- ✅ Create `icd_reference` with PK `(code, version_year)`.
- ✅ Create `ops_reference` with PK `(code, version_year)`.
- ✅ Create `hospital_locations` with PK `(ik, standortnummer, report_year)`.
- ✅ Create `hospital_departments` with surrogate `department_id` and unique `(ik, standortnummer, report_year, department_code)`.
- ✅ Create `hospital_department_diagnoses` with unique `(department_id, icd_code)`.
- ✅ Create `hospital_department_procedures` with unique `(department_id, ops_code)`.
- ✅ Create `ingest_files` checkpoint table with PK `file_path`.
- ✅ Add FK constraints from department tables to parent tables.
- ✅ Keep schema idempotent (safe repeated execution).

## 2) Column-level requiredness finalized
- ✅ No raw hospital JSON payload storage in v1; only required subset columns.
- ✅ `icd_reference` required columns: `code`, `version_year`, `description_de`, `row_type`, `source_file`, `ingested_at`.
- ✅ `ops_reference` required columns: `code`, `version_year`, `description_de`, `row_type`, `source_file`, `ingested_at`.
- ✅ `hospital_locations` required columns: `ik`, `standortnummer`, `report_year`, `hospital_name`, `source_file`, `ingested_at`.
- ✅ `hospital_locations` nullable columns: `street`, `house_number`, `postal_code`, `city`, `beds_count`, `inpatient_case_count`, `partial_inpatient_case_count`, `outpatient_case_count`.
- ✅ `hospital_departments` required columns: `department_id`, `ik`, `standortnummer`, `report_year`, `department_code`, `source_file`, `ingested_at`.
- ✅ `hospital_departments` nullable columns: `department_name`.
- ✅ `hospital_department_diagnoses` required columns: `department_id`, `icd_code`, `source_file`, `ingested_at`.
- ✅ `hospital_department_diagnoses` nullable column: `case_count` (privacy-masked values).
- ✅ `hospital_department_procedures` required columns: `department_id`, `ops_code`, `source_file`, `ingested_at`.
- ✅ `hospital_department_procedures` nullable column: `case_count` (privacy-masked values).
- ✅ `ingest_files` required columns: `file_path`, `file_size_bytes`, `file_mtime_ns`, `file_sha256`, `last_ingested_at`, `status`.
- ✅ `ingest_files` nullable column: `error_message`.

## 3) Ingestion behavior finalized
- ✅ Hospital source finalized: parse JSON from `DATA/json_output/json_YYYY/*.json`.
- ✅ ICD parser rule: include row types `1` and `5`; skip `0` synonyms.
- ✅ OPS parser rule: include row type `1`; skip `0` synonyms.
- ✅ Hospital parser rule: each file is one hospital location with one or more departments.
- ✅ Parse filename pattern: `{IK}-{Standort}-{Year}.json`; reject invalid pattern with explicit reason logging.
- ✅ Use batched upserts for all tables.
- ✅ Use `ON CONFLICT DO UPDATE` for idempotent reruns.
- ✅ Same key + same values: no meaningful data change.
- ✅ Same key + different values: incoming row wins and update timestamp/counters.
- ✅ Add retry behavior for failed batches (bounded retries + logged failures).
- ✅ Use `ingest_files` checkpoints for skip-on-unchanged behavior.
- ✅ Support reprocessing if file hash/mtime/size changes.

## 4) Ingestion tests finalized
- ✅ Test: load entries from a single file (ICD, OPS, hospital JSON).
- ✅ Test: load non-overlapping entries from two files.
- ✅ Test: load from a file containing a corrupted row/JSON record.
- ✅ Test: load from a file containing duplicate records.
- ✅ Test: load two overlapping files (same keys).
- ✅ Test: load same file twice (idempotency).
- ✅ Test: same keys with different values -> update behavior verified.
- ✅ Test: second file superset of first -> only delta updates.
- ✅ Assert row counts per table after each test.
- ✅ Assert inserted/updated/skipped/errors counters.
- ✅ Assert uniqueness constraints remain intact.
- ✅ Assert nullable `case_count` handling for privacy-masked values.
- ✅ Assert `ingest_files` checkpoint behavior (new vs unchanged vs changed files).

## 5) Execution order (implementation checklist)
- ✅ Implement schema migration SQL for all 7 ingestion tables.
- ✅ Implement ICD ingestion module and normalization.
- ✅ Implement OPS ingestion module and normalization.
- ✅ Implement hospital location + department + diagnosis/procedure ingestion modules.
- ✅ Implement checkpoint and batch retry utilities.
- ✅ Implement orchestration CLI (`run_ingest.py`) with counters and summary output.
- ✅ Implement pytest fixtures for isolated empty DB per test.
- ✅ Implement ingestion test suite for all baseline scenarios.
- ✅ Run test suite and fix failures until green.
- ✅ Update README ingestion commands only after tests pass.

