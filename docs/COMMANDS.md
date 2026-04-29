# Project Commands

Quick reference for commands used in this project. For full context, see the root `README.md`.

---

## Quick Start (Run in Order)

Use these commands in sequence to start PostgreSQL in Docker and ingest data.

1. Start database container: `docker compose up -d`
2. Create and activate venv: `python -m venv .venv` then `source .venv/bin/activate` (macOS/Linux)
3. Install Python dependencies: `pip install -r requirements.txt`
4. Confirm required data files exist: `ls DATA/ICD-diagnoses.txt DATA/OPS-procedures.txt`
5. Run full ingest: `python -m ingest.run_ingest --batch-size 1000`
6. (Optional) Run tests: `pytest`

---

## Docker (PostgreSQL)

| Label | Command |
|-------|---------|
| **Start database** | `docker compose up -d` |
| **Stop database** | `docker compose down` |
| **View logs** | `docker compose logs -f postgres` |
| **Stop and remove volumes / reset DB (destructive)** | `docker compose down -v` |
| **Check container status** | `docker compose ps` |

Default connection: `localhost:5432`, user `postgres`, database `hospital_db`.

Password: defaults to `postgres`; override for the container with env `POSTGRES_PASSWORD` (see `docker-compose.yml`). Python ingestion uses `DB_PASSWORD` (default `postgres`) — keep these aligned with `.env` if you change one.

If Postgres 18 reports an upgrade/mount-layout error and keeps restarting, run `docker compose down -v` and then `docker compose up -d` to reinitialize the database volume.

---

## Python Setup

| Label | Command |
|-------|---------|
| **Create virtual env** (recommended) | `python -m venv .venv` then `source .venv/bin/activate` (macOS/Linux) |
| **Install dependencies** | `pip install -r requirements.txt` |

---

## Tests

| Label | Command |
|-------|---------|
| **Run all tests** | `pytest` |
| **Quiet** | `pytest -q` |
| **Verbose** | `pytest -v` |
| **Integration / ingest tests** | `pytest tests/test_icd_ingest.py` · `pytest tests/test_ops_ingest.py` · `pytest tests/test_hospital_ingest.py` · `pytest tests/test_tracking.py` |
| **Unit tests** | `pytest tests/test_parsers_unit.py` · `pytest tests/test_common_unit.py` |
| **Single test** | `pytest tests/test_icd_ingest.py::test_name` |

---

## Populate / Ingest Data

| Label | Command |
|-------|---------|
| **Full ingest (ICD → OPS → hospital JSON)** | `python -m ingest.run_ingest --batch-size 1000` |
| **CLI help** | `python -m ingest.run_ingest --help` |
| **Equivalent script path** | `python ingest/run_ingest.py` (same entrypoint; prefer `-m` from repo root) |

Requires:

- PostgreSQL running (e.g. via Docker).
- `DATA/ICD-diagnoses.txt` and `DATA/OPS-procedures.txt`.
- Hospital reports as `DATA/**/*.json` with filenames like `ik-standortnummer-year.json` (nested dirs such as `DATA/json_2023/` are scanned recursively).

Schema is created during ingestion (`ensure_schema`); you do not need a separate migrate step for the Python workflow.

Env vars (optional, defaults shown): `DB_HOST=localhost`, `DB_PORT=5432`, `DB_NAME=hospital_db`, `DB_USER=postgres`, `DB_PASSWORD=postgres`.

Useful flags (see `--help` for all): `--dry-run`, `--include-years`, `--exclude-years`, `--no-track-files`, `--strict`, `--failed-log PATH`, `--icd-path`, `--ops-path`, `--hospital-dir`, `--icd-version-year`, `--ops-version-year`. (`--continue-on-error` is kept as a deprecated no-op since skipping is now the default.)

---

## Geocache Maintenance (Offline Maps)

| Label | Command |
|-------|---------|
| **Check missing postal codes** | `python dashboard/sync_geocache.py` |
| **Append missing postal codes to cache** | `python dashboard/sync_geocache.py --write` |

`dashboard/geocache.csv` is the committed map coordinate source used by the dashboard.  
If `GEOAPIFY_API_KEY` is set, `--write` attempts to auto-fill missing `lat/lon` via Geoapify for both new and already-cached postal codes with empty coordinates.  
Without API key, it adds postal codes with empty `lat/lon` for later enrichment.

---

## Verify data (psql in container)

| Label | Command |
|-------|---------|
| **Row counts (examples)** | `docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) FROM icd_reference;"` |
| **More examples** | Same pattern for `ops_reference`, `hospital_locations`, `hospital_departments`, etc. (see `README.md` → Verify Data Loaded) |

---

## Node.js / Database Scripts

| Label | Command |
|-------|---------|
| **Install Node deps** | `npm install` |
| **Run migrations** | `npm run db:migrate` → `node src/scripts/migrate.js` |
| **Run seed** | `npm run db:seed` → `node src/scripts/seed.js` |

The `src/` directory (and those script files) are **not** in this repository yet; `package.json` declares the scripts, but they will error until you add them. Optional tooling only — not required for Python ingestion above.

---

## Typical workflow

1. Start Postgres: `docker compose up -d`
2. Create venv, activate, then `pip install -r requirements.txt`
3. Confirm data files: `ls DATA/ICD-diagnoses.txt DATA/OPS-procedures.txt` and hospital JSON under `DATA/`
4. Run ingest: `python -m ingest.run_ingest --batch-size 1000`
5. Run tests: `pytest`

Optional: `npm install` and `npm run db:migrate` / `db:seed` only if you add the Sequelize scripts under `src/scripts/`.
