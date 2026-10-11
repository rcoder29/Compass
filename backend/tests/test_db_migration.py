"""
The pre-Compass database (stockmonitor.db) is renamed to compass.db on first start, keeping every row.
Run: python -m pytest tests/test_db_migration.py -v
"""
import os
import sqlite3

import pytest

import database


@pytest.fixture(autouse=True)
def real_resolution(monkeypatch):
    monkeypatch.delenv("COMPASS_DB_PATH", raising=False)       # these tests exercise the real resolution rules


def make_db(path, rows=("AAPL", "MSFT")):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE watchlist (id INTEGER PRIMARY KEY, symbol TEXT)")
    con.executemany("INSERT INTO watchlist (symbol) VALUES (?)", [(r,) for r in rows])
    con.commit()
    con.close()


def symbols(path):
    con = sqlite3.connect(path)
    try:
        return [r[0] for r in con.execute("SELECT symbol FROM watchlist ORDER BY id")]
    finally:
        con.close()


def test_the_test_suite_never_points_at_the_real_database():
    here = os.path.dirname(os.path.abspath(database.__file__))
    assert not os.path.abspath(database.DB_PATH).startswith(here + os.sep)


def test_renames_the_legacy_file_and_keeps_every_row(tmp_path):
    make_db(tmp_path / "stockmonitor.db")
    path = database.resolve_db_path(str(tmp_path))
    assert path == str(tmp_path / "compass.db")
    assert not (tmp_path / "stockmonitor.db").exists()
    assert symbols(path) == ["AAPL", "MSFT"]


def test_moves_sqlite_sidecar_files_with_it(tmp_path):
    make_db(tmp_path / "stockmonitor.db")
    for suffix in ("-wal", "-shm", "-journal"):
        (tmp_path / f"stockmonitor.db{suffix}").write_bytes(b"x")
    database.resolve_db_path(str(tmp_path))
    for suffix in ("-wal", "-shm", "-journal"):
        assert (tmp_path / f"compass.db{suffix}").exists() and not (tmp_path / f"stockmonitor.db{suffix}").exists()


def test_is_idempotent(tmp_path):
    make_db(tmp_path / "stockmonitor.db")
    first = database.resolve_db_path(str(tmp_path))
    assert database.resolve_db_path(str(tmp_path)) == first and symbols(first) == ["AAPL", "MSFT"]


def test_existing_compass_db_wins_and_the_old_file_is_left_alone(tmp_path):
    make_db(tmp_path / "compass.db", rows=("NEW",))
    make_db(tmp_path / "stockmonitor.db", rows=("OLD",))
    path = database.resolve_db_path(str(tmp_path))
    assert symbols(path) == ["NEW"] and symbols(tmp_path / "stockmonitor.db") == ["OLD"]


def test_fresh_install_uses_the_new_name_and_creates_nothing(tmp_path):
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    path = database.resolve_db_path(str(fresh))
    assert path == str(fresh / "compass.db") and list(fresh.iterdir()) == []


def test_falls_back_to_the_old_file_if_the_rename_fails(tmp_path, monkeypatch):
    make_db(tmp_path / "stockmonitor.db")

    def boom(src, dst):
        raise PermissionError("read-only")
    monkeypatch.setattr(database.os, "replace", boom)
    path = database.resolve_db_path(str(tmp_path))
    assert path == str(tmp_path / "stockmonitor.db") and symbols(path) == ["AAPL", "MSFT"]      # never an empty database beside real data


def test_env_override_wins_and_moves_nothing(tmp_path, monkeypatch):
    make_db(tmp_path / "stockmonitor.db")
    monkeypatch.setenv("COMPASS_DB_PATH", str(tmp_path / "custom.db"))
    assert database.resolve_db_path(str(tmp_path)) == str(tmp_path / "custom.db")
    assert (tmp_path / "stockmonitor.db").exists()
