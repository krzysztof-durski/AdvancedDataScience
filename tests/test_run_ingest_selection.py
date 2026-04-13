"""Tests for hospital file selection behavior in run_ingest."""

from pathlib import Path

from ingest.run_ingest import _select_hospital_files


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return path


def test_select_hospital_files_discovers_nested_jsons(tmp_path):
    top = _touch(tmp_path / "260100001-771111000-2024.json")
    nested_2024 = _touch(tmp_path / "json_2024" / "260100023-773287000-2024.json")
    nested_2023 = _touch(tmp_path / "json_2023" / "260100023-773287000-2023.json")
    _touch(tmp_path / "json_2024" / "bad-name.json")

    selected = _select_hospital_files(tmp_path, include_years=None, exclude_years=None)

    assert selected == sorted([top, nested_2024, nested_2023])


def test_select_hospital_files_include_years(tmp_path):
    _touch(tmp_path / "json_2024" / "260100023-773287000-2024.json")
    _touch(tmp_path / "json_2023" / "260100023-773287000-2023.json")

    selected = _select_hospital_files(tmp_path, include_years={2024}, exclude_years=None)

    assert len(selected) == 1
    assert selected[0].name.endswith("-2024.json")


def test_select_hospital_files_exclude_years(tmp_path):
    _touch(tmp_path / "json_2024" / "260100023-773287000-2024.json")
    _touch(tmp_path / "json_2023" / "260100023-773287000-2023.json")

    selected = _select_hospital_files(tmp_path, include_years=None, exclude_years={2023})

    assert len(selected) == 1
    assert selected[0].name.endswith("-2024.json")
