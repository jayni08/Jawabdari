"""Realistic sample data for Jawabdari (Ahmedabad).

Run:  python seed.py        -> wipes the database and creates fresh demo data
From app.py: ensure_seeded() -> only seeds when the database is empty

Only services.py functions are used to insert data, so all rules (DLP, events,
liability check) are applied exactly as in the real app.
The data is built so every demo case is always present, whatever today's date is.
"""

import random
import threading
from datetime import timedelta

import db
import services as s

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

CONTRACTORS = [
    "Shree Ambica Infra",
    "Patel Brothers Constructions",
    "Navkar Buildcon",            # weak performer (see BAD_CONTRACTORS)
    "Sardar Infraprojects",
    "Umiya Civil Works",
    "Jay Bhavani Road Carriers",  # weak performer
    "Swaminarayan Engineers",
    "Gujarat Setu Nirman",
]
BAD_CONTRACTORS = ["C-003", "C-006"]  # get the overdue / late defects

# Approximate ward centres (lat, long) and AMC zone
WARDS = {
    "Navrangpura": (23.0365, 72.5611, "West"),
    "Maninagar":   (22.9962, 72.6030, "South"),
    "Bopal":       (23.0330, 72.4700, "South West"),
    "Vastrapur":   (23.0370, 72.5290, "West"),
    "Naroda":      (23.0680, 72.6530, "North"),
    "Chandkheda":  (23.1090, 72.5850, "North"),
    "Odhav":       (23.0250, 72.6600, "East"),
    "Paldi":       (23.0120, 72.5630, "West"),
}

# 40 public works: (name, asset type, ward)
WORKS = [
    ("CG Road resurfacing phase 2", "Road", "Navrangpura"),
    ("Swastik char rasta junction road", "Road", "Navrangpura"),
    ("Navrangpura bus stand storm drain", "Drain", "Navrangpura"),
    ("Law Garden LED streetlights", "Streetlight", "Navrangpura"),
    ("Navrangpura ward office building", "Building", "Navrangpura"),
    ("Maninagar railway crossing road", "Road", "Maninagar"),
    ("Kankaria lake periphery road", "Road", "Maninagar"),
    ("Maninagar stormwater drain line", "Drain", "Maninagar"),
    ("Jawahar chowk streetlight upgrade", "Streetlight", "Maninagar"),
    ("Maninagar urban health centre", "Building", "Maninagar"),
    ("Bopal-Ghuma main road widening", "Road", "Bopal"),
    ("Stormwater drain Bopal", "Drain", "Bopal"),
    ("Bopal lake bridge approach", "Bridge", "Bopal"),
    ("Bopal smart streetlights", "Streetlight", "Bopal"),
    ("Bopal community hall", "Building", "Bopal"),
    ("Vastrapur lake ring road", "Road", "Vastrapur"),
    ("IIM road footpath and carriageway", "Road", "Vastrapur"),
    ("Vastrapur drain desilting chamber", "Drain", "Vastrapur"),
    ("Vastrapur streetlight cabling", "Streetlight", "Vastrapur"),
    ("Vastrapur municipal school building", "Building", "Vastrapur"),
    ("Naroda GIDC approach road", "Road", "Naroda"),
    ("Naroda Patiya internal roads", "Road", "Naroda"),
    ("Naroda canal culvert bridge", "Bridge", "Naroda"),
    ("Naroda stormwater network", "Drain", "Naroda"),
    ("Naroda ward streetlights", "Streetlight", "Naroda"),
    ("Chandkheda Visat-Gandhinagar road", "Road", "Chandkheda"),
    ("Chandkheda railway overbridge joints", "Bridge", "Chandkheda"),
    ("Chandkheda drainage pumping line", "Drain", "Chandkheda"),
    ("Chandkheda civic centre", "Building", "Chandkheda"),
    ("Chandkheda park streetlights", "Streetlight", "Chandkheda"),
    ("Odhav ring road service lane", "Road", "Odhav"),
    ("Odhav GIDC stormwater drain", "Drain", "Odhav"),
    ("Odhav fire station building", "Building", "Odhav"),
    ("Odhav Kharicut canal bridge", "Bridge", "Odhav"),
    ("Odhav market streetlights", "Streetlight", "Odhav"),
    ("Shastri bridge expansion joint", "Bridge", "Paldi"),
    ("Paldi char rasta road resurfacing", "Road", "Paldi"),
    ("Paldi Sabarmati riverfront drain outfall", "Drain", "Paldi"),
    ("Paldi ward library building", "Building", "Paldi"),
    ("Ellisbridge approach streetlights", "Streetlight", "Paldi"),
]

