import csv
from pathlib import Path

from tqdm import tqdm

from ingest.common import IngestCounters, chunked, execute_values_with_retry


def parse_ops_file(
    path: str, version_year: int, *, show_progress: bool = False
) -> tuple[list[tuple], IngestCounters]:
    counters = IngestCounters()
    rows: list[tuple] = []
    source = str(Path(path))
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="|")
        iterable = (
            tqdm(
                reader,
                desc=f"OPS {Path(path).name}",
                unit="row",
                disable=not show_progress,
            )
            if show_progress
            else reader
        )
        for parts in iterable:
            counters.read += 1
            if not parts:
                counters.skipped += 1
                continue
            try:
                row_type = int(parts[0].strip() or "0")
            except ValueError:
                counters.skipped += 1
                continue
            if row_type != 1:
                counters.skipped += 1
                continue
            code = parts[2].strip() if len(parts) > 2 else ""
            description = parts[4].strip() if len(parts) > 4 else ""
            if not code or not description:
                counters.skipped += 1
                continue
            rows.append((code, version_year, description, row_type, source))
            counters.accepted += 1
    return rows, counters


def upsert_ops_rows(cur, rows: list[tuple], batch_size: int = 1000, retries: int = 3) -> tuple[int, int]:
    if not rows:
        return 0, 0
    # Guard against duplicate (code, version_year) entries in a single VALUES batch.
    # Postgres rejects ON CONFLICT statements that touch the same target key twice.
    deduped_map = {(r[0], r[1]): r for r in rows}
    deduped_rows = list(deduped_map.values())
    duplicate_updates = len(rows) - len(deduped_rows)
    inserted = 0
    updated = 0
    sql = """
    WITH incoming(code, version_year, description_de, row_type, source_file) AS (VALUES %s),
    upserted AS (
      INSERT INTO ops_reference(code, version_year, description_de, row_type, source_file, ingested_at)
      SELECT code, version_year, description_de, row_type, source_file, NOW() FROM incoming
      ON CONFLICT (code, version_year) DO UPDATE
      SET description_de = EXCLUDED.description_de,
          row_type = EXCLUDED.row_type,
          source_file = EXCLUDED.source_file,
          ingested_at = NOW()
      RETURNING xmax = 0 AS inserted
    )
    SELECT
      SUM(CASE WHEN inserted THEN 1 ELSE 0 END),
      SUM(CASE WHEN inserted THEN 0 ELSE 1 END)
    FROM upserted
    """
    for batch in chunked(deduped_rows, batch_size):
        execute_values_with_retry(cur, sql, batch, retries=retries)
        c_inserted, c_updated = cur.fetchone()
        inserted += c_inserted or 0
        updated += c_updated or 0
    return inserted, updated + duplicate_updates

