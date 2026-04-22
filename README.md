# AdvancedDataScience

Hospital data ingestion project for German ICD-10-GM diagnoses, OPS procedures, and hospital location reports.
The runnable path is Docker Postgres + Python ingestion scripts.

## Quick Start

```bash
# 1) Start PostgreSQL
docker compose up -d

# 2) Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3) Ensure input files exist
ls DATA/ICD-diagnoses.txt DATA/OPS-procedures.txt DATA

# 4) Run ingestion
python -m ingest.run_ingest --batch-size 1000

# 5) Run tests
pytest
```

If ingestion succeeds, you should see output lines like:
- `ICD: read=... accepted=... skipped=... inserted=... updated=... errors=...`
- `OPS: read=... accepted=... skipped=... inserted=... updated=... errors=...`
- `HOSPITAL: read=... accepted=... skipped=... inserted=... updated=... errors=...`
- `TOTAL: read=... accepted=... skipped=... inserted=... updated=... errors=...`

## Prerequisites

- Docker + Docker Compose
- Python 3.11+ and `pip`
- Optional: Node.js 20+ and `npm` (for Sequelize model-side tooling)

## Environment Configuration

Create or verify `.env` in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hospital_db
DB_USER=postgres
DB_PASSWORD=postgres
```

These values are used by Python ingestion (`ingest/common.py`).

## Database (Docker)

Postgres is defined in `docker-compose.yml` and exposed on `localhost:5432`.

```bash
# Start
docker compose up -d

# Check logs
docker compose logs -f postgres

# Stop
docker compose down

# Stop and delete data volume
docker compose down -v
```

## Python Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Dependencies include parser/DB/testing packages such as `lxml`, `psycopg2-binary`, and `pytest`.

## Data Files Required for Ingestion

`ingest.run_ingest` expects these exact files:

- `DATA/ICD-diagnoses.txt`
- `DATA/OPS-procedures.txt`
- `DATA/**/*.json` with filename format `ik-standortnummer-year.json`

If either file is missing, the script exits with a clear error message.

Current repository layout stores hospital JSON under year folders (for example `DATA/json_2023/` and `DATA/json_2024/`). The runner scans recursively under `--hospital-dir`.

## Run Ingestion

```bash
python -m ingest.run_ingest \
  --icd-path DATA/ICD-diagnoses.txt \
  --ops-path DATA/OPS-procedures.txt \
  --hospital-dir DATA \
  --icd-version-year 2025 \
  --ops-version-year 2025 \
  --batch-size 1000
```

What it does:
- Connects to Postgres using env vars/defaults.
- Runs phases in deterministic order: ICD -> OPS -> hospital.
- Upserts rows into `icd_reference`, `ops_reference`, and `hospital_locations`.
- Upserts department-level metrics into `hospital_departments`, `hospital_department_diagnoses`, and `hospital_department_procedures`.
- Tracks processed files in `ingest_files` using `mtime_ns`, `size_bytes`, and `sha256`.
- Prints per-phase and final summary counters.

Optional flags:

```bash
# Parse and validate without persisting
python -m ingest.run_ingest --dry-run

# Process only selected hospital years
python -m ingest.run_ingest --include-years 2023,2024

# Exclude selected hospital years
python -m ingest.run_ingest --exclude-years 2008,2010

# Disable processed-file tracking
python -m ingest.run_ingest --no-track-files

# Override inferred ICD/OPS version year (recommended when filename has no year)
python -m ingest.run_ingest --icd-version-year 2025 --ops-version-year 2025

# Default skips unparsable hospital JSON files and records them in `ingest_files`
# (status='failed'); logs each failure to stderr. Use --strict to fail fast instead.
python -m ingest.run_ingest --strict

# Also write the list of failed files to a plain-text log
python -m ingest.run_ingest --failed-log failed_hospital.log
```

## Verify Data Loaded

Use psql from the running container:

```bash
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS icd_rows FROM icd_reference;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS ops_rows FROM ops_reference;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS hospital_rows FROM hospital_locations;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS department_rows FROM hospital_departments;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS diagnosis_rows FROM hospital_department_diagnoses;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS procedure_rows FROM hospital_department_procedures;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT version_year, COUNT(*) FROM icd_reference GROUP BY version_year ORDER BY version_year;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT version_year, COUNT(*) FROM ops_reference GROUP BY version_year ORDER BY version_year;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT report_year, COUNT(*) FROM hospital_locations GROUP BY report_year ORDER BY report_year;"
```

## Testing

```bash
# Run all tests
pytest

# Verbose
pytest -v