# Costs in Rs, from Rs 15 lakh to Rs 12 crore (a mix of 12-month and 36-month guarantees)
COSTS = [15_00_000, 22_00_000, 35_00_000, 48_00_000, 65_00_000, 80_00_000, 95_00_000,
         1_40_00_000, 2_25_00_000, 3_50_00_000, 5_20_00_000, 7_80_00_000, 12_00_00_000]

CITIZEN_NAMES = ["Ramesh Solanki", "Asha Parmar", "Imran Shaikh", "Kiran Desai",
                 "Meena Rathod", "Harsh Trivedi", "Farzana Pathan", "Jignesh Modi"]
ENGINEER_NAMES = ["JE Nikunj Patel", "AE Hetal Shah", "JE Rakesh Chauhan"]

PROBLEMS = {
    "Road": ["Potholes after rain", "Surface cracking near junction", "Road sinking near manhole"],
    "Drain": ["Waterlogging, drain blocked", "Broken drain cover", "Leak in drain line"],
    "Bridge": ["Expansion joint gap widened", "Railing damaged", "Cracks on deck surface"],
    "Building": ["Roof leaking", "Plaster falling from ceiling", "Cracks in wall"],
    "Streetlight": ["Lights not working at night", "Pole leaning", "Exposed wiring"],
}


def jitter(value, spread=0.006):
    """Small random offset so points don't sit on top of each other on the map."""
    return round(value + random.uniform(-spread, spread), 6)


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------

