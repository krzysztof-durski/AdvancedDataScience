import json
from pathlib import Path

import pytest

from ingest.hospital_ingest import (
    _to_int,
    discover_hospital_files,
    parse_hospital_file,
)
from ingest.icd_ingest import parse_icd_file
from ingest.ops_ingest import parse_ops_file


def test_to_int_handles_symbols_and_blank_values():
    assert _to_int(" 1.234 ") == 1234
    assert _to_int("-42 beds") == -42
    assert _to_int("") is None
    assert _to_int("n/a") is None
    assert _to_int(None) is None


def test_parse_hospital_file_rejects_bad_filename(tmp_path: Path):
    p = tmp_path / "bad_name.json"
    p.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid hospital filename"):
        parse_hospital_file(p)


def test_parse_hospital_file_requires_qualitaetsbericht(tmp_path: Path):
    p = tmp_path / "260100023-773287000-2024.json"
    p.write_text(json.dumps({"Krankenhaus": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing Qualitaetsbericht root"):
        parse_hospital_file(p)


def test_parse_hospital_file_accepts_single_department_object(tmp_path: Path):
    p = tmp_path / "260100023-773287000-2024.json"
    payload = {
        "Qualitaetsbericht": {
            "Krankenhaus": {
                "Name": "Hospital Unit",
                "Organisationseinheit_Fachabteilung": {
                    "Fachabteilungsschluessel": "0200",
                    "Name": "Unit Dept",
                    "Hauptdiagnose": {"ICD_10": "F14.1", "Fallzahl": "7"},
                    "OPS": "5-868.0",
                },
            }
        }
    }
    p.write_text(json.dumps(payload), encoding="utf-8")

    location, departments, diagnoses, procedures, counters = parse_hospital_file(p)
    assert counters.read == 1
    assert counters.accepted == 1
    assert location[0:3] == ("260100023", "773287000", 2024)
    assert len(departments) == 1
    assert diagnoses[0][4:6] == ("F14.1", 7)
    assert procedures[0][4:6] == ("5-868.0", None)


def test_parse_hospital_file_prozedur_ops_301_and_anzahl(tmp_path: Path):
    p = tmp_path / "260100023-773287000-2024.json"
    payload = {
        "Qualitaetsbericht": {
            "Krankenhaus": {"Name": "X"},
            "Organisationseinheit_Fachabteilung": [
                {
                    "Fachabteilungsschluessel": "0100",
                    "Name": "Chirurgie",
                    "Prozeduren": {
                        "Verpflichtende_Angabe": {
                            "Prozedur": [
                                {"OPS_301": "8-855.3", "Anzahl": "3453"},
                                {"OPS_301": "8-933", "Anzahl": "1770"},
                            ]
                        }
                    },
                }
            ],
        }
    }
    p.write_text(json.dumps(payload), encoding="utf-8")

    _, _, _, procedures, counters = parse_hospital_file(p)
    assert counters.accepted == 1
    assert len(procedures) == 2
    assert procedures[0][3:6] == ("0100", "8-855.3", 3453)
    assert procedures[1][3:6] == ("0100", "8-933", 1770)


def test_parse_hospital_file_list_fa_schluessel_replicates_procedures(tmp_path: Path):
    p = tmp_path / "260100023-773287000-2024.json"
    payload = {
        "Qualitaetsbericht": {
            "Organisationseinheit_Fachabteilung": {
                "Fachabteilungsschluessel": [
                    {"FA_Schluessel": "0100"},
                    {"FA_Schluessel": "0101"},
                ],
                "Name": "Shared OE",
                "Prozeduren": {
                    "Prozedur": [{"OPS_301": "8-855.3", "Anzahl": "10"}]
                },
            }
        }
    }
    p.write_text(json.dumps(payload), encoding="utf-8")

    _, departments, _, procedures, _ = parse_hospital_file(p)
    assert len(departments) == 2
    assert len(procedures) == 2
    assert {r[3] for r in procedures} == {"0100", "0101"}
    assert all(r[4:6] == ("8-855.3", 10) for r in procedures)


def test_discover_hospital_files_sorts_matching_files(tmp_path: Path):
    (tmp_path / "260100023-773287000-2024.json").write_text("{}", encoding="utf-8")
    (tmp_path / "260100023-773287000-2023.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ignore.json").write_text("{}", encoding="utf-8")

    files = discover_hospital_files(str(tmp_path), include_years=None, exclude_years=None)
    assert [p.name for p in files] == [
        "260100023-773287000-2023.json",
        "260100023-773287000-2024.json",
    ]


def test_parse_icd_file_type_five_uses_secondary_code_column(tmp_path: Path):
    icd_file = tmp_path / "icd.txt"
    icd_file.write_text("5|1|1|||B96.5!||Acinetobacter\n", encoding="utf-8")

    rows, counters = parse_icd_file(str(icd_file), 2025)
    assert counters.read == 1
    assert counters.accepted == 1
    assert counters.skipped == 0
    assert rows == [("B96.5!", 2025, "Acinetobacter", 5, str(icd_file))]


def test_parse_ops_file_skips_malformed_row_type(tmp_path: Path):
    ops_file = tmp_path / "ops.txt"
    ops_file.write_text("x|1|5-868.0||Procedure\n", encoding="utf-8")

    rows, counters = parse_ops_file(str(ops_file), 2025)
    assert rows == []
    assert counters.read == 1
    assert counters.accepted == 0
    assert counters.skipped == 1
