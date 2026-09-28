"""Tests for db.py. Run with:  pytest -q"""

import sqlite3
import sys
from pathlib import Path

import pytest

# Make the project root importable when running pytest from the project folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import db  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own fresh database file."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


def add_contractor(conn, cid="C-001"):
    conn.execute("INSERT INTO contractors (id, name) VALUES (?, ?)", (cid, "Shree Ambica Infra"))


def add_work(conn, wid="W-0001", contractor_id="C-001"):
    conn.execute(
        """INSERT INTO works (id, name, asset_type, contractor_id, cost_rs,
                              completion_date, dlp_months, dlp_end_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (wid, "CG Road resurfacing", "Road", contractor_id, 5000000, "2026-01-01", 12, "2027-01-01"),
    )


def test_all_tables_exist():
    assert db.table_names() == ["contractors", "defects", "events", "works"]


def test_init_db_twice_is_safe():
    db.init_db()
    assert len(db.table_names()) == 4


def test_foreign_key_is_enforced():
    conn = db.get_conn()
    with pytest.raises(sqlite3.IntegrityError):
        add_work(conn, contractor_id="C-999")  # contractor does not exist
    conn.close()


def test_invalid_asset_type_rejected():
    conn = db.get_conn()
    add_contractor(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO works (id, name, asset_type, contractor_id, cost_rs,
                                  completion_date, dlp_months, dlp_end_date)
               VALUES ('W-0001', 'x', 'Spaceship', 'C-001', 100, '2026-01-01', 12, '2027-01-01')"""
        )
    conn.close()


def test_next_id_starts_at_one_and_increments():
    assert db.next_id("works", "W", 4) == "W-0001"
    conn = db.get_conn()
    add_contractor(conn)
    add_work(conn, "W-0001")
    add_work(conn, "W-0009")
    conn.commit()
    conn.close()
    assert db.next_id("works", "W", 4) == "W-0010"
    assert db.next_id("contractors", "C", 3) == "C-002"


def test_next_id_rejects_unknown_table():
    with pytest.raises(ValueError):
        db.next_id("users; DROP TABLE works", "X", 3)


def test_reset_db_clears_data():
    conn = db.get_conn()
    add_contractor(conn)
    conn.commit()
    conn.close()
    db.reset_db()
    conn = db.get_conn()
    count = conn.execute("SELECT COUNT(*) FROM contractors").fetchone()[0]
    conn.close()
    assert count == 0