# Specific file
pytest tests/test_icd_ingest.py
pytest tests/test_ops_ingest.py
pytest tests/test_hospital_ingest.py
```

## Node / Sequelize Status

Current Node-side pieces available:
- Package scripts:
  - `npm run db:migrate` -> `node src/scripts/migrate.js`
  - `npm run db:seed` -> `node src/scripts/seed.js`

Current status:
- The `src/` folder is currently not present in this repository checkout.
- Node scripts are declared in `package.json` but will fail until matching files are added.

## Troubleshooting

- `Database connection failed` during ingestion:
  - Ensure Postgres is up: `docker compose ps`
  - Check env values in `.env` match container settings.
  - Verify port `5432` is not occupied by another local Postgres.

- `ICD file not found` or `OPS file not found`:
  - Place files at exactly `DATA/ICD-diagnoses.txt` and `DATA/OPS-procedures.txt`.

- `relation "icd" does not exist`, `relation "ops" does not exist`, or `relation "hospital_locations" does not exist`:
  - Re-run ingestion; schema creation is handled in ingestion flow.
  - If database state is corrupted, reset: `docker compose down -v && docker compose up -d`.

- Hospital files are unexpectedly skipped:
  - Ensure JSON filenames follow `ik-standortnummer-year.json`.
  - Use `--hospital-dir DATA` for nested layouts like `DATA/json_2023` and `DATA/json_2024`.
  - Remove tracking entries for a clean rerun:
    `docker compose exec -T postgres psql -U postgres -d hospital_db -c "TRUNCATE ingest_files;"`
  - Or run once with `--no-track-files`.

- Python package import errors:
  - Activate virtualenv before running commands.
  - Reinstall dependencies: `pip install -r requirements.txt`.

- Container start issues:
  - Check logs: `docker compose logs postgres`
  - If needed, clear old volume/state: `docker compose down -v`.

## Design Notes

See `docs/ingestion_strategy.md` for deterministic-key strategy, duplicate policy, and rerun tracking details.

## Reproducibility Checklist (Exam)

1. Start clean DB: `docker compose down -v && docker compose up -d`
2. Run ingest: `python -m ingest.run_ingest --batch-size 1000`
3. Re-run ingest to validate deterministic behavior:
   `python -m ingest.run_ingest --batch-size 1000`
4. Verify no unintended duplicate growth in key tables:
   - `icd_reference` uniqueness by `(code, version_year)`
   - `ops_reference` uniqueness by `(code, version_year)`
   - `hospital_locations` uniqueness by `(ik, standortnummer, report_year)`
5. Execute tests:
   `pytest -q`

## Pipeline assumptions (optional constraints)

The list below is a **generic scenario** (large volume, flaky writes, changing schema, GDPR, etc.). **This project does not claim** that every item applies to the current deployment (for example, redundant storage with eventual consistency is an external circumstance, not something the ingestion code models).

| Assumption | What this repo does today | If it became a real requirement |
|------------|---------------------------|--------------------------------|
| Very large row counts (e.g. 1B+) | Single-process batched upserts; ICD/OPS parse into memory before write. | Stream parsing, smaller commits, partitioning/sharding or distributed ingest, capacity planning for Postgres. |
| Large per-entry annotations (e.g. ~1MB) later | Core tables are fixed columns; no extension store. | Add a **reference / extension table** (FK to stable entity key, optional `JSONB` or blob **pointer** to object storage for huge payloads); keep hot path tables narrow. |
| Incremental updates | Hospital JSON: skip unchanged files via `ingest_files` fingerprints; upserts are idempotent. ICD/OPS: full file pass each run. | Add file-level tracking for ICD/OPS, or change feeds, if sources are huge. |
| Full reload | Rebuild truth from **all** sources: truncate or delete target tables, clear `ingest_files` (or `--no-track-files`). Empty `hospital_locations` forces re-read of JSON when tracking is on. | Document runbook + optional CLI flag; consider separate “staging then swap” for zero-downtime. |
| Unpredictable write failures | Retries + savepoints on batched `execute_values`; hospital parse errors default to skip+record in `ingest_files` and stderr log, `--strict` restores fail-fast. | Smaller transactions, dead-letter queue for bad rows/batches, replay from durable log. |
| Evolving data model | `CREATE TABLE IF NOT EXISTS` only in `ensure_schema`. | Migrations (e.g. Alembic/Flyway), additive columns, backward-compatible ingest. |
| Redundant storage / eventual consistency | Single Postgres connection. | Idempotent keys, outbox pattern, explicit sync jobs; not handled inside this script. |
| Retroactive deletion (GDPR) | Hard delete is possible in SQL; child rows cascade from `hospital_locations`. | Document **subject/entity → DELETE** procedure; extend tables if annotations hold PII; cover replicas and backups. |
| Tight timeline | Batching, progress bars, skip unchanged hospital files speed re-runs. | Prioritize incremental path and runbook over premature scale engineering. |

## Some questions to consider

**1. To ingest all data, do you run one script or several separate scripts?**  
**One script:** `python -m ingest.run_ingest` is the only ingestion entrypoint; a single invocation runs ICD, then OPS, then every eligible hospital JSON file under `--hospital-dir`, so you do not split the workload across multiple top-level ingest programs in this repository.

- You may still **re-run** that same command whenever inputs change (idempotent upserts and optional `ingest_files` skipping); that is repeat use of one program, not a requirement to coordinate several different executables to obtain a full load.

**2. What should happen when an error occurs?**  
ICD/OPS skip unusable lines, batched upserts retry transient database errors with savepoints, and a hospital JSON failure increments `errors`, is logged to stderr and (when tracking is on) recorded in `ingest_files` with `status='failed'`, and ingestion continues by default; pass `--strict` to abort on the first bad file. Any other uncaught exception still stops the process immediately.

**3. What should happen when someone runs the ingestion again?**  
Re-running is idempotent via upserts on stable keys, skips unchanged tracked hospital JSON when fingerprints match, and reprocesses JSON when `hospital_locations` is empty so stale `ingest_files` metadata cannot hide a truncated hospital load.

**4. What configuration options should the program have?**  
Postgres is configured via `DB_*` environment variables, and ingestion is tuned with `ingest.run_ingest` CLI flags for input paths, ICD/OPS version years, hospital year filters, batch size, hospital flush cadence, dry-run, file tracking, strict failure mode, failed-file log, and progress output.

## Ingestion pipeline design decisions

### Database

- PostgreSQL (Docker Compose) is the system of record.
- Table roles:
  - Reference: `icd_reference`, `ops_reference`.
  - Hospital domain: locations, departments, department diagnoses/procedures.
  - Ops metadata: `ingest_files` (fingerprints, status).
- Schema:
  - Applied at ingest time via `ensure_schema` (`CREATE TABLE IF NOT EXISTS`).
  - Trades separate migration tooling for a minimal “clone and run” setup.
- Keys and writes:
  - Composite keys: ICD/OPS `(code, version_year)`; hospital `(ik, standortnummer, report_year)`.
  - Idempotent loads: batched `INSERT ... ON CONFLICT DO UPDATE` instead of ad hoc dedupe.
- Referential integrity:
  - Department ICD/OPS codes are mainly a logical join to reference tables (no enforced FK on those columns).

### Ingestion strategy

- Shape of the run:
  - Single CLI: `python -m ingest.run_ingest`.
  - Phase order: ICD → OPS → hospital JSON (scan recursive under `--hospital-dir`).
- Database I/O and resilience:
  - Bulk inserts via `execute_values` with `--batch-size`.
  - Transient errors: retries with savepoints (`ingest/common.py`).
  - Hospital path: periodic flush/commit every `--hospital-flush-files` files to cap memory and save partial work.
- What gets skipped vs reprocessed:
  - Hospital JSON: may skip unchanged files when tracking compares `mtime_ns`, `size_bytes`, `sha256` in `ingest_files`.
  - ICD/OPS: full parse + upsert each run (no first-class fingerprint skip in-repo).
- Conflict and rerun policy:
  - Same key, new payload: latest ingest wins (`ON CONFLICT DO UPDATE`).
  - See `docs/ingestion_strategy.md` for deterministic-key notes.
- Operator modes:
  - `--dry-run`: parse/validate without writing.
  - Hospital phase skips + records unparsable JSON files by default; `--strict` restores fail-fast.
  - `--failed-log PATH` writes a tab-separated list of failed files for quick triage.
  - ICD/OPS: bad lines usually bump counters; hard failures still abort.
- Feedback:
  - Per-phase counters on stdout.
  - Optional `tqdm` bars (`--no-progress` to disable).

### Language and stack

- Runtime: Python 3.11+.
- Main libraries:
  - `psycopg2-binary` for Postgres access.
  - `lxml` for markup-heavy sources where needed.
  - Code organized as small modules under `ingest/`.
- Why Python here:
  - Fast iteration for a batch job.
  - Strong text / JSON ergonomics.
  - No compile step for contributors running ingest locally.

### If data were ~100× or ~1000× larger

- Current baseline:
  - Single process, single DB connection.
  - ICD/OPS parsers hold full row lists in memory before write (scales poorly past “catalog” sizes).
- Likely next steps:
  - Stream parsers and smaller transactions.
  - Parallel workers partitioned by file or report year.
  - File-level incremental tracking for ICD/OPS, not only hospitals.
  - Postgres: indexes, partitioning (e.g. by year), `COPY` or staging-then-swap instead of long upsert windows.
- Related doc: the “Pipeline assumptions” table earlier in this README states the same themes in table form.

### Tests

- Runner: `pytest`.
- Coverage areas:
  - ICD/OPS/hospital parsers and ingest paths.
  - Reference scenarios (duplicates, non-overlap, validation).
- Test modules:
  - `tests/test_icd_ingest.py`
  - `tests/test_ops_ingest.py`
  - `tests/test_hospital_ingest.py`
  - `tests/test_reference_ingest_scenarios.py`
- Data:
  - Fixtures under `tests/fixtures/` for small, repeatable inputs without full production dumps.
