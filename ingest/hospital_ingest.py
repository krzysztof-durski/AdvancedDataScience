import json
import re
from pathlib import Path
from typing import Any

from ingest.common import IngestCounters, chunked, execute_values_with_retry


FILE_RE = re.compile(r"^(?P<ik>\d+)-(?P<standort>\d+)-(?P<year>\d{4})\.json$")


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit() or ch == "-")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _first(d: Any, *keys: str):
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _ops_code_and_count(px: Any) -> tuple[str | None, int | None]:
    """OPS from legacy `OPS` blocks or newer `Prozedur` entries (`OPS_301`, `Anzahl`)."""
    if isinstance(px, dict):
        code = _first(px, "OPS_301", "OPS", "OPS_Code")
        if code is None:
            return None, None
        text = str(code).strip()
        if not text:
            return None, None
        count = _to_int(_first(px, "Anzahl", "Fallzahl"))
        return text, count
    if px is None or px == "":
        return None, None
    text = str(px).strip()
    return (text if text else None), None


def _department_codes(dept: dict) -> list[str]:
    """Normalize `Fachabteilungsschluessel` (string, dict, or list of `FA_Schluessel`) to FA codes."""
    raw = dept.get("Fachabteilungsschluessel")
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        t = raw.strip()
        return [t] if t else []
    if isinstance(raw, dict):
        v = _first(raw, "FA_Schluessel")
        if v is None:
            return []
        t = str(v).strip()
        return [t] if t else []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                v = _first(item, "FA_Schluessel")
                if v is not None:
                    t = str(v).strip()
                    if t:
                        out.append(t)
            else:
                if item is None:
                    continue
                t = str(item).strip()
                if t:
                    out.append(t)
        return out
    t = str(raw).strip()
    return [t] if t else []


def _dig(node: Any, *path: str) -> Any:
    cur = node
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _collect_by_key(node: Any, key: str) -> list:
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                out.extend(_as_list(v))
            out.extend(_collect_by_key(v, key))
    elif isinstance(node, list):
        for item in node:
            out.extend(_collect_by_key(item, key))
    return out


def _address_from_contact(contact: Any) -> tuple:
    """Pull (Strasse, Hausnummer, Postleitzahl, Ort) from a contact block.

    Real-world reports place the address under any of: top-level fields,
    a nested `Adresse` subobject (older shape), `Hausanschrift` (the
    2008-2012 shape), or `Kontakt_Zugang` (the shape used by most
    `*_Standort*kontaktdaten` blocks). Check them in that order.
    """
    if not isinstance(contact, dict):
        return None, None, None, None
    addr = _first(contact, "Adresse") or {}
    haus = _first(contact, "Hausanschrift") or {}
    zugang = _first(contact, "Kontakt_Zugang") or {}
    street = (
        _first(contact, "Strasse")
        or _first(addr, "Strasse")
        or _first(haus, "Strasse")
        or _first(zugang, "Strasse")
    )
    house = (
        _first(contact, "Hausnummer")
        or _first(addr, "Hausnummer")
        or _first(haus, "Hausnummer")
        or _first(zugang, "Hausnummer")
    )
    plz = (
        _first(contact, "Postleitzahl")
        or _first(addr, "Postleitzahl")
        or _first(haus, "Postleitzahl")
        or _first(zugang, "Postleitzahl")
    )
    ort = (
        _first(contact, "Ort")
        or _first(addr, "Ort")
        or _first(haus, "Ort")
        or _first(zugang, "Ort")
    )
    return street, house, plz, ort


def _contact_candidates(report: dict, kr: dict) -> list[dict]:
    """Ordered list of contact blocks to consult when extracting location data.

    The site-specific `Standortkontaktdaten` is preferred over the umbrella
    `Krankenhauskontaktdaten` because its address corresponds to the
    `standortnummer` recorded on the row.
    """
    candidates: list[dict] = []
    for c in (
        _first(report, "Kontakt_Adresse", "Kontaktdaten"),
        _first(kr, "Kontakt_Adresse", "Kontaktdaten", "Krankenhauskontaktdaten"),
        _dig(kr, "Mehrere_Standorte", "Standortkontaktdaten"),
        _dig(kr, "Ein_Standort", "Krankenhauskontaktdaten"),
        _dig(kr, "Mehrere_Standorte", "Krankenhauskontaktdaten"),
    ):
        if isinstance(c, dict) and c:
            candidates.append(c)
    return candidates


