# Data Ingestion: What It Is and How to Build a Pipeline

A conceptual guide for the Hospital Maps Data Pipeline project.

---

## 1. What Is Ingestion?

**Data ingestion** is the process of moving data from source systems (files, APIs, streams) into a target storage system—typically a database or data warehouse—where it can be queried, analyzed, and used by applications.

In plain terms: you have data sitting in files (JSON, TXT, CSV, etc.), and you want it inside a database so you can run queries, build dashboards, and answer research questions. Ingestion is the bridge between "raw data on disk" and "structured data in a database."

### Why Not Just Read Files Directly?

- **Performance:** Databases are optimized for filtering, aggregating, and joining. Scanning thousands of files every time you need a statistic is slow.
- **Consistency:** A database enforces schema, constraints, and relationships. Files can be inconsistent or malformed.
- **Scalability:** As data grows (e.g. 1B+ entries), in-memory processing breaks down. Databases handle large datasets with indexing and query optimization.
- **Reusability:** Once ingested, many tools (dashboards, APIs, analysts) can use the same data without re-parsing files.

### In Your Project Context

Your pipeline flow is:

```
Raw XML → JSON conversion → Ingestion into database → Dashboard
```

Ingestion is the step that takes:
- `DATA/diagnoses.txt` (ICD codes)
- `DATA/Procedures.txt` (OPS codes)
- `DATA/json_output/json_YYYY/*.json` (hospital quality reports)

…and loads them into PostgreSQL (or DuckDB/MongoDB) so your dashboard can answer questions like "Where are the most cardiac surgeries?" or "Which area has the most hospitals per population?"

---

## 2. Core Concepts of an Ingestion Pipeline

### 2.1 Extract → Transform → Load (ETL)

Ingestion pipelines often follow an ETL pattern:

| Phase | What Happens |
|-------|--------------|
| **Extract** | Read data from sources (files, APIs). Parse formats (JSON, pipe-delimited, etc.). |
| **Transform** | Clean, filter, normalize. Map column names, filter out synonyms (e.g. ICD type 0), flatten nested structures. |
| **Load** | Write transformed records into the database. Handle duplicates, conflicts, and errors. |

In your case:
- **Extract:** Read `.json` files and `.txt` files.
- **Transform:** Filter ICD rows (keep type 1/5, skip 0), extract hospital fields from nested JSON, normalize addresses.
- **Load:** Insert into `hospitals`, `diagnoses`, `procedures` tables (or equivalent).

### 2.2 Idempotency

**Idempotency** means: running the pipeline multiple times with the same input produces the same result. If you ingest the same file twice, you should not end up with duplicate rows.

This is critical because:
- Pipelines fail mid-run (network, disk, timeout).
- You need to re-run after fixing a bug.
- Incremental updates may re-process some files.

Your ingestion strategy must define: *What happens when we see an entry we've already loaded?* (Update? Skip? Fail?)

### 2.3 Error Handling and Resilience

Real-world assumptions (from your course materials):

- Writing any entry might fail in a non-predictable way.
- Data is stored with eventual consistency (e.g. distributed systems).
- The client is in a hurry—you can't assume perfect conditions.

