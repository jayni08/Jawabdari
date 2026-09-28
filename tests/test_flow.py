"""End-to-end story test: the full lifecycle of one public work, using only services.py.

Registered -> citizen reports defect -> contractor liable -> repaired -> verified (money saved)
-> deposit blocked during guarantee -> 31 months later guarantee ends -> deposit released.
Run with:  pytest -q
"""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import db  # noqa: E402
import services as s  # noqa: E402


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "flow.db"))
    db.init_db()
    connection = db.get_conn()
    yield connection
    connection.close()


def test_full_lifecycle_story(conn):
    today = s.local_today()
    completed = s.add_months(today, -6)          # finished 6 months ago
    later = s.add_months(today, 31)              # 31 months in the future

    # 1. Register contractor and a Rs 2 crore work -> 36-month guarantee
    cid = s.add_contractor(conn, "Gujarat Setu Nirman", "9800000999", "24ABCDE9999F1Z9", on_date=completed)
    wid = s.add_work(conn, "Sabarmati riverfront road", "Road", cid, 2_00_00_000, completed,
                     ward="Paldi", zone="West", today=today)
    work = s.get_work(conn, wid)
    assert work["dlp_months"] == 36
    assert work["dlp_end_date"] == s.add_months(completed, 36).isoformat()
    assert work["deposit_status"] == "Held"

    # 2. Citizen reports a defect -> contractor must repair free
    result = s.report_defect(conn, wid, "Citizen", "Asha Parmar", "Potholes after rain", "gu", on_date=today)
    assert result["liable_party"] == "Contractor"
    assert result["status"] == "Notice Sent"
    assert result["notice_deadline"] == (today + timedelta(days=config.NOTICE_DAYS)).isoformat()
    defect_id = result["defect_id"]

    # 3. Contractor repairs, engineer approves -> money saved
    repair_cost = 1_75_000
    s.mark_repaired(conn, defect_id, repair_cost, on_date=today + timedelta(days=2))
    s.verify_repair(conn, defect_id, approved=True, on_date=today + timedelta(days=3))
    assert s.get_defect(conn, defect_id)["status"] == "Closed"
    assert s.money_saved(conn) == repair_cost

    # 4. Deposit cannot be released while the guarantee is running
    allowed, reason = s.can_release_deposit(conn, wid, today + timedelta(days=4))
    assert not allowed and "active" in reason

    # 5. Jump 31 months ahead: guarantee has ended, nothing pending
    s.daily_refresh(conn, later)
    assert s.get_work(conn, wid)["lifecycle_stage"] == "Guarantee Ended"
    allowed, reason = s.can_release_deposit(conn, wid, later)
    assert allowed, reason

    ok, message = s.release_deposit(conn, wid, later)
    assert ok, message
    work = s.get_work(conn, wid)
    assert work["deposit_status"] == "Released"
    assert work["lifecycle_stage"] == "Guarantee Ended"

    # 6. Audit timeline has every step, in order
    events = [e["event_type"] for e in s.get_work_timeline(conn, wid)]
    assert events == [
        "WORK_REGISTERED",
        "NOTICE_SENT",
        "REPAIR_DONE",
        "REPAIR_VERIFIED",
        "GUARANTEE_ENDED",
        "DEPOSIT_RELEASED",
    ]
    # contractor kept a perfect record: 1 defect (-5) closed on time (+2) = 97
    score = s.contractor_scores(conn).set_index("contractor_id").loc[cid, "score"]
    assert score == 97
