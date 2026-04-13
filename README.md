# AdvancedDataScience

Hospital data ingestion project for German ICD-10-GM diagnoses and OPS procedures.
The current runnable path is Docker Postgres + Python ingestion scripts.

## Quick Start

```bash
# 1) Start PostgreSQL
docker compose up -d

# 2) Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3) Ensure input files exist
ls DATA/ICD-diagnoses.txt DATA/OPS-procedures.txt

# 4) Run ingestion
python ingest/run_ingest.py

# 5) Run tests
pytest
```

If ingestion succeeds, you should see output like:
- `Ingesting ICD...`
- `ICD: <n> rows`
- `Ingesting OPS...`
- `OPS: <n> rows`
- `Done.`

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

These values are used by both:
- Python ingestion (`ingest/common.py`)
- Node Sequelize config (`src/config/database.js`)

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

`ingest/run_ingest.py` expects these exact files:

- `DATA/ICD-diagnoses.txt`
- `DATA/OPS-procedures.txt`

If either file is missing, the script exits with a clear error message.

## Run Ingestion

```bash
python ingest/run_ingest.py
```

What it does:
- Connects to Postgres using env vars/defaults.
- Parses ICD and OPS text files.
- Upserts rows into `icd` and `ops` tables.
- Commits after ICD and OPS phases.

## Verify Data Loaded

Use psql from the running container:

```bash
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS icd_rows FROM icd;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT COUNT(*) AS ops_rows FROM ops;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT version_year, COUNT(*) FROM icd GROUP BY version_year ORDER BY version_year;"
docker compose exec -T postgres psql -U postgres -d hospital_db -c "SELECT version_year, COUNT(*) FROM ops GROUP BY version_year ORDER BY version_year;"
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
```

## Node / Sequelize Status

Current Node-side pieces available:
- DB config: `src/config/database.js`
- Models: `src/models/Icd.js`, `src/models/Ops.js`, `src/models/index.js`
- Package scripts:
  - `npm run db:migrate` -> `node src/scripts/migrate.js`
  - `npm run db:seed` -> `node src/scripts/seed.js`

Important: `src/scripts/migrate.js` and `src/scripts/seed.js` are not present yet.
So `db:migrate` / `db:seed` commands are placeholders until those scripts are added.

## Troubleshooting

- `Database connection failed` during ingestion:
  - Ensure Postgres is up: `docker compose ps`
  - Check env values in `.env` match container settings.
  - Verify port `5432` is not occupied by another local Postgres.

- `ICD file not found` or `OPS file not found`:
  - Place files at exactly `DATA/ICD-diagnoses.txt` and `DATA/OPS-procedures.txt`.

- `relation "icd" does not exist` or `relation "ops" does not exist`:
  - Re-run ingestion; schema creation is handled in ingestion flow.
  - If database state is corrupted, reset: `docker compose down -v && docker compose up -d`.

- Python package import errors:
  - Activate virtualenv before running commands.
  - Reinstall dependencies: `pip install -r requirements.txt`.

- Container start issues:
  - Check logs: `docker compose logs postgres`
  - If needed, clear old volume/state: `docker compose down -v`.

## Command Reference

See `COMMANDS.md` for a compact command catalog.
