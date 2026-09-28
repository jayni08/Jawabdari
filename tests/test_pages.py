"""Smoke tests for the Streamlit pages using Streamlit's built-in AppTest.
Run with:  pytest -q
"""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import db  # noqa: E402

REGISTER_PAGE = str(ROOT / "pages" / "1_Register_Work.py")


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))


def load(path):
    at = AppTest.from_file(path, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def by_label(widgets, label_start):
    return next(w for w in widgets if w.label.startswith(label_start))


def work_count():
    conn = db.get_conn()
    n = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    conn.close()
    return n


def test_register_page_loads_and_seeds():
    at = load(REGISTER_PAGE)
    assert work_count() == 40                      # ensure_seeded() filled demo data
    assert "12 months" in at.info[0].value         # default cost 50 lakh -> 12 months
    assert len(at.dataframe) == 1                  # recent works table shown


def test_register_page_rejects_empty_name():
    at = load(REGISTER_PAGE)
    by_label(at.button, "Register work").click().run()
    assert any("name is required" in e.value for e in at.error)
    assert work_count() == 40                      # nothing saved


def test_register_page_creates_work_with_36_month_guarantee():
    at = load(REGISTER_PAGE)
    by_label(at.text_input, "Work name").input("SG Highway service road").run()
    by_label(at.number_input, "Cost").set_value(5_00_00_000).run()
    assert "36 months" in at.info[0].value         # live preview updated
    by_label(at.button, "Register work").click().run()
    assert not at.exception
    assert work_count() == 41
    assert any("W-0041" in m.value for m in at.success)
    assert any(b.label.startswith("⬇️ Download QR") for b in at.get("download_button"))
