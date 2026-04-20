import json
from pathlib import Path

from ingest.hospital_ingest import (
    discover_hospital_files,
    parse_hospital_file,
    upsert_department_diagnoses,
    upsert_department_procedures,
    upsert_departments,
    upsert_location_rows,
)


def _sample_payload(name="Hospital A", dept_code="0100", icd="F14.1", ops="5-868.0", fallzahl="12"):
    return {
        "Qualitaetsbericht": {
            "Krankenhaus": {
                "Name": name,
                "Kontakt_Adresse": {
                    "Strasse": "Main",
                    "Hausnummer": "1",
                    "Postleitzahl": "12345",
                    "Ort": "Berlin",
                },
                "Anzahl_Betten": "100",
                "Fallzahlen": {
                    "Vollstationaere_Fallzahl": "1000",
                    "Teilstationaere_Fallzahl": "100",
                    "Ambulante_Fallzahl": "5000",
                },
                "Organisationseinheit_Fachabteilung": [
                    {
                        "Fachabteilungsschluessel": dept_code,
                        "Name": "Cardiology",
                        "Hauptdiagnose": [{"ICD_10": icd, "Fallzahl": fallzahl}],
                        "OPS": [{"OPS": ops, "Fallzahl": "20"}],
                    }
                ],
            }
        }
    }


def test_hospital_ingest_single_file(db_conn, tmp_data_dir: Path):
    p = tmp_data_dir / "260100023-773287000-2024.json"
    p.write_text(json.dumps(_sample_payload()), encoding="utf-8")

    location, depts, dx, px, counters = parse_hospital_file(p)
    assert counters.read == 1
    assert counters.accepted == 1
    assert location[0] == "260100023"
    assert location[1] == "773287000"
    assert location[2] == 2024

    with db_conn.cursor() as cur:
        ins, upd = upsert_location_rows(cur, [location])
        upsert_departments(cur, depts)
        upsert_department_diagnoses(cur, dx)
        upsert_department_procedures(cur, px)
    db_conn.commit()
    assert ins == 1
    assert upd == 0

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM hospital_locations")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT COUNT(*) FROM hospital_departments")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT COUNT(*) FROM hospital_department_diagnoses")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT COUNT(*) FROM hospital_department_procedures")
        assert cur.fetchone()[0] == 1