def seed(today=None):
    """Wipe the database and insert the full demo dataset. Returns the summary dict."""
    random.seed(42)
    today = today or s.local_today()
    db.reset_db()
    conn = db.get_conn()

    # --- 1. Contractors ---
    contractor_ids = []
    for i, name in enumerate(CONTRACTORS, start=1):
        cid = s.add_contractor(
            conn, name,
            phone=f"9800000{i:03d}",
            gst_no=f"24ABCDE{1000 + i}F1Z{i}",   # 24 = Gujarat state code (fake numbers)
            on_date=today - timedelta(days=1500),
        )
        contractor_ids.append(cid)

    # --- 2. Works ---
    # Plan each work's completion date so every demo case exists:
    #   works 0-5  : guarantee ends within 30 days  -> "inspect before expiry" list
    #   works 6-10 : old small works, guarantee long over -> deposits released later
    #   the rest   : random dates across the last 4 years
    expiring_offsets = [3, 8, 12, 17, 22, 27]  # days until guarantee ends
    work_ids = []
    for i, (name, asset_type, ward) in enumerate(WORKS):
        lat, lon, zone = WARDS[ward]
        contractor_id = contractor_ids[i % len(contractor_ids)]

        if i < 6:
            cost = random.choice(COSTS[:7])                  # <= 1 crore -> 12-month DLP
            end = today + timedelta(days=expiring_offsets[i])
            completion = s.add_months(end, -12)
        elif i < 11:
            cost = random.choice(COSTS[:7])                  # 12-month DLP, ended long ago
            completion = today - timedelta(days=random.randint(900, 1400))
        else:
            cost = random.choice(COSTS)
            completion = today - timedelta(days=random.randint(60, 4 * 365))

        wid = s.add_work(
            conn, name, asset_type, contractor_id, cost, completion,
            ward=ward, zone=zone, latitude=jitter(lat), longitude=jitter(lon),
            today=today,
        )
        work_ids.append(wid)

    # --- 3. Defects (liability check decides who pays) ---
    def active_works(contractor_filter=None, min_age_days=45):
        """Works still under guarantee, completed at least `min_age_days` ago."""
        result = []
        for wid in work_ids:
            w = s.get_work(conn, wid)
            if (s.is_under_guarantee(w["dlp_end_date"], today)
                    and s.to_date(w["completion_date"]) <= today - timedelta(days=min_age_days)
                    and (contractor_filter is None or w["contractor_id"] in contractor_filter)):
                result.append(w)
        return result

    def ended_works():
        return [s.get_work(conn, wid) for wid in work_ids[11:]
                if not s.is_under_guarantee(s.get_work(conn, wid)["dlp_end_date"], today)]

    def report(work, days_ago, by="Citizen"):
        name = random.choice(CITIZEN_NAMES if by == "Citizen" else ENGINEER_NAMES)
        lang = random.choice(["gu", "hi", "en"]) if by == "Citizen" else "en"
        problem = random.choice(PROBLEMS[work["asset_type"]])
        return s.report_defect(conn, work["id"], by, name, problem, lang,
                               on_date=today - timedelta(days=days_ago))["defect_id"]

    def repair_cost():
        return random.choice([25_000, 40_000, 65_000, 90_000, 1_20_000, 1_80_000, 2_50_000, 3_50_000])

    # Alternate between the two weak contractors so BOTH end up clearly worse
    bad_a = active_works([BAD_CONTRACTORS[0]]) or active_works(BAD_CONTRACTORS)
    bad_b = active_works([BAD_CONTRACTORS[1]]) or active_works(BAD_CONTRACTORS)
    bad_cycle = [(bad_a if i % 2 == 0 else bad_b)[(i // 2) % len(bad_a if i % 2 == 0 else bad_b)]
                 for i in range(6)]
    good = [w for w in active_works() if w["contractor_id"] not in BAD_CONTRACTORS]
    good_cycle = (good * 3)[:5]     # reuse works if there are few

    # Weak contractors: 3 overdue, 1 closed late, 2 more open/closed
    for w in bad_cycle[:3]:
        report(w, days_ago=random.randint(15, 30))                       # -> Overdue after refresh
    late = report(bad_cycle[3], days_ago=40, by="Engineer")
    s.mark_repaired(conn, late, repair_cost(), on_date=today - timedelta(days=25))  # after deadline
    s.verify_repair(conn, late, True, on_date=today - timedelta(days=23))
    extra = report(bad_cycle[4], days_ago=12)
    s.mark_repaired(conn, extra, repair_cost(), on_date=today - timedelta(days=2))
    report(bad_cycle[5], days_ago=3)                                     # fresh notice, still in time

    # Good contractors: closed on time (money saved) and pending verification
    for w in good_cycle[:3]:
        days_ago = random.randint(20, 60)
        d = report(w, days_ago=days_ago, by=random.choice(["Citizen", "Engineer"]))
        # good contractors repair within 2-6 days, i.e. before the 7-day deadline
        rep_day = today - timedelta(days=days_ago) + timedelta(days=random.randint(2, 6))
        s.mark_repaired(conn, d, repair_cost(), on_date=rep_day)
        s.verify_repair(conn, d, True, on_date=rep_day + timedelta(days=1))
    d = report(good_cycle[3], days_ago=5)
    s.mark_repaired(conn, d, repair_cost(), on_date=today - timedelta(days=1))  # pending verification

    # City liability: guarantee already over
    for w in ended_works()[:2]:
        report(w, days_ago=random.randint(2, 10))

    # --- 4. Automatic updates: overdue notices, ended guarantees ---
    s.daily_refresh(conn, today)

    # --- 5. Release 5 deposits (old works with no open defects) ---
    released = 0
    for wid in work_ids[6:]:
        if released == 5:
            break
        ok, _ = s.release_deposit(conn, wid, today)
        released += ok

    summary = get_summary(conn, today)
    conn.close()
    return summary


def get_summary(conn, today=None):
    """Counts used for the printout and for quick checks."""
    today = today or s.local_today()

    def count(sql):
        return conn.execute(sql).fetchone()[0]

    return {
        "contractors": count("SELECT COUNT(*) FROM contractors"),
        "works": count("SELECT COUNT(*) FROM works"),
        "defects": count("SELECT COUNT(*) FROM defects"),
        "events": count("SELECT COUNT(*) FROM events"),
        "contractor_liable": count("SELECT COUNT(*) FROM defects WHERE liable_party='Contractor'"),
        "city_liable": count("SELECT COUNT(*) FROM defects WHERE liable_party='City'"),
        "closed": count("SELECT COUNT(*) FROM defects WHERE status='Closed'"),
        "overdue": count("SELECT COUNT(*) FROM defects WHERE status='Overdue'"),
        "pending_verification": count(
            "SELECT COUNT(*) FROM defects WHERE status='Repaired - Pending Verification'"),
        "deposits_released": count("SELECT COUNT(*) FROM works WHERE deposit_status='Released'"),
        "expiring_30_days": len(s.expiring_soon(conn, today, 30)),
        "money_saved_rs": s.money_saved(conn),
    }


# One lock shared by all users of the app (Streamlit runs every visitor in the same process),
# so two people opening the app at the same moment cannot both start seeding.
_SEED_LOCK = threading.Lock()


def _works_count():
    conn = db.get_conn()
    count = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    conn.close()
    return count


def ensure_seeded():
    """Create tables, and fill demo data only if there are no works yet.
    Returns True if it seeded. Safe to call on every page load, from many users at once."""
    db.init_db()
    if _works_count() > 0:          # fast path: no locking once data exists
        return False
    with _SEED_LOCK:
        if _works_count() > 0:      # another visitor seeded while we waited
            return False
        seed()
        return True


if __name__ == "__main__":
    result = seed()
    print("Jawabdari demo data created for", s.local_today().isoformat())
    for key, value in result.items():
        label = key.replace("_", " ").capitalize()
        print(f"  {label:<24} {value:,}" if isinstance(value, int) else f"  {label:<24} {value}")

    conn = db.get_conn()
    print("\nContractor scores (worst first):")
    print(s.contractor_scores(conn).sort_values("score")[["contractor", "defects", "overdue", "score"]]
          .to_string(index=False))
    conn.close()
