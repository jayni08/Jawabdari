"""Business logic for Jawabdari.

Every rule of the app lives here as a plain function:
- no Streamlit imports, so everything can be unit-tested with pytest
- later, these same functions can be exposed as a REST API (e.g. FastAPI)

Conventions
- Functions that change data take an open connection `conn` and COMMIT before returning.
- Dates may be passed as datetime.date or 'YYYY-MM-DD' strings; they are stored as ISO strings.
- Invalid input raises ValueError with a human-readable message (pages show it with st.error).
"""

import calendar
import html
import re
from datetime import date, datetime, timedelta, timezone

import pandas as pd

import config
import db

ASSET_TYPES = ["Road", "Bridge", "Drain", "Building", "Streetlight"]
REPORTERS = ["Citizen", "Engineer"]

# Defect statuses that mean "work is still pending" -> deposit must stay held
UNRESOLVED_STATUSES = ("Open", "Notice Sent", "Overdue", "Repaired - Pending Verification")


# ---------------------------------------------------------------------------
# Small date helpers
# ---------------------------------------------------------------------------

def local_today():
    """Today's date in India (IST, UTC+5:30), whatever time zone the server runs in.
    Streamlit Cloud runs on UTC, so local_today() would be a day behind before 5:30am IST."""
    offset = timezone(timedelta(minutes=config.UTC_OFFSET_MINUTES))
    return datetime.now(offset).date()


def to_date(value):
    """Accept a date or a 'YYYY-MM-DD' string and return a date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def iso(value):
    """Return a date as a 'YYYY-MM-DD' string."""
    return to_date(value).isoformat()


def add_months(start, months):
    """Add calendar months to a date. If the day doesn't exist (e.g. 29 Feb -> 2025),
    use the last day of that month instead: 2024-02-29 + 12 months = 2025-02-28."""
    start = to_date(start)
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(start.day, last_day))


def log_event(conn, work_id, event_type, details, on_date):
    """Append a row to the audit log (we never update or delete events)."""
    conn.execute(
        "INSERT INTO events (work_id, event_type, details, created_at) VALUES (?, ?, ?, ?)",
        (work_id, event_type, details, iso(on_date)),
    )


# ---------------------------------------------------------------------------
# 1-2. Guarantee (DLP) rules
# ---------------------------------------------------------------------------

def calc_dlp(cost_rs, completion_date):
    """AMC rule: cost up to Rs 1 crore -> 12 months DLP, above Rs 1 crore -> 36 months.
    Returns (dlp_months, dlp_end_date as 'YYYY-MM-DD')."""
    if cost_rs is None or cost_rs <= 0:
        raise ValueError("Cost must be greater than 0.")
    months = config.DLP_MONTHS_SMALL if cost_rs <= config.DLP_THRESHOLD_RS else config.DLP_MONTHS_LARGE
    end_date = add_months(completion_date, months)
    return months, end_date.isoformat()


def is_under_guarantee(dlp_end_date, on_date):
    """True if on_date is on or before the DLP end date (the end date itself is still covered)."""
    return to_date(on_date) <= to_date(dlp_end_date)


def safe_html(value):
    """Escape text typed by users before putting it inside HTML (stops <script> etc.)."""
    return html.escape("" if value is None else str(value))


def safe_md(value):
    """Escape Markdown symbols in user text so names like '*Best* Infra' show literally."""
    return re.sub(r"([\\`*_{}\[\]()#+\-!|>~<])", r"\\\1", "" if value is None else str(value))


def format_inr(amount):
    """Indian-style money text: 45000 -> 'Rs 45,000', 1250000 -> 'Rs 12.5 lakh',
    52000000 -> 'Rs 5.2 crore'."""
    amount = int(amount or 0)

    def short(value):
        # up to 2 decimals, without trailing zeros: 12.50 -> 12.5, 1.00 -> 1
        return f"{value:.2f}".rstrip("0").rstrip(".")

    if amount >= 1_00_00_000:
        return f"Rs {short(amount / 1_00_00_000)} crore"
    if amount >= 1_00_000:
        return f"Rs {short(amount / 1_00_000)} lakh"
    return f"Rs {amount:,}"


# ---------------------------------------------------------------------------
# Read helpers used by other functions and by the pages
# ---------------------------------------------------------------------------

def get_work(conn, work_id):
    """Return one work joined with its contractor's name, as a dict (or None)."""
    row = conn.execute(
        """SELECT w.*, c.name AS contractor_name
           FROM works w JOIN contractors c ON c.id = w.contractor_id
           WHERE w.id = ?""",
        (work_id,),
    ).fetchone()
    return dict(row) if row else None


