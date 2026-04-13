"""Tests for processed-file tracking helpers."""

from ingest import tracking


class _FakeCursor:
    def __init__(self, row):
        self._row = row
        self.executed = []
        self.closed = False

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return self._row

    def close(self):
        self.closed = True


class _FakeConn:
    def __init__(self, row):
        self.cursor_obj = _FakeCursor(row)

    def cursor(self):
        return self.cursor_obj


def test_should_process_file_when_no_previous_row(monkeypatch):
    monkeypatch.setattr(
        tracking,
        "compute_file_signature",
        lambda _: {"mtime_ns": "1", "size_bytes": "2", "sha256": "abc"},
    )
    conn = _FakeConn(row=None)

    assert tracking.should_process_file("x.json", "hospital", conn) is True


def test_should_not_process_unchanged_file(monkeypatch):
    monkeypatch.setattr(
        tracking,
        "compute_file_signature",
        lambda _: {"mtime_ns": "1", "size_bytes": "2", "sha256": "abc"},
    )
    conn = _FakeConn(row=("1", "2", "abc"))

    assert tracking.should_process_file("x.json", "hospital", conn) is False


def test_should_process_changed_file(monkeypatch):
    monkeypatch.setattr(
        tracking,
        "compute_file_signature",
        lambda _: {"mtime_ns": "1", "size_bytes": "2", "sha256": "abc"},
    )
    conn = _FakeConn(row=("9", "2", "abc"))

    assert tracking.should_process_file("x.json", "hospital", conn) is True


def test_mark_processed_file_persists_signature(monkeypatch):
    monkeypatch.setattr(
        tracking,
        "compute_file_signature",
        lambda _: {"mtime_ns": "123", "size_bytes": "456", "sha256": "deadbeef"},
    )
    conn = _FakeConn(row=None)

    tracking.mark_processed_file("x.json", "hospital", conn)

    _, params = conn.cursor_obj.executed[0]
    assert params == ("hospital", "x.json", 123, 456, "deadbeef")
