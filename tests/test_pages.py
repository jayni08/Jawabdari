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


# ---------- Stage 6: Report Defect ----------

REPORT_PAGE = str(ROOT / "pages" / "2_Report_Defect.py")


def load_report(work_id=None):
    at = AppTest.from_file(REPORT_PAGE, default_timeout=60)
    if work_id:
        at.query_params["work_id"] = work_id
    at.run()
    assert not at.exception, at.exception
    return at


def card_text(at):
    return " ".join(m.value for m in at.markdown)


def test_report_page_needs_a_work():
    at = load_report()
    at.button[0].click().run()
    assert any("select a work" in e.value for e in at.error)


def test_report_page_preselects_from_url():
    at = load_report("W-0003")
    assert at.selectbox[0].value == "W-0003"


def test_report_other_needs_description():
    at = load_report("W-0001")
    by_label(at.radio, "What is the problem").set_value("other").run()
    at.button[0].click().run()
    assert any("describe the problem" in e.value for e in at.error)


def test_report_under_guarantee_goes_to_contractor():
    at = load_report("W-0001")          # seed: guarantee ends in 3 days
    at.button[0].click().run()
    assert not at.exception
    text = card_text(at)
    assert "must repair FREE" in text and "Notice ID: D-" in text


def test_report_old_work_goes_to_city():
    at = load_report("W-0007")          # seed: guarantee ended years ago
    at.button[0].click().run()
    assert "city maintenance queue" in card_text(at)


def test_report_in_gujarati():
    at = load_report("W-0001")
    at.radio[0].set_value("gu").run()
    assert at.title[0].value.endswith("સમસ્યા નોંધાવો")
    at.button[0].click().run()
    assert "મફત સમારકામ" in card_text(at)


# ---------- Stage 7: Contractor Portal ----------

PORTAL_PAGE = str(ROOT / "pages" / "3_Contractor_Portal.py")


def load_portal():
    at = AppTest.from_file(PORTAL_PAGE, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def defect_status(defect_id):
    conn = db.get_conn()
    status = conn.execute("SELECT status FROM defects WHERE id = ?", (defect_id,)).fetchone()[0]
    conn.close()
    return status


def test_portal_contractor_can_mark_repaired():
    at = load_portal()
    by_label(at.selectbox, "Log in as contractor").set_value("C-006").run()  # weak contractor
    repair_buttons = [b for b in at.button if b.key and b.key.startswith("repair_")]
    assert repair_buttons, "weak contractor should have open notices"
    defect_id = repair_buttons[0].key.split("_", 1)[1]
    repair_buttons[0].click().run()
    assert not at.exception
    assert defect_status(defect_id) == "Repaired - Pending Verification"


def test_portal_engineer_approve_and_reject():
    at = load_portal()
    approve = [b for b in at.button if b.key and b.key.startswith("approve_")]
    assert len(approve) >= 2                     # seed has 2 pending verification
    first = approve[0].key.split("_", 1)[1]
    approve[0].click().run()
    assert defect_status(first) == "Closed"
    reject = [b for b in at.button if b.key and b.key.startswith("reject_")]
    second = reject[0].key.split("_", 1)[1]
    reject[0].click().run()
    assert defect_status(second) in ("Notice Sent", "Open")


def test_portal_deposit_release_rules():
    import services as s
    from datetime import date
    at = load_portal()
    conn = db.get_conn()
    held = [r[0] for r in conn.execute("SELECT id FROM works WHERE deposit_status='Held'")]
    ok_ids = [w for w in held if s.can_release_deposit(conn, w, date.today())[0]]
    blocked = [w for w in held if not s.can_release_deposit(conn, w, date.today())[0]]
    conn.close()
    assert ok_ids and blocked

    select = by_label(at.selectbox, "Select a work")
    select.set_value(blocked[0]).run()
    assert by_label(at.button, "Release deposit").disabled

    by_label(at.selectbox, "Select a work").set_value(ok_ids[0]).run()
    release = by_label(at.button, "Release deposit")
    assert not release.disabled
    release.click().run()
    conn = db.get_conn()
    status = conn.execute("SELECT deposit_status FROM works WHERE id=?", (ok_ids[0],)).fetchone()[0]
    conn.close()
    assert status == "Released"


# ---------- Stage 8: Public Board ----------

BOARD_PAGE = str(ROOT / "pages" / "4_Public_Board.py")


def load_board(work_id=None):
    at = AppTest.from_file(BOARD_PAGE, default_timeout=60)
    if work_id:
        at.query_params["work_id"] = work_id
    at.run()
    assert not at.exception, at.exception
    return at


def all_markdown(at):
    return " ".join(m.value for m in at.markdown)


def test_board_without_id_shows_picker():
    at = load_board()
    assert len(at.selectbox) == 1


def test_board_under_guarantee():
    at = load_board("W-0001")
    text = all_markdown(at)
    assert "UNDER GUARANTEE until" in text and "Built by" in text and "★" in text


def test_board_guarantee_ended():
    at = load_board("W-0007")
    assert "GUARANTEE ENDED" in all_markdown(at)


def test_board_unknown_id_is_friendly():
    at = load_board("W-9999")
    assert at.warning and len(at.selectbox) == 1


def test_board_in_gujarati():
    at = load_board("W-0001")
    at.radio[0].set_value("gu").run()
    assert not at.exception
    assert "ગેરંટીમાં" in all_markdown(at)


# ---------- Stage 9: Dashboard ----------

DASHBOARD = str(ROOT / "app.py")


def test_dashboard_loads_with_kpis_and_charts():
    at = AppTest.from_file(DASHBOARD, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert len(at.metric) == 5
    labels = [m.label for m in at.metric]
    assert any("Money saved" in label for label in labels)
    assert any("₹" in str(m.value) for m in at.metric)
    assert len(at.get("plotly_chart")) == 2       # bar chart + map
    assert len(at.dataframe) == 2                 # expiring table + leaderboard
