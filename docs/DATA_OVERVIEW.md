# DATA Folder — Overview (English)

A quick reference for the German healthcare data in this project. All column names and descriptions are translated so you know what you're working with.

---

## 1. Folder Structure

```
DATA/
├── diagnoses.txt      (~4.8 MB) — ICD diagnosis codes & descriptions
├── Procedures.txt     (~4.8 MB) — OPS procedure codes & descriptions
└── json_output/
    ├── json_2008/     Hospital quality reports (JSON)
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

> **Note:** JSON files are generated from `DATA/Folders/xml_YYYY/*-xml.xml` via `scripts/xml_to_json.py`. Ignore `DATA/BROKEN/` (corrupted 2017, 2019 data).

---

## 2. diagnoses.txt — ICD-10-GM (Diagnoses)

**Format:** Pipe-delimited (`|`), no header row  
**Rows:** ~89,600  
**Purpose:** German ICD-10-GM classification of medical diagnoses (conditions/diseases)

### Column Layout (8 columns)

| Col | Name (inferred) | English meaning | Example |
|-----|-----------------|-----------------|---------|
| 0 | Type | Row type: `0` = synonym/cross-reference (skip), `1` = main entry with ICD code, `2`–`6` = other variants | `1` or `0` |
| 1 | ID | Internal identifier | `90016` |
| 2 | Subtype | Sub-type flag (often `0` or `1`) | `1` |
| 3 | ICD_Code | ICD-10 code (when type = 1) | `A00.0`, `F14.1` |
| 4 | (empty) | — | |
| 5 | ICD_Code_Alt | Alternative code position (when type = 5) | `U61.2!`, `B96.5!` |
| 6 | (empty) | — | |
| 7 | Description | German description of the diagnosis | `Cholera durch Vibrio cholerae...` |

### Row types (column 0)

| Value | Count | Use |
|-------|-------|-----|
| `1` | ~83,900 | **Use these** — main entries with ICD code in column 3 |
| `2` | ~3,900 | May have codes in later columns |
| `5` | ~474 | ICD code in column 5 (e.g. `U61.2!`) |
| `0` | ~309 | Synonyms — skip (e.g. "see also", "see type of disease") |
| `3`, `4`, `6` | fewer | Other variants |

### Filtering for analysis

- **Keep:** rows where column 0 = `1` (or `5` if you also want those codes)
- **Skip:** rows where column 0 = `0` (synonyms)
- **ICD code:** column 3 for type `1`, column 5 for type `5`
- **Description:** column 7 (German text)

### Example rows

```
1|90016|1|A00.0||||Cholera durch Vibrio cholerae O:1, Biovar cholerae
5|97691|1|||B96.5!||Acinetobacter als Erreger
0|86498|1|||||Abnorm - s. Art der Krankheit   ← synonym, skip
```

---

## 3. Procedures.txt — OPS (Medical Procedures)

**Format:** Pipe-delimited (`|`), no header row  
**Rows:** ~48,700  
**Purpose:** German OPS classification of medical procedures (surgeries, treatments, etc.)

### Column Layout (5 columns)

| Col | Name (inferred) | English meaning | Example |
|-----|-----------------|-----------------|---------|
| 0 | Type | Row type: `0` = synonym (skip), `1` = main entry with OPS code | `1` or `0` |
| 1 | ID | Internal identifier | `10573` |
| 2 | OPS_Code | OPS procedure code | `1-100`, `8-200.2#`, `5-868.0` |
| 3 | (empty) | — | |
| 4 | Description | German description of the procedure | `Klinische Untersuchung in Allgemeinanästhesie` |

### Row types (column 0)

| Value | Count | Use |
|-------|-------|-----|
| `1` | ~48,400 | **Use these** — main entries with OPS code in column 2 |
| `0` | ~188 | Synonyms — skip |
| `2` | ~134 | Other variants |

### Filtering for analysis

- **Keep:** rows where column 0 = `1`
- **Skip:** rows where column 0 = `0`
- **OPS code:** column 2
- **Description:** column 4 (German text)

### Example rows

```
1|10573|1-100||Klinische Untersuchung in Allgemeinanästhesie
1|6120|8-200.2#||Geschlossene Reposition einer Fraktur am Humerusschaft ohne Osteosynthese
0|10422|||Abnorm - s. jeweiliger durchgeführter Eingriff   ← synonym, skip
```

---

## 4. Hospital JSON Files — Quality Reports

**Path:** `DATA/json_output/json_YYYY/*.json`  
**Files:** ~30,000 total  
**Purpose:** German hospital quality reports (Qualitätsberichte) — one JSON file per hospital location per year

### Filename pattern

`{IK}-{Standort}-{Year}.json`

- **IK** = Institutionskennzeichen (institution identifier)
- **Standort** = location/site number
- **Year** = report year (2008, 2010, 2012–2016, 2018, 2020–2024)

Example: `260100023-773287000-2024.json`

### Reading JSON in Python

```python
import json
from pathlib import Path

path = Path("DATA/json_output/json_2024/260100023-773287000-2024.json")
with open(path, encoding="utf-8") as f:
    data = json.load(f)

# Root key is always Qualitaetsbericht
report = data["Qualitaetsbericht"]
```

### Main German → English mappings (JSON keys)

| German key | English meaning |
|------------|-----------------|
| `Qualitaetsbericht` | Quality report (root object) |
| `Krankenhaus` | Hospital |
| `Name` | Name |
| `IK` | Institution identifier |
| `Standortnummer` | Site/location number |
| `Strasse` | Street |
| `Hausnummer` | House number |
| `Postleitzahl` | Postal code |
| `Ort` | City/town |
| `Anzahl_Betten` | Number of beds |
| `Fallzahlen` | Case numbers |
| `Vollstationaere_Fallzahl` | Inpatient case count |
| `Teilstationaere_Fallzahl` | Partial inpatient case count |
| `Ambulante_Fallzahl` | Outpatient case count |
| `Organisationseinheit_Fachabteilung` | Department/unit |
| `Fachabteilungsschluessel` | Department code |
| `Hauptdiagnose` | Main diagnosis |
| `ICD_10` | ICD-10 code |
| `Fallzahl` | Case count (for that diagnosis/procedure) |
| `OPS` / procedure codes | Procedure codes with counts |
| `Krankenhaustraeger` | Hospital operator |
| `Aerztliche_Leitung` | Medical director |
| `Pflegedienstleitung` | Nursing director |

### Data model (simplified)

Structure varies by year; newer files (2020+) use `Krankenhaus` → `Mehrere_Standorte` → `Standortkontaktdaten`. Focus on:

```
Qualitaetsbericht
  ├── Name / IK / Standortnummer
  ├── Kontaktdaten or Kontakt_Adresse (Strasse, Postleitzahl, Ort)
  ├── Anzahl_Betten
  ├── Fallzahlen (Vollstationaere_Fallzahl, Ambulante_Fallzahl, etc.)
  ├── Departments (Organisationseinheit_Fachabteilung)
  │     ├── Department name & codes
  │     ├── Diagnoses (ICD_10 + Fallzahl)
  │     └── Procedures (OPS + Fallzahl)
  └── Staff, services, etc.
```

### Years available

| Year | Files |
|------|-------|
| 2008 | ~1,922 |
| 2010 | ~1,841 |
| 2012–2016 | ~2,200–2,570 |
| 2018 | ~2,602 |
| 2020–2024 | ~2,200–2,900 |

2017 and 2019 — no data (BROKEN).

---

## 5. Quick reference — German terms in descriptions

Common words you'll see in the **description** columns (column 7 in diagnoses, column 4 in procedures):

| German | English |
|--------|---------|
| s. | see |
| s.a. | see also |
| s. Art der Krankheit | see type of disease |
| s. jeweiliger durchgeführter Eingriff | see respective procedure performed |
| Abnorm | Abnormal |
| Akut | Acute |
| Chronisch | Chronic |
| Angeboren | Congenital |
| Bösartig | Malignant |
| Gutartig | Benign |
| links | left |
| rechts | right |
| beidseitig | bilateral |
| ohne | without |
| mit | with |
| bei | in/with |
| als Erreger | as pathogen |
| Fraktur | Fracture |
| Operation | Surgery |
| Therapie | Therapy |
| Diagnostik | Diagnostics |
| Untersuchung | Examination |

---

## 6. Summary

| Source | Rows/Files | Key fields | Use for |
|-------|------------|------------|---------|
| **diagnoses.txt** | ~89.6k rows | Col 0 (filter), Col 3 or 5 (ICD), Col 7 (description) | ICD code lookup, diagnosis names |
| **Procedures.txt** | ~48.7k rows | Col 0 (filter), Col 2 (OPS), Col 4 (description) | OPS code lookup, procedure names |
| **json_output/json_YYYY/*.json** | ~30k files | Name, IK, address, Anzahl_Betten, ICD_10, OPS, Fallzahl | Hospital locations, beds, diagnosis/procedure counts by hospital |
