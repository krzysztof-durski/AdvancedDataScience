# Project Plan: Hospital Maps Data Pipeline

## Overview

This plan synthesizes the INFO documentation for the Advanced Data Science course project. The goal is to build a data ingestion pipeline and dashboard for German health sector data.

**Data flow:** Raw XML → JSON conversion → Ingestion into database → Dashboard

---

## 1. Course Context (from INFO/0_info_about_course.md)

- **Course:** Advanced Data Science
- **Focus:** Real-world health sector data, clean coding, testing, architecture, advanced data analysis
- **Prerequisite:** Python knowledge
- **Recommendation:** Work in teams of 2–3; share ideas and code; plan milestones and reach out when stuck

---

## 2. Project Goal (from INFO/1_project_overview.md)

Build a **data ingestion pipeline** that feeds a **dashboard** with maps and/or diagrams for German health data analysis.

**Three main data sources:**
- Diagnoses (ICD system)
- Medical procedures (OPS system)
- Hospital data (quality reports)

---

## 3. Research Questions (from INFO/1_project_overview.md)

| Priority | Question                                                                |
| -------- | ----------------------------------------------------------------------- |
| 1        | Which types of diagnosis are the most frequent?                         |
| 2        | Where are the most cardiac surgeries (or other procedures) carried out? |
| 3        | Where are hospitals located?                                            |
| 4        | Calculate geographical density of hospitals                             |
| 5        | Which area has the most hospitals/beds/diagnoses per population?        |
| 6        | Calculate travel distance from a given location to hospitals            |
| 7        | Compare 2023 vs 2024 data and visualize differences                    |
| 8        | Use Protomaps for data-privacy-sensitive mapping                        |
| 9        | Integrate an AI system to query the data                                |

---

## 4. Data Sources — After Conversion

### 4.1 Canonical Data Files & Folders (Post-Conversion)

> **After XML→JSON conversion, these are the data sources for ingestion.** No XML parsing in the pipeline.

| Source               | Path                          | Format         | Notes                                                                 |
| -------------------- | ----------------------------- | -------------- | --------------------------------------------------------------------- |
| **Diagnoses (ICD)**  | `DATA/diagnoses.txt`          | Pipe-delimited | ~89.6k rows. Col 0: filter. Col 3 or 5: ICD code. Col 7: description. |
| **Procedures (OPS)** | `DATA/Procedures.txt`         | Pipe-delimited | ~48.7k rows. Col 0: filter. Col 2: OPS code. Col 4: description.       |
| **Hospital JSON**    | `DATA/json_output/json_YYYY/` | JSON           | ~30k files total. One `.json` per hospital location per year.        |

**Folder structure (post-conversion):**

```
DATA/
├── diagnoses.txt           (~4.8 MB) — ICD codes & descriptions
├── Procedures.txt          (~4.8 MB) — OPS codes & descriptions
└── json_output/
    ├── json_2008/           Hospital quality reports (JSON)
    ├── json_2010/
    ├── json_2012/
    ├── json_2013/
    ├── json_2014/
    ├── json_2015/
    ├── json_2016/
    ├── json_2018/
    ├── json_2020/
    ├── json_2021/
    ├── json_2022/
    ├── json_2023/
    └── json_2024/
```

**JSON filename pattern:** `{IK}-{Standort}-{Year}.json` (e.g. `260100023-773287000-2024.json`)

**JSON structure (from INFO/4_data_hospitals.md):** Each file = one hospital location. Focus on:
- Hospital name, IK, address (street, postal code, city)
- Anzahl_Betten (beds)
- Fallzahlen (inpatient, outpatient counts)
- Departments (Fachabteilungen) with ICD_10 + Fallzahl, OPS + Fallzahl

### 4.2 Raw XML (Pre-Conversion, Optional)

| Source        | Path                     | Purpose                          |
| ------------- | ------------------------- | -------------------------------- |
| Hospital XML  | `DATA/Folders/xml_YYYY/`  | Source for conversion. Ignore after. |

