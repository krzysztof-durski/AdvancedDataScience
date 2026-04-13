"""
ICD-10-GM ingestion from pipe-delimited TXT.
Format: level|id|?|?|?|code|?|label
Only rows with level=5 and non-empty code are ingested.
"""

import re
from pathlib import Path
from typing import Iterator

from .common import IngestStats
from .common import get_version_year_from_filename


def _extract_category3(code: str) -> str:
    """Extract 3-char category from ICD code (e.g. A00.0 -> A00)."""
    code_clean = code.upper().replace(".", "").replace("!", "").replace("*", "").replace("†", "")
    match = re.match(r"^([A-Z]\d{2})", code_clean)
    return match.group(1) if match else code[:3]


def _infer_level(code: str) -> int:
    """Infer hierarchy level from code: 3=A00, 4=A00.0, 5=A00.00."""
    code_clean = code.upper().replace(".", "").replace("!", "").replace("*", "").replace("†", "")
    if len(code_clean) <= 3:
        return 3
    if "." in code.upper():
        return 5 if code_clean.count("0") + len(code_clean) > 5 else 4
    return 4


def _infer_code_type(code: str) -> str:
    """Infer codeType from code suffix (!, *, †)."""
    if "†" in code or "dagger" in code.lower():
        return "dagger"
    if "*" in code or "asterisk" in code.lower():
        return "asterisk"
    if "!" in code or "exclamation" in code.lower():
        return "exclamation"
    return "primary"


def _derive_parent_code(code: str, known_codes: set[str]) -> str | None:
    """Derive parent code by truncation. A00.0 -> A00, A00.00 -> A00.0."""
    code_clean = code.upper().replace("!", "").replace("*", "").replace("†", "")
    # Try removing last segment: A00.00 -> A00.0 -> A00
    if "." in code_clean:
        parts = code_clean.split(".")
        for i in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in known_codes:
                return candidate
        # Parent is 3-char category
        if len(parts[0]) >= 3:
            cat3 = parts[0][:3]
            if cat3 in known_codes:
                return cat3
    elif len(code_clean) > 3:
        cat3 = code_clean[:3]
        if cat3 in known_codes:
            return cat3
    return None


def parse_icd_txt(
    path: str | Path,
    version_year: int | None = None,
    stats: IngestStats | None = None,
) -> Iterator[dict]:
    """
    Parse pipe-delimited ICD TXT and yield records as dicts.
    Format: level|id|?|?|?|code|?|label
    Only level=5 rows with code are yielded.
    """
    path = Path(path)
    if version_year is None:
        version_year = get_version_year_from_filename(path) or 2025

    # First pass: collect all codes for parent resolution
    rows: list[tuple[str, str]] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if stats:
                stats.read += 1
            parts = line.split("|")
            if len(parts) < 8:
                if stats:
                    stats.skipped += 1
                    print(f"[ICD] skipped malformed row {line_no}: expected >=8 columns")
                continue
            level, _, _, _, _, code, _, label = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
            if level != "5" or not code or not label:
                if stats:
                    stats.skipped += 1
                continue
            code = code.strip().upper()
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
        category3 = _extract_category3(code)
        level = _infer_level(code)
        code_type = _infer_code_type(code)
        parent_code = _derive_parent_code(code, known_codes)

        yield {
            "code": code,
            "label": label,
            "category3": category3,
            "parent_code": parent_code,
            "level": level,
            "version_year": version_year,
            "is_terminal": True,
            "code_type": code_type,
        }


def ingest_icd_to_db(
    path: str | Path,
    conn,
    version_year: int | None = None,
    batch_size: int = 1000,
) -> IngestStats:
    """
    Ingest ICD TXT into PostgreSQL. Returns count of inserted/updated rows.
    """
    stats = IngestStats()
    records = list(parse_icd_txt(path, version_year, stats))
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
                    INSERT INTO icd (code, label, category3, parent_code, parent_id, level, version_year, is_terminal, code_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (code, version_year) DO UPDATE SET
                        label = EXCLUDED.label,
                        category3 = EXCLUDED.category3,
                        parent_code = EXCLUDED.parent_code,
                        parent_id = EXCLUDED.parent_id,
                        level = EXCLUDED.level,
                        is_terminal = EXCLUDED.is_terminal,
                        code_type = EXCLUDED.code_type
                    RETURNING id, (xmax = 0) AS inserted
                    """,
                    (
                        r["code"],
                        r["label"],
                        r["category3"],
                        r["parent_code"],
                        parent_id,
                        r["level"],
                        r["version_year"],
                        r["is_terminal"],
                        r["code_type"],
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
