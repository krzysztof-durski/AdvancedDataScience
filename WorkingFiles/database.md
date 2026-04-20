# PostgreSQL with Docker — Quick Reference

## Essential Commands

| Action | Command |
|--------|---------|
| **Start** | `docker compose up -d` |
| **Stop** | `docker compose down` |
| **Stop + remove volumes** | `docker compose down -v` |
| **View logs** | `docker compose logs -f postgres` |
| **Check status** | `docker compose ps` |
| **Connect (psql)** | `docker compose exec postgres psql -U postgres -d hospital_db` |
| **Connect (from host)** | `psql -h localhost -p 5432 -U postgres -d hospital_db` |
| **Full reset** | `docker compose down -v && docker compose up -d` |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)

---

## Setup

### 1. `docker-compose.yml` (project root)

File exists. Postgres 18 Alpine, port 5432, database `hospital_db`. Edit if you need different settings.

### 2. Add credentials to `.env`

```env
POSTGRES_PASSWORD=your_secure_password
POSTGRES_USER=postgres
POSTGRES_DB=hospital_db
```

> Add `.env` to `.gitignore` if not already (never commit passwords).

### 3. Start the database

```bash
docker compose up -d
```

### 4. Verify it's running

```bash
docker compose ps
# or
docker compose exec postgres psql -U postgres -c "\l"
```

---

## Connection Details

| Setting | Value |
|---------|-------|
| Host | `localhost` |
| Port | `5432` |
| Database | `hospital_db` |
| User | `postgres` |
| Password | From `.env` |

**Python (psycopg2):**
```python
import os
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="hospital_db",
    user="postgres",
    password=os.environ.get("POSTGRES_PASSWORD", "postgres")
)
```

**Connection string:**
```
postgresql://postgres:YOUR_PASSWORD@localhost:5432/hospital_db
```

---

## Common Operations

### Reset database (drop all data, keep container)

```bash
docker compose exec postgres psql -U postgres -c "DROP DATABASE hospital_db;"
docker compose exec postgres psql -U postgres -c "CREATE DATABASE hospital_db;"
```

### Full reset (remove container and data)

```bash
docker compose down -v
docker compose up -d
```

### Backup database

```bash
docker compose exec postgres pg_dump -U postgres hospital_db > backup_$(date +%Y%m%d).sql
```

### Restore from backup

```bash
docker compose exec -T postgres psql -U postgres hospital_db < backup_20250304.sql
```

### List tables

```bash
docker compose exec postgres psql -U postgres -d hospital_db -c "\dt"
```