def get_defect(conn, defect_id):
    """Return one defect as a dict (or None)."""
    row = conn.execute("SELECT * FROM defects WHERE id = ?", (defect_id,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# 3. Registering contractors and works
# ---------------------------------------------------------------------------

def add_contractor(conn, name, phone=None, gst_no=None, on_date=None):
    """Insert a contractor and return its new id (e.g. 'C-004')."""
    if not name or not name.strip():
        raise ValueError("Contractor name is required.")
    new_id = db.next_id("contractors", "C", 3, conn)
    conn.execute(
        "INSERT INTO contractors (id, name, phone, gst_no, created_at) VALUES (?, ?, ?, ?, ?)",
        (new_id, name.strip(), phone, gst_no, iso(on_date or local_today())),
    )
    conn.commit()
    return new_id


def add_work(conn, name, asset_type, contractor_id, cost_rs, completion_date,
             ward=None, zone=None, latitude=None, longitude=None,
             security_deposit_rs=None, today=None):
    """Register a completed public work, calculate its guarantee, hold the deposit.

    If security_deposit_rs is not given, we assume 5% of the cost (a common tender norm).
    Returns the new work id (e.g. 'W-0012').
    """
    today = to_date(today or local_today())

    # --- validation (friendly messages for the UI) ---
    if not name or not name.strip():
        raise ValueError("Work name is required.")
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"Asset type must be one of: {', '.join(ASSET_TYPES)}.")
    if to_date(completion_date) > today:
        raise ValueError("Completion date cannot be in the future.")
    if conn.execute("SELECT 1 FROM contractors WHERE id = ?", (contractor_id,)).fetchone() is None:
        raise ValueError(f"Contractor {contractor_id} does not exist.")

    dlp_months, dlp_end = calc_dlp(cost_rs, completion_date)
    if security_deposit_rs is None:
        security_deposit_rs = round(cost_rs * 0.05)

    new_id = db.next_id("works", "W", 4, conn)
    conn.execute(
        """INSERT INTO works (id, name, asset_type, ward, zone, latitude, longitude,
                              contractor_id, cost_rs, completion_date, dlp_months, dlp_end_date,
                              security_deposit_rs, deposit_status, lifecycle_stage, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Held', 'Under Guarantee', ?)""",
        (new_id, name.strip(), asset_type, ward, zone, latitude, longitude, contractor_id,
         int(cost_rs), iso(completion_date), dlp_months, dlp_end, int(security_deposit_rs), iso(today)),
    )
    log_event(conn, new_id, "WORK_REGISTERED",
              f"Completed {iso(completion_date)}; guarantee {dlp_months} months until {dlp_end}; "
              f"deposit Rs {int(security_deposit_rs):,} held", completion_date)
    conn.commit()
    return new_id


# ---------------------------------------------------------------------------
# 4-7. Defects: report -> repair -> verify, and overdue checks
# ---------------------------------------------------------------------------

def report_defect(conn, work_id, reported_by, reporter_name, description, language="en",
                  on_date=None, photo_path=None):
    """Record a defect and run the LIABILITY CHECK.

    Under guarantee  -> Contractor must repair free: status 'Notice Sent', deadline = +NOTICE_DAYS
    Guarantee ended  -> City repairs: status 'Open'
    Returns a dict with the decision and a message for the user.
    """
    on_date = to_date(on_date or local_today())
    work = get_work(conn, work_id)
    if work is None:
        raise ValueError(f"Work {work_id} not found.")
    if reported_by not in REPORTERS:
        raise ValueError("Reported by must be 'Citizen' or 'Engineer'.")
    if not description or not description.strip():
        raise ValueError("Please describe the problem.")

    defect_id = db.next_id("defects", "D", 4, conn)

    if work["lifecycle_stage"] != "Decommissioned" and is_under_guarantee(work["dlp_end_date"], on_date):
        liable, status = "Contractor", "Notice Sent"
        deadline = (on_date + timedelta(days=config.NOTICE_DAYS)).isoformat()
        event_type = "NOTICE_SENT"
        message = (f"Under guarantee until {work['dlp_end_date']}. {work['contractor_name']} must "
                   f"repair FREE by {deadline}. Notice {defect_id}.")
    else:
        liable, status, deadline = "City", "Open", None
        event_type = "CITY_MAINTENANCE"
        message = (f"Guarantee ended on {work['dlp_end_date']}. Added to city maintenance queue "
                   f"as {defect_id}.")

    conn.execute(
        """INSERT INTO defects (id, work_id, reported_by, reporter_name, description, photo_path,
                                language, reported_on, liable_party, status, notice_deadline,
                                repair_cost_rs)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
        (defect_id, work_id, reported_by, reporter_name, description.strip(), photo_path,
         language, on_date.isoformat(), liable, status, deadline),
    )
    log_event(conn, work_id, event_type, f"{defect_id}: {description.strip()} ({reported_by})", on_date)
    conn.commit()

    return {
        "defect_id": defect_id,
        "work_id": work_id,
        "liable_party": liable,
        "status": status,
        "notice_deadline": deadline,
        "dlp_end_date": work["dlp_end_date"],
        "contractor_name": work["contractor_name"],
        "under_guarantee": liable == "Contractor",
        "message": message,
    }


def mark_repaired(conn, defect_id, repair_cost_rs, on_date=None):
    """Contractor (or city team) says the repair is done -> waits for engineer verification.
    repair_cost_rs = estimated cost of the repair (what the city would otherwise have paid)."""
    on_date = to_date(on_date or local_today())
    defect = get_defect(conn, defect_id)
    if defect is None:
        raise ValueError(f"Defect {defect_id} not found.")
    if defect["status"] not in ("Open", "Notice Sent", "Overdue"):
        raise ValueError(f"Defect {defect_id} cannot be marked repaired from status '{defect['status']}'.")
    if repair_cost_rs is None or repair_cost_rs < 0:
        raise ValueError("Repair cost cannot be negative.")

    conn.execute(
        """UPDATE defects SET status = 'Repaired - Pending Verification',
                              repair_cost_rs = ?, repaired_on = ?
           WHERE id = ?""",
        (int(repair_cost_rs), on_date.isoformat(), defect_id),
    )
    log_event(conn, defect["work_id"], "REPAIR_DONE",
              f"{defect_id} repaired, cost Rs {int(repair_cost_rs):,}", on_date)
    conn.commit()


def verify_repair(conn, defect_id, approved, on_date=None):
    """Engineer checks the repair.
    Approved -> Closed.  Rejected -> back to 'Notice Sent' with a fresh deadline
    (or back to 'Open' if the city was liable)."""
    on_date = to_date(on_date or local_today())
    defect = get_defect(conn, defect_id)
    if defect is None:
        raise ValueError(f"Defect {defect_id} not found.")
    if defect["status"] != "Repaired - Pending Verification":
        raise ValueError(f"Defect {defect_id} is not waiting for verification.")

    if approved:
        conn.execute(
            "UPDATE defects SET status = 'Closed', verified_on = ? WHERE id = ?",
            (on_date.isoformat(), defect_id),
        )
        log_event(conn, defect["work_id"], "REPAIR_VERIFIED", f"{defect_id} closed", on_date)
    else:
        if defect["liable_party"] == "Contractor":
            new_status = "Notice Sent"
            new_deadline = (on_date + timedelta(days=config.NOTICE_DAYS)).isoformat()
        else:
            new_status, new_deadline = "Open", None
        conn.execute(
            """UPDATE defects SET status = ?, notice_deadline = ?, repaired_on = NULL
               WHERE id = ?""",
            (new_status, new_deadline, defect_id),
        )
        log_event(conn, defect["work_id"], "REPAIR_REJECTED",
                  f"{defect_id} rejected; back to {new_status}", on_date)
    conn.commit()


def refresh_overdue(conn, today=None):
    """Mark every 'Notice Sent' defect whose deadline has passed as 'Overdue'.
    Deadline day itself is NOT overdue. Returns how many were changed."""
    today = iso(today or local_today())
    rows = conn.execute(
        "SELECT id, work_id FROM defects WHERE status = 'Notice Sent' AND notice_deadline < ?",
        (today,),
    ).fetchall()
    for row in rows:
        conn.execute("UPDATE defects SET status = 'Overdue' WHERE id = ?", (row["id"],))
        log_event(conn, row["work_id"], "NOTICE_OVERDUE", f"{row['id']} not repaired by deadline", today)
    conn.commit()
    return len(rows)


def refresh_lifecycle(conn, today=None):
    """Move works whose guarantee has ended from 'Under Guarantee' to 'Guarantee Ended'.
    (The deposit stays Held until accounts releases it.) Returns how many were changed."""
    today = iso(today or local_today())
    rows = conn.execute(
        "SELECT id, dlp_end_date FROM works WHERE lifecycle_stage = 'Under Guarantee' AND dlp_end_date < ?",
        (today,),
    ).fetchall()
    for row in rows:
        conn.execute("UPDATE works SET lifecycle_stage = 'Guarantee Ended' WHERE id = ?", (row["id"],))
        log_event(conn, row["id"], "GUARANTEE_ENDED", f"Guarantee ended on {row['dlp_end_date']}",
                  row["dlp_end_date"])
    conn.commit()
    return len(rows)


def daily_refresh(conn, today=None):
    """Run all automatic status updates. Pages call this when they load."""
    return {"overdue": refresh_overdue(conn, today), "ended": refresh_lifecycle(conn, today)}


# ---------------------------------------------------------------------------
# 8-9. Security deposit
# ---------------------------------------------------------------------------

def can_release_deposit(conn, work_id, today=None):
    """Deposit can be released only if the guarantee has ENDED and no defect is unresolved.
    Returns (True/False, reason)."""
    today = to_date(today or local_today())
    work = get_work(conn, work_id)
    if work is None:
        return False, f"Work {work_id} not found."
    if work["deposit_status"] != "Held":
        return False, f"Deposit is already {work['deposit_status']}."
    if is_under_guarantee(work["dlp_end_date"], today):
        return False, f"Guarantee is active until {work['dlp_end_date']}. Deposit must stay held."

    placeholders = ",".join("?" * len(UNRESOLVED_STATUSES))
    pending = conn.execute(
        f"SELECT COUNT(*) FROM defects WHERE work_id = ? AND status IN ({placeholders})",
        (work_id, *UNRESOLVED_STATUSES),
    ).fetchone()[0]
    if pending > 0:
        return False, f"{pending} defect(s) still unresolved. Deposit must stay held."
    return True, "Guarantee ended and no unresolved defects. Deposit can be released."


def release_deposit(conn, work_id, today=None):
    """Release the deposit if allowed. Returns (True/False, reason)."""
    today = to_date(today or local_today())
    allowed, reason = can_release_deposit(conn, work_id, today)
    if not allowed:
        return False, reason
    work = get_work(conn, work_id)
    conn.execute(
        "UPDATE works SET deposit_status = 'Released', lifecycle_stage = 'Guarantee Ended' WHERE id = ?",
        (work_id,),
    )
    log_event(conn, work_id, "DEPOSIT_RELEASED",
              f"Deposit Rs {work['security_deposit_rs']:,} released", today)
    conn.commit()
    return True, "Deposit released."


# ---------------------------------------------------------------------------
# 10-13. Dashboard numbers
# ---------------------------------------------------------------------------

def expiring_soon(conn, today=None, days=None):
    """Works whose guarantee ends within `days` from today -> inspect them BEFORE expiry,
    because any defect found after expiry becomes the city's cost. Returns a DataFrame."""
    today = to_date(today or local_today())
    days = config.EXPIRY_ALERT_DAYS if days is None else days
    limit = today + timedelta(days=days)
    df = pd.read_sql_query(
        """SELECT w.id, w.name, w.asset_type, w.ward, c.name AS contractor,
                  w.dlp_end_date, w.security_deposit_rs
           FROM works w JOIN contractors c ON c.id = w.contractor_id
           WHERE w.dlp_end_date BETWEEN ? AND ? AND w.lifecycle_stage != 'Decommissioned'
           ORDER BY w.dlp_end_date""",
        conn,
        params=(today.isoformat(), limit.isoformat()),
    )
    df["days_left"] = [(to_date(d) - today).days for d in df["dlp_end_date"]]
    return df


def contractor_scores(conn):
    """Reliability score per contractor (0-100), based only on defects they were liable for.

    Formula:
        start at 100
        -5  for every defect in their guarantee period  (poor quality work)
        -15 for every overdue notice (still overdue, or repaired after the deadline)
        +2  for every defect closed on time              (reward for responsiveness)
        then clamp between 0 and 100.
    """
    contractors = conn.execute("SELECT id, name FROM contractors ORDER BY id").fetchall()
    rows = []
    for c in contractors:
        works = conn.execute("SELECT COUNT(*) FROM works WHERE contractor_id = ?", (c["id"],)).fetchone()[0]
        defects = conn.execute(
            """SELECT d.status, d.reported_on, d.notice_deadline, d.repaired_on
               FROM defects d JOIN works w ON w.id = d.work_id
               WHERE w.contractor_id = ? AND d.liable_party = 'Contractor'""",
            (c["id"],),
        ).fetchall()

        total = len(defects)
        closed = sum(1 for d in defects if d["status"] == "Closed")
        late_closed = sum(1 for d in defects if d["status"] == "Closed" and d["repaired_on"]
                          and d["notice_deadline"] and d["repaired_on"] > d["notice_deadline"])
        overdue = sum(1 for d in defects if d["status"] == "Overdue") + late_closed
        on_time = closed - late_closed
        repair_days = [(to_date(d["repaired_on"]) - to_date(d["reported_on"])).days
                       for d in defects if d["repaired_on"]]
        avg_days = round(sum(repair_days) / len(repair_days), 1) if repair_days else None

        score = 100 - 5 * total - 15 * overdue + 2 * on_time
        score = max(0, min(100, score))

        rows.append({
            "contractor_id": c["id"], "contractor": c["name"], "works": works,
            "defects": total, "closed": closed, "overdue": overdue,
            "avg_days_to_repair": avg_days, "score": score,
        })
    return pd.DataFrame(rows, columns=["contractor_id", "contractor", "works", "defects", "closed",
                                       "overdue", "avg_days_to_repair", "score"])


def money_saved(conn):
    """Rs the city did NOT pay: repair costs of closed defects the contractor had to fix free."""
    total = conn.execute(
        "SELECT COALESCE(SUM(repair_cost_rs), 0) FROM defects WHERE liable_party = 'Contractor' AND status = 'Closed'"
    ).fetchone()[0]
    return int(total)


def get_work_timeline(conn, work_id):
    """All events for one work, oldest first, as a list of dicts."""
    rows = conn.execute(
        "SELECT event_type, details, created_at FROM events WHERE work_id = ? ORDER BY created_at, id",
        (work_id,),
    ).fetchall()
    return [dict(r) for r in rows]