So the pipeline must:
- Handle corrupt entries (skip or log, don't crash the whole run).
- Retry failed writes.
- Support partial progress (checkpoints) so you don't restart from zero.

---

## 3. Ingestion Strategies

A naive approach—"read file, write each row to DB"—fails at scale and under real-world conditions. Here are alternative strategies.

### Strategy A: Check Before Writing

Before inserting, query the database: "Does this entry already exist?" If yes, skip or update. If no, insert.

- **Pros:** Simple logic, no duplicates.
- **Cons:** One extra query per row → very slow at scale (1B rows = 1B extra queries). Race conditions if multiple processes run.

### Strategy B: Hash-Based Unique Identification

Compute a hash (e.g. SHA-256) of the record's key fields. Use the hash as a unique identifier. On insert, use "upsert" (INSERT ... ON CONFLICT) so duplicates overwrite or are ignored.

- **Pros:** No pre-check query. Deterministic: same data → same hash. Works well with batched upserts.
- **Cons:** Hash collisions (rare). Need to define which fields form the "identity" of a record.

### Strategy C: Checkpoints + Metadata of Processed Entries

Maintain a log or table of processed files/entries: "File X, rows 1–1000, processed at timestamp T." On re-run, skip already-processed chunks. Resume from the last checkpoint on failure.

- **Pros:** Resilient to crashes. Can resume without re-reading everything.
- **Cons:** Checkpoint management adds complexity. Need to handle "same file, different content" (e.g. file was updated).

### Strategy D: Batched Processing with Retry for Failed Batches

Process in batches (e.g. 1000 rows). Insert batch. If batch fails, retry that batch (with backoff). Log failed batches for manual review. Continue with next batch.

- **Pros:** Good balance of speed and resilience. Failed batches don't block the rest.
- **Cons:** Need to track which batches failed. May need to disable indexes during bulk load for speed.

### Choosing a Strategy

For your project, consider:
- **Scale:** ~30k JSON files, ~90k ICD rows, ~49k OPS rows. Not billions, but enough that per-row checks are costly.
- **Re-runs:** You'll likely re-run when adding new years or fixing bugs.
- **Overlap:** Same hospital might appear in multiple years—need a composite key (e.g. IK + Standort + Year).

A practical choice: **Strategy B (hash/upsert)** or **Strategy D (batches + retry)**, possibly combined with **Strategy C (checkpoints)** for long-running full reloads.

---

## 4. How to Design an Ingestion Pipeline

### Step 1: Choose a Database

- **PostgreSQL:** Robust, SQL, good for relational data (hospitals, diagnoses, procedures). You already have Docker setup.
- **DuckDB:** Embedded, no server, great for analytics. Easy `pip install`, good for prototyping.
- **MongoDB:** Document store, flexible schema. Good if JSON structure varies a lot.

Document your choice and why (e.g. "PostgreSQL for relational queries and future dashboard integration").

### Step 2: Define the Schema

Before writing ingestion logic, define:
- What tables exist?
- What are the primary keys? (e.g. `(ik, standort, year)` for hospitals)
- What columns are required vs optional?
- What indexes do you need for dashboard queries?

### Step 3: Define the Ingestion Strategy

Document:
- Which strategy (A, B, C, or D) you use.
- How duplicates are handled (skip, update, fail).
- What happens on error (skip row, skip batch, abort).
- Whether the pipeline is one-off or incremental.

### Step 4: Implement in Stages

1. **Parsers:** Logic to read and parse each source (diagnoses.txt, Procedures.txt, JSON files). Output a stream or list of normalized records.
2. **Transformers:** Apply filters (e.g. ICD type 1/5 only), map field names, validate.
3. **Loaders:** Write to the database. Use batches, transactions, and your chosen strategy.
4. **Orchestration:** Tie parsers, transformers, and loaders together. Add config (paths, DB connection, batch size).

### Step 5: Configuration

Make the pipeline configurable:
- Paths to data folders.
- Database connection string.
- Batch size.
- Which years to ingest.
- Dry-run mode (parse only, don't write).

### Step 6: Observability

- Log progress (files processed, rows inserted, errors).
- Report counts at the end (expected vs actual).
- Write errors to a file or table for inspection.

---

## 5. Test Cases (from Your Course Materials)

Before considering the pipeline "done," test with small, controlled data:

| Test | Purpose |
|------|---------|
| Single file load | Basic path works |
| Two non-overlapping files | Multiple sources, no conflict |
| Corrupted entry in file | Pipeline doesn't crash; corrupt row is skipped/logged |
| Duplicate entry in file | Defined behavior (e.g. one row in DB, not two) |
| Two overlapping files | Same entity in both; strategy handles it |
| Same file loaded twice | Idempotency: no duplicate rows |
| Same entries, different values | Which value wins? (e.g. latest, or error) |
| Second file is superset of first | Incremental update works |

Create small test files (e.g. 10 rows each) to run these scenarios. Start each test with an empty database.

---

## 6. Scalability Considerations

If data grows 100× or 1000×:

- **Streaming:** Use generators/iterators instead of loading entire files into memory.
- **Batching:** Insert in batches (e.g. 1000–10000 rows per transaction), not row-by-row.
- **Indexes:** Disable non-essential indexes during bulk load; rebuild after. Speeds up inserts significantly.
- **Parallelism:** Process multiple files in parallel (if the database and disk can handle it).
- **Checkpointing:** For very long runs, persist progress so you can resume.

---

## 7. Summary

| Concept | Takeaway |
|---------|----------|
| **Ingestion** | Moving data from files/APIs into a database for querying and analysis |
| **ETL** | Extract (read/parse) → Transform (clean/normalize) → Load (write to DB) |
| **Idempotency** | Re-running with same input gives same result; no duplicates |
| **Strategy** | Choose one: check-before-write, hash-based, checkpoints, or batched retry |
| **Design** | Database → Schema → Strategy → Parsers → Transformers → Loaders → Config → Tests |

---

## 8. References

- `INFO/2_data_ingestion.md` — Assumptions, strategies, identifiers
- `INFO/5_write_ingestion_pipeline.md` — Steps, database choice, test cases
- `***WorkingFiles/plan.md` — Full project plan, Phase 4 (Ingestion)
- `***WorkingFiles/DATA_OVERVIEW.md` — Data formats, column layouts, filtering rules
