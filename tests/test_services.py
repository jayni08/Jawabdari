"""Tests for services.py. Run with:  pytest -q"""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import db  # noqa: E402
import services as s  # noqa: E402

CRORE = 1_00_00_000


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """Fresh temporary database for every test."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    connection = db.get_conn()
    yield connection
    connection.close()


def make_work(conn, cost=50_00_000, completion="2026-01-01", today="2026-01-02"):
    """Create one contractor + one work, return (contractor_id, work_id)."""
    cid = s.add_contractor(conn, "Shree Ambica Infra", on_date=today)
    wid = s.add_work(conn, "CG Road resurfacing", "Road", cid, cost, completion,
                     ward="Navrangpura", today=today)
    return cid, wid


# ---------- DLP rules ----------

def test_dlp_exactly_one_crore_is_12_months():
    assert s.calc_dlp(CRORE, "2026-01-01") == (12, "2027-01-01")


def test_dlp_above_one_crore_is_36_months():
    assert s.calc_dlp(CRORE + 1, "2026-01-01") == (36, "2029-01-01")


def test_dlp_leap_year():
    # 29 Feb 2024 + 12 months -> 28 Feb 2025 (2025 has no 29 Feb)
    assert s.calc_dlp(10_00_000, "2024-02-29") == (12, "2025-02-28")
    # + 48 months would land on a leap year again, check helper directly
    assert s.add_months("2024-02-29", 48) == date(2028, 2, 29)


def test_dlp_rejects_zero_cost():
    with pytest.raises(ValueError):
        s.calc_dlp(0, "2026-01-01")


def test_is_under_guarantee_boundaries():
    assert s.is_under_guarantee("2027-01-01", "2027-01-01") is True
    assert s.is_under_guarantee("2027-01-01", "2027-01-02") is False


# ---------- registering ----------

def test_add_work_sets_guarantee_and_logs_event(conn):
    _, wid = make_work(conn)
    work = s.get_work(conn, wid)
    assert wid == "W-0001"
    assert work["dlp_end_date"] == "2027-01-01"
    assert work["deposit_status"] == "Held"
    assert work["lifecycle_stage"] == "Under Guarantee"
    assert work["security_deposit_rs"] == 2_50_000  # default 5% of 50 lakh
    assert s.get_work_timeline(conn, wid)[0]["event_type"] == "WORK_REGISTERED"


def test_add_work_rejects_future_completion(conn):
    cid = s.add_contractor(conn, "X Infra")
    with pytest.raises(ValueError):
        s.add_work(conn, "Road", "Road", cid, 100, "2030-01-01", today="2026-01-01")


def test_add_work_rejects_unknown_contractor(conn):
    with pytest.raises(ValueError):
        s.add_work(conn, "Road", "Road", "C-999", 100, "2026-01-01", today="2026-01-02")


# ---------- liability check ----------

def test_defect_on_last_dlp_day_is_contractor(conn):
    _, wid = make_work(conn)  # guarantee until 2027-01-01
    result = s.report_defect(conn, wid, "Citizen", "Ramesh", "Pothole", on_date="2027-01-01")
    assert result["liable_party"] == "Contractor"
    assert result["status"] == "Notice Sent"
    assert result["notice_deadline"] == "2027-01-08"


def test_defect_day_after_dlp_is_city(conn):
    _, wid = make_work(conn)
    result = s.report_defect(conn, wid, "Citizen", "Ramesh", "Pothole", on_date="2027-01-02")
    assert result["liable_party"] == "City"
    assert result["status"] == "Open"
    assert result["notice_deadline"] is None


def test_report_defect_needs_description(conn):
    _, wid = make_work(conn)
    with pytest.raises(ValueError):
        s.report_defect(conn, wid, "Citizen", "Ramesh", "   ", on_date="2026-02-01")


# ---------- repair flow ----------

def test_full_flow_closes_and_saves_money(conn):
    _, wid = make_work(conn)
    assert s.money_saved(conn) == 0
    did = s.report_defect(conn, wid, "Engineer", "JE Patel", "Crack", on_date="2026-03-01")["defect_id"]
    s.mark_repaired(conn, did, 45_000, on_date="2026-03-05")
    assert s.get_defect(conn, did)["status"] == "Repaired - Pending Verification"
    s.verify_repair(conn, did, approved=True, on_date="2026-03-06")
    assert s.get_defect(conn, did)["status"] == "Closed"
    assert s.money_saved(conn) == 45_000


def test_rejected_verification_goes_back_to_notice_sent(conn):
    _, wid = make_work(conn)
    did = s.report_defect(conn, wid, "Citizen", "Asha", "Pothole", on_date="2026-03-01")["defect_id"]
    s.mark_repaired(conn, did, 10_000, on_date="2026-03-03")
    s.verify_repair(conn, did, approved=False, on_date="2026-03-04")
    defect = s.get_defect(conn, did)
    assert defect["status"] == "Notice Sent"
    assert defect["notice_deadline"] == "2026-03-11"  # fresh 7-day deadline
    assert defect["repaired_on"] is None
    assert s.money_saved(conn) == 0


def test_cannot_verify_before_repair(conn):
    _, wid = make_work(conn)
    did = s.report_defect(conn, wid, "Citizen", "Asha", "Pothole", on_date="2026-03-01")["defect_id"]
    with pytest.raises(ValueError):
        s.verify_repair(conn, did, approved=True, on_date="2026-03-02")


def test_overdue_after_8_days_not_on_deadline(conn):
    _, wid = make_work(conn)
    did = s.report_defect(conn, wid, "Citizen", "Asha", "Pothole", on_date="2026-03-01")["defect_id"]
    assert s.refresh_overdue(conn, "2026-03-08") == 0  # deadline day: still fine
    assert s.get_defect(conn, did)["status"] == "Notice Sent"
    assert s.refresh_overdue(conn, "2026-03-09") == 1  # 8 days later: overdue
    assert s.get_defect(conn, did)["status"] == "Overdue"


# ---------- deposit ----------

def test_deposit_rules(conn):
    _, wid = make_work(conn)  # guarantee until 2027-01-01
    did = s.report_defect(conn, wid, "Citizen", "Asha", "Pothole", on_date="2026-12-20")["defect_id"]

    ok, reason = s.can_release_deposit(conn, wid, "2026-06-01")
    assert not ok and "active" in reason  # guarantee still running

    ok, reason = s.can_release_deposit(conn, wid, "2027-02-01")
    assert not ok and "unresolved" in reason  # guarantee ended but defect open

    s.mark_repaired(conn, did, 20_000, on_date="2026-12-24")
    s.verify_repair(conn, did, approved=True, on_date="2026-12-26")
    ok, _ = s.can_release_deposit(conn, wid, "2027-02-01")
    assert ok

    ok, _ = s.release_deposit(conn, wid, "2027-02-01")
    work = s.get_work(conn, wid)
    assert ok and work["deposit_status"] == "Released"
    assert work["lifecycle_stage"] == "Guarantee Ended"
    ok, reason = s.release_deposit(conn, wid, "2027-02-02")
    assert not ok and "already" in reason


# ---------- dashboard numbers ----------

def test_expiring_soon(conn):
    make_work(conn)  # ends 2027-01-01
    assert len(s.expiring_soon(conn, "2026-12-10", 30)) == 1
    assert s.expiring_soon(conn, "2026-12-10", 30)["days_left"].iloc[0] == 22
    assert len(s.expiring_soon(conn, "2026-10-01", 30)) == 0


def test_contractor_score_stays_between_0_and_100(conn):
    cid, wid = make_work(conn)
    df = s.contractor_scores(conn)
    assert df.loc[0, "score"] == 100  # no defects yet

    # 30 defects left overdue -> formula goes far below 0, must clamp to 0
    for _ in range(30):
        s.report_defect(conn, wid, "Citizen", "Asha", "Pothole", on_date="2026-02-01")
    s.refresh_overdue(conn, "2026-03-01")
    df = s.contractor_scores(conn)
    assert df.loc[0, "score"] == 0
    assert df.loc[0, "overdue"] == 30

    # a contractor with many on-time closures must not exceed 100
    cid2 = s.add_contractor(conn, "Good Builders")
    w2 = s.add_work(conn, "Drain", "Drain", cid2, 10_00_000, "2026-01-01", today="2026-01-02")
    for _ in range(10):
        d = s.report_defect(conn, w2, "Citizen", "A", "Leak", on_date="2026-02-01")["defect_id"]
        s.mark_repaired(conn, d, 1000, on_date="2026-02-02")
        s.verify_repair(conn, d, True, on_date="2026-02-03")
    score = s.contractor_scores(conn).set_index("contractor_id").loc[cid2, "score"]
    assert 0 <= score <= 100


def test_refresh_lifecycle_and_timeline_order(conn):
    _, wid = make_work(conn)
    s.report_defect(conn, wid, "Citizen", "Asha", "Pothole", on_date="2026-05-01")
    assert s.refresh_lifecycle(conn, "2027-01-02") == 1
    assert s.get_work(conn, wid)["lifecycle_stage"] == "Guarantee Ended"
    events = [e["event_type"] for e in s.get_work_timeline(conn, wid)]
    assert events == ["WORK_REGISTERED", "NOTICE_SENT", "GUARANTEE_ENDED"]


def test_format_inr():
    assert s.format_inr(1250000) == "Rs 12.5 lakh"
    assert s.format_inr(52000000) == "Rs 5.2 crore"
    assert s.format_inr(1_00_00_000) == "Rs 1 crore"
    assert s.format_inr(1_00_000) == "Rs 1 lakh"
    assert s.format_inr(45000) == "Rs 45,000"
    assert s.format_inr(0) == "Rs 0"
    assert s.format_inr(12_34_56_789) == "Rs 12.35 crore"


def test_local_today_is_india_date():
    from datetime import datetime, timedelta, timezone
    ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    assert s.local_today() == ist
