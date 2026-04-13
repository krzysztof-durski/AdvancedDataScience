"""
OPS ingestion from pipe-delimited TXT.
Format: level|id|code|?|label
Only rows with level=1 and non-empty code are ingested.
"""

import re
from pathlib import Path
from typing import Iterator

from .common import IngestStats
from .common import get_version_year_from_filename


def _extract_chapter(code: str) -> int:
    """Extract chapter from OPS code (e.g. 1-100 -> 1, 5-010.0 -> 5)."""
    match = re.match(r"^(\d)[-\s]", code)
    return int(match.group(1)) if match else 1


def _infer_level(code: str) -> int:
    """Infer hierarchy level: 3=1-10, 4=1-100/1-202, 5=1-202.0, 6=1-202.00."""
    if "." in code:
        # Has decimal: 1-202.0 -> 5, 1-202.00 -> 6
        return 6 if code.split(".")[-1] and len(code.split(".")[-1]) > 1 else 5
    parts = re.split(r"[-\s]+", code)
    if not parts:
        return 3
    # No decimal: 1-10 (2 chars) -> 3, 1-100 (3 chars) -> 4, 1-202 (3 chars) -> 4
    total_digits = sum(len(p) for p in parts if p.isdigit())
    return 3 if total_digits <= 2 else 4


def _derive_parent_code(code: str, known_codes: set[str]) -> str | None:
    """Derive parent by truncation. 1-202.00 -> 1-202.0 -> 1-202 -> 1-20 -> 1-2."""
    if not code:
        return None
    # If code has decimal part (e.g. 1-202.00), parent is 1-202.0 (drop last digit after dot)
    if "." in code:
        before, after = code.rsplit(".", 1)
        if len(after) > 1:
            candidate = before + "." + after[:-1]
        else:
            candidate = before
        if candidate in known_codes:
            return candidate
    # Try shortening last numeric segment (1-202 -> 1-20 -> 1-2, 1-100 -> 1-10)
    parts = code.split("-")
    for i in range(len(parts) - 1, -1, -1):
        seg = parts[i].replace(".", "")
        if seg.isdigit() and len(seg) > 1:
            for n in range(len(seg) - 1, 0, -1):
                candidate = "-".join(parts[:i] + [seg[:n]] + parts[i + 1 :])
                if candidate in known_codes:
                    return candidate
            break
    return None


def parse_ops_txt(
    path: str | Path,
    version_year: int | None = None,
    stats: IngestStats | None = None,
) -> Iterator[dict]:
    """
    Parse pipe-delimited OPS TXT and yield records as dicts.
    Format: level|id|code|?|label
    Only level=1 rows with code are yielded.
    """
    path = Path(path)
    if version_year is None:
        version_year = get_version_year_from_filename(path) or 2025

    rows: list[tuple[str, str]] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if stats:
                stats.read += 1
            parts = line.split("|")
            if len(parts) < 5:
                if stats:
                    stats.skipped += 1
                    print(f"[OPS] skipped malformed row {line_no}: expected >=5 columns")
                continue
            level, _, code, _, label = parts[0], parts[1], parts[2], parts[3], parts[4]
            if level != "1" or not code or not label:
                if stats:
                    stats.skipped += 1
                continue
            code = code.strip()
            label = label.strip()
            if not code or not label:
                if stats:
                    stats.skipped += 1
                continue
            rows.append((code, label))
            if stats:
                stats.accepted += 1

    known_codes = {code for code, _ in rows}

    for code, label in rows:
        chapter = _extract_chapter(code)
        level = _infer_level(code)
        parent_code = _derive_parent_code(code, known_codes)

        yield {
            "code": code,
            "label": label,
            "chapter": chapter,
            "parent_code": parent_code,
            "level": level,
            "version_year": version_year,
            "is_terminal": True,
        }


def ingest_ops_to_db(
    path: str | Path,
    conn,
    version_year: int | None = None,
    batch_size: int = 1000,
) -> IngestStats:
    """
    Ingest OPS TXT into PostgreSQL. Returns count of inserted/updated rows.
    """
    stats = IngestStats()
    records = list(parse_ops_txt(path, version_year, stats))
    if not records:
        return stats

    parent_codes = {r["parent_code"] for r in records if r["parent_code"]}
    for r in records:
        r["is_terminal"] = r["code"] not in parent_codes

    by_level: dict[int, list[dict]] = {}
    for r in records:
        by_level.setdefault(r["level"], []).append(r)

    code_to_id: dict[str, int] = {}
    effective_batch_size = max(batch_size, 1)
    for level in sorted(by_level.keys()):
        level_records = by_level[level]
        for idx in range(0, len(level_records), effective_batch_size):
            for r in level_records[idx : idx + effective_batch_size]:
                parent_id = code_to_id.get(r["parent_code"]) if r["parent_code"] else None
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO ops (code, label, chapter, parent_code, parent_id, level, version_year, is_terminal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (code, version_year) DO UPDATE SET
                        label = EXCLUDED.label,
                        chapter = EXCLUDED.chapter,
                        parent_code = EXCLUDED.parent_code,
                        parent_id = EXCLUDED.parent_id,
                        level = EXCLUDED.level,
                        is_terminal = EXCLUDED.is_terminal
                    RETURNING id, (xmax = 0) AS inserted
                    """,
                    (
                        r["code"],
                        r["label"],
                        r["chapter"],
                        r["parent_code"],
                        parent_id,
                        r["level"],
                        r["version_year"],
                        r["is_terminal"],
                    ),
                )
                row = cur.fetchone()
                if row:
                    code_to_id[r["code"]] = row[0]
                    if row[1]:
                        stats.inserted += 1
                    else:
                        stats.updated += 1
                cur.close()

    return stats