def _extract_location(report: dict, ik: str, standort: str, year: int, source_file: str) -> tuple:
    kr = report.get("Krankenhaus", {}) or {}
    candidates = _contact_candidates(report, kr)

    street = house = plz = ort = None
    for c in candidates:
        cs, ch, cp, co = _address_from_contact(c)
        street = street or cs
        house = house or ch
        plz = plz or cp
        ort = ort or co
        if street and house and plz and ort:
            break

    name = _first(report, "Name") or _first(kr, "Name")
    if not name:
        for c in candidates:
            n = _first(c, "Name")
            if n:
                name = n
                break
    if not name:
        name = _first(report, "Krankenhaus_Name") or _first(kr, "Krankenhaus_Name")
    if not name:
        name = "UNKNOWN"

    cases = _first(report, "Fallzahlen") or _first(kr, "Fallzahlen") or {}
    beds = _to_int(_first(report, "Anzahl_Betten") or _first(kr, "Anzahl_Betten"))
    return (
        ik,
        standort,
        year,
        str(name),
        street,
        house,
        plz,
        ort,
        beds,
        _to_int(_first(cases, "Vollstationaere_Fallzahl")),
        _to_int(_first(cases, "Teilstationaere_Fallzahl")),
        _to_int(_first(cases, "Ambulante_Fallzahl")),
        source_file,
    )


