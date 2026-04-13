# Ingestion Strategy

## Deterministic keys

- ICD upsert key: `(code, version_year)`
- OPS upsert key: `(code, version_year)`
- Hospital/location upsert key: `(ik, standortnummer, report_year)`

## Duplicate and conflict behavior

- Same key + same values: upsert executes as a no-op update and row content remains unchanged.
- Same key + different values: incoming file wins (`ON CONFLICT ... DO UPDATE`).
- Reruns are deterministic because keys and update policy are stable across runs.

## Processed-file tracking strategy

The pipeline tracks processed files in `ingest_files` using:

- `phase` (`icd`, `ops`, `hospital`)
- absolute `file_path`
- `mtime_ns`
- `size_bytes`
- `sha256`

Before each phase/file load, current file signature is compared with the last stored signature:

- unchanged signature -> skip file
- changed or unseen signature -> ingest and update signature state

This prevents unintended duplicate work during reruns while still allowing updates when source files change.

## Retry and error policy

- Upserts are idempotent, so rerunning after failure is safe.
- Default mode is fail-fast (`--continue-on-error` disabled).
- Optional continue mode keeps processing when non-critical phase errors occur.
