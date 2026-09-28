"""Contractor Portal + Engineer / Accounts desk.

Tab 1 - Contractor: sees notices for defects in their guarantee period, marks them repaired.
Tab 2 - Engineer / Accounts: verifies repairs (approve / reject) and releases deposits
        only when the guarantee has ended and nothing is pending.
"""

from datetime import date

import streamlit as st

import db
import seed
import services as s

st.set_page_config(page_title="Contractor Portal | Jawabdari", page_icon="🧾", layout="wide")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
today = date.today()
s.refresh_overdue(conn, today)
s.refresh_lifecycle(conn, today)

st.title("🧾 Contractor Portal & Engineer Desk")

# Show a message saved before the last st.rerun() (so it survives the refresh)
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))


def flash_and_rerun(message):
    st.session_state["flash"] = message
    st.rerun()


tab_contractor, tab_engineer = st.tabs(["👷 Contractor", "🏛️ Engineer / Accounts"])

# ===========================================================================
# TAB 1 - Contractor
# ===========================================================================
with tab_contractor:
    contractors = conn.execute("SELECT id, name FROM contractors ORDER BY name").fetchall()
    names = {c["id"]: c["name"] for c in contractors}
    contractor_id = st.selectbox("Log in as contractor", list(names.keys()),
                                 format_func=lambda cid: f"{names[cid]} ({cid})")
    st.caption("Demo login. In production contractors would log in with an OTP sent to "
               "their registered mobile number.")

    # --- Reliability score ---
    scores = s.contractor_scores(conn).set_index("contractor_id")
    if contractor_id in scores.index:
        row = scores.loc[contractor_id]
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Reliability score", f"{int(row['score'])}/100")
        m2.metric("Works", int(row["works"]))
        m3.metric("Defects (in guarantee)", int(row["defects"]))
        m4.metric("Overdue / late", int(row["overdue"]))
        avg = row["avg_days_to_repair"]
        m5.metric("Avg days to repair", "-" if avg is None or avg != avg else avg)  # avg != avg -> NaN

    # --- Open notices ---
    notices = conn.execute(
        """SELECT d.id, d.description, d.reported_on, d.notice_deadline, d.status, d.reporter_name,
                  w.id AS work_id, w.name AS work_name, w.ward
           FROM defects d JOIN works w ON w.id = d.work_id
           WHERE w.contractor_id = ? AND d.liable_party = 'Contractor'
             AND d.status IN ('Notice Sent', 'Overdue')
           ORDER BY d.notice_deadline""",
        (contractor_id,),
    ).fetchall()

    waiting = conn.execute(
        """SELECT COUNT(*) FROM defects d JOIN works w ON w.id = d.work_id
           WHERE w.contractor_id = ? AND d.status = 'Repaired - Pending Verification'""",
        (contractor_id,),
    ).fetchone()[0]

    st.subheader(f"Repair notices ({len(notices)})")
    if waiting:
        st.info(f"{waiting} repair(s) submitted and waiting for engineer verification.")
    if not notices:
        st.success("No pending notices. 🎉")

    for n in notices:
        days_left = (s.to_date(n["notice_deadline"]) - today).days
        with st.container(border=True):
            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"**{n['id']} · {n['work_name']}** ({n['work_id']}, {n['ward']})")
                st.write(f"Problem: {n['description']}")
                st.caption(f"Reported on {n['reported_on']} by {n['reporter_name'] or 'Anonymous'}")
                if days_left < 0:
                    st.markdown(f":red[**OVERDUE by {-days_left} day(s)** — deadline was "
                                f"{n['notice_deadline']}. This lowers your score.]")
                else:
                    st.markdown(f":green[**{days_left} day(s) left** — repair free by "
                                f"{n['notice_deadline']}]")
            with right:
                cost = st.number_input("Repair cost (₹)", min_value=0, value=50_000, step=5_000,
                                       key=f"cost_{n['id']}",
                                       help="Estimated value of the repair (what the city would "
                                            "otherwise have paid).")
                if st.button("✅ Mark repaired", key=f"repair_{n['id']}"):
                    try:
                        s.mark_repaired(conn, n["id"], cost, today)
                        flash_and_rerun(f"{n['id']} marked repaired. Sent for engineer verification.")
                    except ValueError as err:
                        st.error(str(err))

# ===========================================================================
# TAB 2 - Engineer / Accounts
# ===========================================================================
with tab_engineer:
    st.subheader("Repairs waiting for verification")
    pending = conn.execute(
        """SELECT d.id, d.description, d.repaired_on, d.repair_cost_rs, d.liable_party,
                  w.id AS work_id, w.name AS work_name, c.name AS contractor
           FROM defects d JOIN works w ON w.id = d.work_id
           JOIN contractors c ON c.id = w.contractor_id
           WHERE d.status = 'Repaired - Pending Verification'
           ORDER BY d.repaired_on""",
    ).fetchall()

    if not pending:
        st.success("Nothing waiting for verification.")

    for p in pending:
        with st.container(border=True):
            info, approve_col, reject_col = st.columns([4, 1, 1])
            who = p["contractor"] if p["liable_party"] == "Contractor" else "City team"
            info.markdown(f"**{p['id']} · {p['work_name']}** ({p['work_id']})  \n"
                          f"{p['description']} — repaired by {who} on {p['repaired_on']}, "
                          f"value ₹{p['repair_cost_rs']:,}")
            if approve_col.button("👍 Approve", key=f"approve_{p['id']}"):
                s.verify_repair(conn, p["id"], True, today)
                flash_and_rerun(f"{p['id']} approved and closed.")
            if reject_col.button("👎 Reject", key=f"reject_{p['id']}"):
                s.verify_repair(conn, p["id"], False, today)
                flash_and_rerun(f"{p['id']} rejected. New 7-day notice sent.")

    st.divider()
    st.subheader("💰 Security deposit release")
    st.caption("A deposit can be released only after the guarantee ends AND every defect is closed.")

    held = conn.execute(
        """SELECT w.id, w.name, w.dlp_end_date, w.security_deposit_rs, c.name AS contractor
           FROM works w JOIN contractors c ON c.id = w.contractor_id
           WHERE w.deposit_status = 'Held' ORDER BY w.dlp_end_date""",
    ).fetchall()
    held_map = {w["id"]: w for w in held}

    if not held:
        st.info("No deposits are currently held.")
    else:
        work_id = st.selectbox(
            "Select a work", list(held_map.keys()),
            format_func=lambda wid: f"{wid} - {held_map[wid]['name']} "
                                    f"(guarantee until {held_map[wid]['dlp_end_date']})",
        )
        w = held_map[work_id]
        allowed, reason = s.can_release_deposit(conn, work_id, today)
        st.write(f"Contractor: **{w['contractor']}** · Deposit held: **₹{w['security_deposit_rs']:,}**")
        if allowed:
            st.success(f"✅ {reason}")
        else:
            st.warning(f"⛔ {reason}")

        if st.button("Release deposit", type="primary", disabled=not allowed):
            ok, message = s.release_deposit(conn, work_id, today)
            if ok:
                flash_and_rerun(f"Deposit of ₹{w['security_deposit_rs']:,} for {work_id} released.")
            else:
                st.error(message)

conn.close()