def parse_hospital_file(path: Path) -> tuple[tuple, list[tuple], list[tuple], list[tuple], IngestCounters]:
    counters = IngestCounters(read=1)
    m = FILE_RE.match(path.name)
    if not m:
        counters.errors += 1
        raise ValueError(f"Invalid hospital filename: {path.name}")
    ik = m.group("ik")
    standort = m.group("standort")
    year = int(m.group("year"))
    source_file = str(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        counters.errors += 1
        raise ValueError(f"Malformed JSON: {path}") from exc

    report = payload.get("Qualitaetsbericht")
    if not isinstance(report, dict):
        counters.errors += 1
        raise ValueError(f"Missing Qualitaetsbericht root in {path}")

    location_row = _extract_location(report, ik, standort, year, source_file)
    departments: list[tuple] = []
    diagnoses: list[tuple] = []
    procedures: list[tuple] = []

    dept_nodes = _collect_by_key(report, "Organisationseinheit_Fachabteilung")
    for dept in dept_nodes:
        if not isinstance(dept, dict):
            continue
        codes = _department_codes(dept)
        if not codes:
            continue
        dept_name = _first(dept, "Name")
        for dept_code in codes:
            departments.append((ik, standort, year, dept_code, dept_name, source_file))

        dx_items = [dx for dx in _collect_by_key(dept, "Hauptdiagnose") if isinstance(dx, dict)]
        px_ops = _collect_by_key(dept, "OPS")
        px_proc = _collect_by_key(dept, "Prozedur")

        for dept_code in codes:
            for dx in dx_items:
                icd = _first(dx, "ICD_10")
                if not icd:
                    continue
                diagnoses.append(
                    (ik, standort, year, dept_code, str(icd), _to_int(_first(dx, "Fallzahl")), source_file)
                )

            for px in px_ops:
                ops_code, count = _ops_code_and_count(px)
                if ops_code:
                    procedures.append((ik, standort, year, dept_code, ops_code, count, source_file))

            for px in px_proc:
                ops_code, count = _ops_code_and_count(px)
                if ops_code:
                    procedures.append((ik, standort, year, dept_code, ops_code, count, source_file))

    counters.accepted += 1
    return location_row, departments, diagnoses, procedures, counters


def discover_hospital_files(base_dir: str, include_years: set[int] | None, exclude_years: set[int] | None) -> list[Path]:
    files: list[Path] = []
    for p in Path(base_dir).rglob("*.json"):
        m = FILE_RE.match(p.name)
        if not m:
            continue
        year = int(m.group("year"))
        if include_years and year not in include_years:
            continue
        if exclude_years and year in exclude_years:
            continue
        files.append(p)
    files.sort()
    return files


def upsert_location_rows(cur, rows: list[tuple], batch_size: int = 500, retries: int = 3) -> tuple[int, int]:
    if not rows:
        return 0, 0
    deduped_rows = list({(r[0], r[1], r[2]): r for r in rows}.values())
    inserted = 0
    updated = 0
    sql = """
    WITH incoming(ik, standortnummer, report_year, hospital_name, street, house_number, postal_code, city, beds_count,
                  inpatient_case_count, partial_inpatient_case_count, outpatient_case_count, source_file) AS (VALUES %s),
    upserted AS (
      INSERT INTO hospital_locations(
        ik, standortnummer, report_year, hospital_name, street, house_number, postal_code, city, beds_count,
        inpatient_case_count, partial_inpatient_case_count, outpatient_case_count, source_file, ingested_at
      )
      SELECT ik, standortnummer, report_year, hospital_name, street, house_number, postal_code, city,
             beds_count::INTEGER,
             inpatient_case_count::INTEGER,
             partial_inpatient_case_count::INTEGER,
             outpatient_case_count::INTEGER,
             source_file, NOW()
      FROM incoming
      ON CONFLICT (ik, standortnummer, report_year) DO UPDATE
      SET hospital_name = EXCLUDED.hospital_name,
          street = EXCLUDED.street,
          house_number = EXCLUDED.house_number,
          postal_code = EXCLUDED.postal_code,
          city = EXCLUDED.city,
          beds_count = EXCLUDED.beds_count,
          inpatient_case_count = EXCLUDED.inpatient_case_count,
          partial_inpatient_case_count = EXCLUDED.partial_inpatient_case_count,
          outpatient_case_count = EXCLUDED.outpatient_case_count,
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
    return inserted, updated


def upsert_departments(cur, rows: list[tuple], batch_size: int = 1000, retries: int = 3) -> None:
    if not rows:
        return
    deduped_rows = list({(r[0], r[1], r[2], r[3]): r for r in rows}.values())
    sql = """
    INSERT INTO hospital_departments(
      ik, standortnummer, report_year, department_code, department_name, source_file
    ) VALUES %s
    ON CONFLICT (ik, standortnummer, report_year, department_code) DO UPDATE
    SET department_name = EXCLUDED.department_name,
        source_file = EXCLUDED.source_file,
        ingested_at = NOW()
    """
    for batch in chunked(deduped_rows, batch_size):
        execute_values_with_retry(cur, sql, batch, retries=retries)


def upsert_department_diagnoses(cur, rows: list[tuple], batch_size: int = 1000, retries: int = 3) -> None:
    if not rows:
        return
    deduped_rows = list({(r[0], r[1], r[2], r[3], r[4]): r for r in rows}.values())
    sql = """
    INSERT INTO hospital_department_diagnoses(department_id, icd_code, case_count, source_file, ingested_at)
    SELECT d.department_id, x.icd_code, x.case_count::INTEGER, x.source_file, NOW()
    FROM (VALUES %s) AS x(ik, standortnummer, report_year, department_code, icd_code, case_count, source_file)
    JOIN hospital_departments d
      ON d.ik = x.ik
     AND d.standortnummer = x.standortnummer
     AND d.report_year = x.report_year
     AND d.department_code = x.department_code
    ON CONFLICT (department_id, icd_code) DO UPDATE
    SET case_count = EXCLUDED.case_count,
        source_file = EXCLUDED.source_file,
        ingested_at = NOW()
    """
    for batch in chunked(deduped_rows, batch_size):
        execute_values_with_retry(cur, sql, batch, retries=retries)


def upsert_department_procedures(cur, rows: list[tuple], batch_size: int = 1000, retries: int = 3) -> None:
    if not rows:
        return
    deduped_rows = list({(r[0], r[1], r[2], r[3], r[4]): r for r in rows}.values())
    sql = """
    INSERT INTO hospital_department_procedures(department_id, ops_code, case_count, source_file, ingested_at)
    SELECT d.department_id, x.ops_code, x.case_count::INTEGER, x.source_file, NOW()
    FROM (VALUES %s) AS x(ik, standortnummer, report_year, department_code, ops_code, case_count, source_file)
    JOIN hospital_departments d
      ON d.ik = x.ik
     AND d.standortnummer = x.standortnummer
     AND d.report_year = x.report_year
     AND d.department_code = x.department_code
    ON CONFLICT (department_id, ops_code) DO UPDATE
    SET case_count = EXCLUDED.case_count,
        source_file = EXCLUDED.source_file,
        ingested_at = NOW()
    """
    for batch in chunked(deduped_rows, batch_size):
        execute_values_with_retry(cur, sql, batch, retries=retries)

