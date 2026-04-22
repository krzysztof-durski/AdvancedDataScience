"""End-to-end ingest smoke test across every reporting year represented in DATA/.

The fixture directory ``tests/fixtures/hospital_json/`` carries one real
Qualitaetsbericht JSON per year (2008, 2010, 2012-2016, 2018, 2020-2024),
chosen as the smallest parsable report per year. The tests exercise the full
pipeline: discovery -> parse -> upsert into every hospital_* table.
"""

from pathlib import Path

import pytest

from ingest.hospital_ingest import (
    discover_hospital_files,
    parse_hospital_file,
    upsert_department_diagnoses,
    upsert_department_procedures,
    upsert_departments,
    upsert_location_rows,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hospital_json"

EXPECTED_YEARS = {
    2008, 2010, 2012, 2013, 2014, 2015, 2016,
    2018, 2020, 2021, 2022, 2023, 2024,
}


def _fixture_files() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("*.json"))


def test_fixture_directory_covers_every_year():
    """Guardrail: bail out loudly if someone removes a year's sample."""
    years_on_disk = {int(p.stem.split("-")[-1]) for p in _fixture_files()}
    assert years_on_disk == EXPECTED_YEARS, (
        f"Fixture coverage drift: on_disk={sorted(years_on_disk)} "
        f"expected={sorted(EXPECTED_YEARS)}"
    )


def test_discover_finds_every_fixture():
    files = discover_hospital_files(str(FIXTURE_DIR), include_years=None, exclude_years=None)
    assert len(files) == len(EXPECTED_YEARS)
    assert {int(p.stem.split("-")[-1]) for p in files} == EXPECTED_YEARS


@pytest.mark.parametrize("fixture_path", _fixture_files(), ids=lambda p: p.name)
def test_parse_fixture_has_minimum_shape(fixture_path: Path):
    """Each fixture must yield a location row, >=1 department and >=1 diagnosis.

    Fixtures were picked to satisfy these bounds so the parser is exercised
    across the evolving Qualitaetsbericht shape used year-over-year.
    """
    location, depts, dx, px, counters = parse_hospital_file(fixture_path)

    assert counters.read == 1
    assert counters.accepted == 1
    assert counters.errors == 0

    ik, standortnummer, report_year, hospital_name, street, house, plz, ort, *_rest = location
    year_from_name = int(fixture_path.stem.split("-")[-1])
    assert report_year == year_from_name
    assert ik and standortnummer and hospital_name
    assert hospital_name != "UNKNOWN", (
        f"{fixture_path.name}: hospital_name fell through to UNKNOWN; "
        f"the schema for this year is not handled by _extract_location"
    )
    assert plz and ort, (
        f"{fixture_path.name}: address not resolved "
        f"(street={street!r} house={house!r} plz={plz!r} ort={ort!r}); "
        f"_extract_location likely missed this year's contact shape"
    )

    assert len(depts) >= 1, f"No departments parsed from {fixture_path.name}"
    assert len(dx) >= 1, f"No diagnoses parsed from {fixture_path.name}"
    assert isinstance(px, list)


def test_ingest_all_years(db_conn):
    """Ingest every fixture year into Postgres and verify row counts."""
    files = discover_hospital_files(str(FIXTURE_DIR), include_years=None, exclude_years=None)
    assert len(files) == len(EXPECTED_YEARS)

    all_locations: list[tuple] = []
    all_depts: list[tuple] = []
    all_dx: list[tuple] = []
    all_px: list[tuple] = []
    per_year_expected = {}

    for fp in files:
        location, depts, dx, px, _ = parse_hospital_file(fp)
        year = location[2]
        per_year_expected[year] = {
            "depts": len(depts),
            "dx": len(dx),
            "px": len(px),
        }
        all_locations.append(location)
        all_depts.extend(depts)
        all_dx.extend(dx)
        all_px.extend(px)

    with db_conn.cursor() as cur:
        inserted, updated = upsert_location_rows(cur, all_locations)
        upsert_departments(cur, all_depts)
        upsert_department_diagnoses(cur, all_dx)
        upsert_department_procedures(cur, all_px)
    db_conn.commit()

    assert inserted == len(EXPECTED_YEARS)
    assert updated == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM hospital_locations")
        assert cur.fetchone()[0] == len(EXPECTED_YEARS)

        cur.execute("SELECT DISTINCT report_year FROM hospital_locations ORDER BY report_year")
        years_in_db = {row[0] for row in cur.fetchall()}
        assert years_in_db == EXPECTED_YEARS

        cur.execute(
            """
            SELECT report_year, COUNT(*)
            FROM hospital_departments
            GROUP BY report_year
            """
        )
        dept_by_year = dict(cur.fetchall())

        cur.execute(
            """
            SELECT dep.report_year, COUNT(*)
            FROM hospital_department_diagnoses diag
            JOIN hospital_departments dep ON dep.department_id = diag.department_id
            GROUP BY dep.report_year
            """
        )
        dx_by_year = dict(cur.fetchall())

        cur.execute(
            """
            SELECT dep.report_year, COUNT(*)
            FROM hospital_department_procedures proc
            JOIN hospital_departments dep ON dep.department_id = proc.department_id
            GROUP BY dep.report_year
            """
        )
        px_by_year = dict(cur.fetchall())

        for year, expected in per_year_expected.items():
            dept_count = dept_by_year.get(year, 0)
            dx_count = dx_by_year.get(year, 0)
            px_count = px_by_year.get(year, 0)

            assert dept_count == expected["depts"], (
                f"year {year}: depts persisted={dept_count} parsed={expected['depts']}"
            )
            assert dx_count == expected["dx"], (
                f"year {year}: diagnoses persisted={dx_count} parsed={expected['dx']}"
            )
            assert px_count == expected["px"], (
                f"year {year}: procedures persisted={px_count} parsed={expected['px']}"
            )
