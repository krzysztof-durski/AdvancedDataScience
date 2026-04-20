# Database ER Diagram

This diagram reflects the schema currently defined in `ingest/schema.py`.

```mermaid
erDiagram
    HOSPITAL_LOCATIONS {
        text ik PK
        text standortnummer PK
        integer report_year PK
        text hospital_name
        text street
        text house_number
        text postal_code
        text city
        integer beds_count
        integer inpatient_case_count
        integer partial_inpatient_case_count
        integer outpatient_case_count
        text source_file
        timestamptz ingested_at
    }

    HOSPITAL_DEPARTMENTS {
        bigint department_id PK
        text ik FK
        text standortnummer FK
        integer report_year FK
        text department_code
        text department_name
        text source_file
        timestamptz ingested_at
    }

    HOSPITAL_DEPARTMENT_DIAGNOSES {
        bigint department_id PK, FK
        text icd_code PK
        integer case_count
        text source_file
        timestamptz ingested_at
    }

    HOSPITAL_DEPARTMENT_PROCEDURES {
        bigint department_id PK, FK
        text ops_code PK
        integer case_count
        text source_file
        timestamptz ingested_at
    }

    ICD_REFERENCE {
        text code PK
        integer version_year PK
        text description_de
        smallint row_type
        text source_file
        timestamptz ingested_at
    }

    OPS_REFERENCE {
        text code PK
        integer version_year PK
        text description_de
        smallint row_type
        text source_file
        timestamptz ingested_at
    }

    INGEST_FILES {
        text file_path PK
        bigint file_size_bytes
        bigint file_mtime_ns
        text file_sha256
        timestamptz last_ingested_at
        text status
        text error_message
    }

    HOSPITAL_LOCATIONS ||--o{ HOSPITAL_DEPARTMENTS : contains
    HOSPITAL_DEPARTMENTS ||--o{ HOSPITAL_DEPARTMENT_DIAGNOSES : reports
    HOSPITAL_DEPARTMENTS ||--o{ HOSPITAL_DEPARTMENT_PROCEDURES : reports
    ICD_REFERENCE o|..o{ HOSPITAL_DEPARTMENT_DIAGNOSES : lookup_by_icd_code
    OPS_REFERENCE o|..o{ HOSPITAL_DEPARTMENT_PROCEDURES : lookup_by_ops_code
```

## Relationship Notes

- `hospital_locations` uses a composite primary key: `(ik, standortnummer, report_year)`.
- `hospital_departments` belongs to one hospital location through that same composite key.
- `hospital_department_diagnoses` and `hospital_department_procedures` belong to one department via `department_id`.
- `icd_reference` and `ops_reference` act as lookup tables for code metadata.
- The current schema does **not** declare foreign keys from `hospital_department_diagnoses.icd_code` to `icd_reference.code` or from `hospital_department_procedures.ops_code` to `ops_reference.code`, so those links are logical relationships rather than enforced constraints.
- `ingest_files` is operational metadata for tracking ingested source files and is not directly connected by foreign keys to the domain tables.