def test_hospital_overlap_and_update(db_conn, tmp_data_dir: Path):
    p1 = tmp_data_dir / "260100023-773287000-2024.json"
    p2 = tmp_data_dir / "260100023-773287000-2024-copy.json"
    p1.write_text(json.dumps(_sample_payload(name="Hospital Old", fallzahl="")), encoding="utf-8")
    p2.write_text(json.dumps(_sample_payload(name="Hospital New", fallzahl="99")), encoding="utf-8")

    l1, d1, dx1, px1, _ = parse_hospital_file(p1)
    # parse_hospital_file enforces strict filename pattern, so keep same structure
    p_valid = tmp_data_dir / "260100023-773287000-2024.json"
    p_valid.write_text(json.dumps(_sample_payload(name="Hospital New", fallzahl="99")), encoding="utf-8")
    l2, d2, dx2, px2, _ = parse_hospital_file(p_valid)

    with db_conn.cursor() as cur:
        upsert_location_rows(cur, [l1])
        upsert_departments(cur, d1)
        upsert_department_diagnoses(cur, dx1)
        upsert_department_procedures(cur, px1)
        _, updated = upsert_location_rows(cur, [l2])
        upsert_departments(cur, d2)
        upsert_department_diagnoses(cur, dx2)
        upsert_department_procedures(cur, px2)
    db_conn.commit()
    assert updated == 1

    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT h.hospital_name, d.case_count
            FROM hospital_locations h
            JOIN hospital_departments dep
              ON dep.ik = h.ik AND dep.standortnummer = h.standortnummer AND dep.report_year = h.report_year
            JOIN hospital_department_diagnoses d
              ON d.department_id = dep.department_id
            LIMIT 1
            """
        )
        name, count = cur.fetchone()
        assert name == "Hospital New"
        assert count == 99


def _ein_standort_kontakt_zugang_payload() -> dict:
    """Mirrors the majority shape in DATA/json_2024: address under
    Krankenhaus.Ein_Standort.Krankenhauskontaktdaten.Kontakt_Zugang.
    """
    return {
        "Qualitaetsbericht": {
            "Krankenhaus": {
                "Ein_Standort": {
                    "Krankenhauskontaktdaten": {
                        "Name": "Hospital Ein-Standort",
                        "Kontakt_Zugang": {
                            "Strasse": "Budapester Straße",
                            "Hausnummer": "38",
                            "Postleitzahl": "20359",
                            "Ort": "Hamburg",
                        },
                    }
                }
            }
        }
    }


def _mehrere_standorte_payload() -> dict:
    """Per-site address under Standortkontaktdaten should beat the umbrella
    address under Krankenhauskontaktdaten.
    """
    return {
        "Qualitaetsbericht": {
            "Krankenhaus": {
                "Mehrere_Standorte": {
                    "Krankenhauskontaktdaten": {
                        "Name": "Umbrella Org",
                        "Kontakt_Zugang": {
                            "Strasse": "Headquarter Str.",
                            "Postleitzahl": "00000",
                            "Ort": "Nowhere",
                        },
                    },
                    "Standortkontaktdaten": {
                        "Name": "Site Clinic",
                        "Kontakt_Zugang": {
                            "Strasse": "Berghäuschensweg",
                            "Hausnummer": "7",
                            "Postleitzahl": "41464",
                            "Ort": "Neuss",
                        },
                    },
                }
            }
        }
    }


def test_extract_address_from_ein_standort_kontakt_zugang(tmp_data_dir: Path):
    p = tmp_data_dir / "260100023-773287000-2024.json"
    p.write_text(json.dumps(_ein_standort_kontakt_zugang_payload()), encoding="utf-8")

    location, _, _, _, _ = parse_hospital_file(p)
    (
        ik, standort, year, name, street, house, plz, ort,
        *_rest,
    ) = location
    assert (ik, standort, year) == ("260100023", "773287000", 2024)
    assert name == "Hospital Ein-Standort"
    assert street == "Budapester Straße"
    assert house == "38"
    assert plz == "20359"
    assert ort == "Hamburg"


def test_extract_address_prefers_standortkontaktdaten(tmp_data_dir: Path):
    p = tmp_data_dir / "260100023-773287000-2024.json"
    p.write_text(json.dumps(_mehrere_standorte_payload()), encoding="utf-8")

    location, _, _, _, _ = parse_hospital_file(p)
    _, _, _, name, street, _house, plz, ort, *_ = location
    assert name == "Site Clinic"
    assert street == "Berghäuschensweg"
    assert plz == "41464"
    assert ort == "Neuss"


def test_extract_address_partial_cascades_across_candidates(tmp_data_dir: Path):
    """If Standortkontaktdaten supplies some fields but is missing others,
    later candidates should fill in the gaps."""
    payload = {
        "Qualitaetsbericht": {
            "Krankenhaus": {
                "Mehrere_Standorte": {
                    "Krankenhauskontaktdaten": {
                        "Kontakt_Zugang": {
                            "Postleitzahl": "41464",
                            "Ort": "Neuss",
                        },
                    },
                    "Standortkontaktdaten": {
                        "Name": "Partial Site",
                        "Kontakt_Zugang": {"Strasse": "Nordkanalallee"},
                    },
                }
            }
        }
    }
    p = tmp_data_dir / "260100023-773287000-2024.json"
    p.write_text(json.dumps(payload), encoding="utf-8")

    location, _, _, _, _ = parse_hospital_file(p)
    _, _, _, name, street, _house, plz, ort, *_ = location
    assert name == "Partial Site"
    assert street == "Nordkanalallee"
    assert plz == "41464"
    assert ort == "Neuss"


def test_discover_include_exclude_years(tmp_data_dir: Path):
    (tmp_data_dir / "260100023-773287000-2023.json").write_text("{}", encoding="utf-8")
    (tmp_data_dir / "260100023-773287000-2024.json").write_text("{}", encoding="utf-8")
    (tmp_data_dir / "bad_name.json").write_text("{}", encoding="utf-8")

    only_2024 = discover_hospital_files(str(tmp_data_dir), include_years={2024}, exclude_years=None)
    assert [f.name for f in only_2024] == ["260100023-773287000-2024.json"]

    exclude_2024 = discover_hospital_files(str(tmp_data_dir), include_years=None, exclude_years={2024})
    assert [f.name for f in exclude_2024] == ["260100023-773287000-2023.json"]

