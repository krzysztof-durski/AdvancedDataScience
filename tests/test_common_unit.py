from pathlib import Path

from ingest.common import repo_root, resolve_repo_relative


def test_repo_root_contains_ingest_package():
    root = repo_root()
    assert (root / "ingest" / "common.py").is_file()


def test_resolve_repo_relative_keeps_absolute():
    p = Path("/tmp/abs-path-test-not-used")
    assert resolve_repo_relative(p) == str(p)


def test_resolve_repo_relative_joins_repo_root():
    resolved = resolve_repo_relative("ingest/common.py")
    assert Path(resolved).is_file()
    assert resolved.endswith("ingest/common.py")