> **Ignore:** `DATA/BROKEN/` — do not use (corrupted 2017, 2019 data).

### 4.3 External Sources (If Updates Needed)

| Source                    | Location                                                                                                               |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| ICD-10-GM                 | [bfarm.de](https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html) → ICD-10-GM → Alphabet EDV-Fassung TXT |
| OPS                       | Same page → OPS section                                                                                                |
| Hospital data (new years) | [qb-referenzdatenbank.g-ba.de](https://qb-referenzdatenbank.g-ba.de/#/login) (request form)                            |

> **Warning (INFO/4_data_hospitals.md):** Hospital data must not be redistributed.

### 4.4 Optional Data

- Geo coordinates (geocode from hospital addresses in JSON)
- Demographic / population density data
- Postal code areas (GeoJSON)
- OpenStreetMap points of interest

---

## 5. Phase 0: XML to JSON Conversion

**Goal:** Convert all `*-xml.xml` files to JSON before ingestion. Pipeline ingests JSON only.

### 5.1 Conversion Script

- **Script:** `scripts/xml_to_json.py`
- **Input:** `DATA/Folders/xml_YYYY/*-xml.xml`
- **Output:** `DATA/json_output/json_YYYY/*.json`
- **Batch by year:** `./scripts/convert_xml_by_year.sh` or `python scripts/xml_to_json.py --year 2024`

### 5.2 Conversion Details

- Uses `xml.etree.ElementTree` + regex fixes for common malformed XML
- Optional: `pip install lxml` for better recovery of corrupted files
- Progress bar with %; errors reported on separate lines
- See `***WorkingFiles/DATA_OVERVIEW.md` for JSON structure and German→English tag mappings

### 5.3 Checklist

- [ ] Run full conversion: `./scripts/convert_xml_by_year.sh` (or per-year)
- [ ] Verify `DATA/json_output/json_YYYY/` contains JSON files
- [ ] Confirm file counts match expected (~2k–2.9k per year)

---

## 6. Data Parsing Notes (from INFO/3, DATA_OVERVIEW)

### 6.1 ICD (Diagnoses) — `DATA/diagnoses.txt`

- Pipe-delimited, no header
- **Filter:** Col 0 = `1` or `5` (skip `0` = synonyms)
- **ICD code:** Col 3 (type 1) or Col 5 (type 5)
- **Description:** Col 7
- Example: `1|90016|1|A00.0||||Cholera durch Vibrio cholerae...`

### 6.2 OPS (Procedures) — `DATA/Procedures.txt`

- Pipe-delimited, no header
- **Filter:** Col 0 = `1` (skip `0` = synonyms)
- **OPS code:** Col 2
- **Description:** Col 4
- Example: `1|10573|1-100||Klinische Untersuchung in Allgemeinanästhesie`

### 6.3 Hospital JSON — `DATA/json_output/json_YYYY/*.json`

- One JSON object per file
- Root key: `Qualitaetsbericht`
- Extract: Name, IK, Standortnummer, address (Strasse, Postleitzahl, Ort), Anzahl_Betten, Fallzahlen, departments with ICD_10/OPS + Fallzahl
- See `***WorkingFiles/DATA_OVERVIEW.md` for full tag mappings

---

## 7. Data Ingestion Plan (from INFO/2_data_ingestion.md, INFO/5_write_ingestion_pipeline.md)

### 7.1 Requirements

- Scale: many entries (1B+), large annotations (1MB/entry)
- Incremental updates and full reload
- Non-predictable write failures
- Evolving data model
- Eventual consistency storage
- GDPR: retroactive deletion
- Time pressure

### 7.2 Ingestion Strategies (Choose One)

| Strategy | Description                                      |
| -------- | ------------------------------------------------ |
| A        | Check if entry exists before writing             |
| B        | Hash-based unique identification                 |
| C        | Checkpoints + metadata of processed entries      |
| D        | Batched processing with retry for failed batches |

**Note:** Document pros and cons of the chosen strategy.

### 7.3 Database Choice

- **Recommended:** DuckDB, MongoDB, or PostgreSQL
- **DuckDB:** `pip`/`uv` install, Python library
- **MongoDB/PostgreSQL:** Run locally via Docker
- **Supabase:** Not suitable — data ~22 GB; free tier 500 MB limit.
- **Optional:** Two databases + ETL for subset copy

### 7.4 Identifiers (from INFO/2_data_ingestion.md)

Evaluate: `john.doe@email`, `1`, `user_001`, `a`, `a4bf2m8`, `Il1O0o`, UUIDs, composite keys, non-ASCII, temporary IDs, date-based IDs.

---

## 8. Implementation Steps

### Phase 1: Setup

1. [ ] Choose database (DuckDB / MongoDB / PostgreSQL)
2. [ ] Set up Docker (if needed)
3. [ ] Create project structure and dependencies

### Phase 2: XML to JSON Conversion

1. [ ] Run `scripts/xml_to_json.py` (or `convert_xml_by_year.sh`) for all years
2. [ ] Verify `DATA/json_output/` structure and file counts
3. [ ] Document any skipped files (parse errors)

### Phase 3: Data Verification

1. [ ] Verify `DATA/diagnoses.txt` and `DATA/Procedures.txt` are complete and parseable
2. [ ] Verify `DATA/json_output/json_*/` structure
3. [ ] (Optional) Download newer ICD/OPS or hospital data if updates needed

### Phase 4: Ingestion Pipeline

1. [ ] Implement ingestion strategy (document choice)
2. [ ] Implement ICD parser (diagnoses.txt)
3. [ ] Implement OPS parser (Procedures.txt)
4. [ ] Implement hospital **JSON** parser (json_output)
5. [ ] Add configuration (paths, DB connection, batch size)
6. [ ] Handle errors, idempotency, re-runs

### Phase 5: Testing (from INFO/5_write_ingestion_pipeline.md)

1. [ ] Create test data (e.g. 10-entry files)
2. [ ] Implement test cases:
   - Single file load
   - Two non-overlapping files
   - Corrupted entry
   - Duplicate entry
   - Two overlapping files
   - Same file loaded twice
   - Same entries, different values
   - Second file superset of first

### Phase 6: Dashboard

1. [ ] Design dashboard (maps, diagrams)
2. [ ] Implement visualization (e.g. Protomaps)
3. [ ] Answer selected research questions

### Phase 7: Documentation

1. [ ] Document design decisions
2. [ ] Document ingestion strategy pros/cons
3. [ ] Add README and usage instructions

---

## 9. Scalability Considerations (from INFO/5_write_ingestion_pipeline.md)

- What if data grows 100× or 1000×?
- Use generators for streaming (Python)
- Disable index updates during bulk ingestion
- Batch processing and checkpointing

---

## 10. Open Decisions

- Exact ingestion strategy
- Database choice
- Which research questions to prioritize
- Team composition and roles
- Which JSON years to ingest first (e.g. 2023+2024 for comparison; or full 2008–2024)

---

## 11. References

| Document | Content |
| -------- | ------- |
| `INFO/0_info_about_course.md` | Course goals |
| `INFO/1_project_overview.md` | Project goal, research questions, data sources |
| `INFO/2_data_ingestion.md` | Ingestion assumptions, strategies, identifiers |
| `INFO/3_data_diagnoses_and_procedures.md` | ICD/OPS format and sources |
| `INFO/4_data_hospitals.md` | Hospital data structure, XML→JSON recommendation |
| `INFO/5_write_ingestion_pipeline.md` | Pipeline steps, database choice, test cases |
| `***WorkingFiles/DATA_OVERVIEW.md` | Column layouts, tag mappings, filtering rules |
| `***WorkingFiles/database.md` | PostgreSQL/Docker quick reference |
