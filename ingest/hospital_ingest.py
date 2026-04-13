"""Hospital location ingestion from quality-report JSON files."""

import json
from pathlib import Path

from .common import IngestStats


def _extract_nested(payload: dict, *path: str) -> str | None:
    node = payload
    for segment in path:
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node if isinstance(node, str) and node.strip() else None


def parse_hospital_json(path: str | Path) -> dict:
    """Parse one hospital report JSON into normalized location fields."""
    p = Path(path)
    parts = p.stem.split("-")
    if len(parts) < 3:
        raise ValueError(f"Unexpected hospital filename format: {p.name}")
    ik, standortnummer, year_raw = parts[0], parts[1], parts[2]
    report_year = int(year_raw)

    with p.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    hospital_name = _extract_nested(
        payload,
        "Qualitaetsbericht",
        "Krankenhaus",
        "Mehrere_Standorte",
        "Krankenhauskontaktdaten",
        "Name",
    )
    city = _extract_nested(
        payload,
        "Qualitaetsbericht",
        "Krankenhaus",
        "Mehrere_Standorte",
        "Krankenhauskontaktdaten",
        "Kontakt_Adresse",
        "Ort",
    )
    postal_code = _extract_nested(
        payload,
        "Qualitaetsbericht",
        "Krankenhaus",
        "Mehrere_Standorte",
        "Krankenhauskontaktdaten",
        "Kontakt_Adresse",
        "Postleitzahl",
    )

    return {
        "ik": ik,
        "standortnummer": standortnummer,
        "report_year": report_year,
        "hospital_name": hospital_name,
        "city": city,
        "postal_code": postal_code,
        "source_file": str(p),
    }


def ingest_hospital_json_files(
    json_files: list[str | Path],
    conn,
    batch_size: int = 200,
) -> IngestStats:
    """Ingest hospital/location records with composite-key upsert."""
    stats = IngestStats()
    effective_batch_size = max(batch_size, 1)
    normalized: list[dict] = []
    for file_path in json_files:
        stats.read += 1
        try:
            normalized.append(parse_hospital_json(file_path))
            stats.accepted += 1
        except Exception as exc:
            stats.errors += 1
            print(f"[HOSPITAL] failed parsing {file_path}: {exc}")

    for i in range(0, len(normalized), effective_batch_size):
        for record in normalized[i : i + effective_batch_size]:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO hospital_locations (
                    ik, standortnummer, report_year, hospital_name, city, postal_code, source_file
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ik, standortnummer, report_year) DO UPDATE SET
                    hospital_name = EXCLUDED.hospital_name,
                    city = EXCLUDED.city,
                    postal_code = EXCLUDED.postal_code,
                    source_file = EXCLUDED.source_file,
                    updated_at = NOW()
                RETURNING id, (xmax = 0) AS inserted
                """,
                (
                    record["ik"],
                    record["standortnummer"],
                    record["report_year"],
                    record["hospital_name"],
                    record["city"],
                    record["postal_code"],
                    record["source_file"],
                ),
            )
            row = cur.fetchone()
            cur.close()
            if row and row[1]:
                stats.inserted += 1
            else:
                stats.updated += 1

    return stats
