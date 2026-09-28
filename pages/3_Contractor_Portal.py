"""Contractor & Engineer desk.

Tab 1 - Contractor: sees notices for defects in their guarantee period, marks them repaired.
Tab 2 - Engineer / Accounts: verifies repairs (approve / reject) and releases deposits
        only when the guarantee has ended and nothing is pending.
"""

import streamlit as st

import db
import seed
import services as s
import ui

ui.setup("Contractor & engineer desk", "🧾")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
today = s.local_today()
s.refresh_overdue(conn, today)
s.refresh_lifecycle(conn, today)

ui.hero("Contractor & engineer desk",
        "Contractors see their repair notices and deadlines. Engineers verify repairs, and accounts "
        "releases deposits only when the guarantee is over and nothing is pending.",
        eyebrow="City teams · Accountability")

# Message saved before the last st.rerun() so it survives the refresh
if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")


def flash_and_rerun(message):
    st.session_state["flash"] = message
    st.rerun()


tab_contractor, tab_engineer = st.tabs([":material/construction: Contractor",
                                        ":material/verified: Engineer / Accounts"])

# ===========================================================================
# TAB 1 - Contractor
# ===========================================================================
with tab_contractor:
    contractors = conn.execute("SELECT id, name FROM contractors ORDER BY name").fetchall()
    names = {c["id"]: c["name"] for c in contractors}

    if not names:
        st.info("No contractors yet — add one on the Register work page.")
    else:
        # Open on the contractor with the most open notices (most useful to look at first)
        busiest = conn.execute(
            """SELECT w.contractor_id FROM defects d JOIN works w ON w.id = d.work_id
               WHERE d.liable_party = 'Contractor' AND d.status IN ('Notice Sent', 'Overdue')
               GROUP BY w.contractor_id ORDER BY COUNT(*) DESC, w.contractor_id LIMIT 1"""
        ).fetchone()
        ids = list(names.keys())
        default_index = ids.index(busiest[0]) if busiest and busiest[0] in ids else 0
        contractor_id = st.selectbox("Log in as contractor", ids, index=default_index,
                                     format_func=lambda cid: f"{names[cid]} ({cid})")
        st.caption("Demo login. In production contractors log in with an OTP sent to their "
                   "registered mobile number.")

        # --- Reliability score ---
        scores = s.contractor_scores(conn).set_index("contractor_id")
        row = scores.loc[contractor_id]
        m1, m2, m3, m4, m5 = st.columns(5)   # stacks automatically on phones
        m1.metric("Reliability score", f"{int(row['score'])}/100")
        m2.metric("Works", int(row["works"]))
        m3.metric("Defects in guarantee", int(row["defects"]))
        m4.metric("Overdue / late", int(row["overdue"]))
        avg = row["avg_days_to_repair"]
        m5.metric("Avg days to repair", "–" if avg is None or avg != avg else avg)  # avg != avg -> NaN
        st.markdown(f"Rating: {ui.pill(ui.stars(row['score']) + '  ' + str(int(row['score'])), ui.score_tone(row['score']))}",
                    unsafe_allow_html=True)

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

        ui.section(f"Repair notices ({len(notices)})",
                   "Repair free before the deadline. Overdue notices lower your score and future tenders.")
        if waiting:
            st.info(f"{waiting} repair(s) submitted and waiting for engineer verification.",
                    icon=":material/hourglass_top:")
        if not notices:
            st.success("No pending notices. Great work!", icon=":material/celebration:")

        for n in notices:
            days_left = (s.to_date(n["notice_deadline"]) - today).days
            if days_left < 0:
                badge = ui.pill(f"OVERDUE by {-days_left} day(s)", "red")
            elif days_left <= 2:
                badge = ui.pill(f"{days_left} day(s) left", "amber")
            else:
                badge = ui.pill(f"{days_left} days left", "green")
            with st.container(border=True):
                left, right = st.columns([3, 2], vertical_alignment="center")
                with left:
                    ui.card_header(f"{n['id']} · {n['work_name']}", f"{n['work_id']} · {n['ward']}", badge)
                    st.text(f"Problem: {n['description']}")
                    st.caption(f"Reported {n['reported_on']} by {s.safe_md(n['reporter_name'] or 'Anonymous')} "
                               f"· repair free by {n['notice_deadline']}")
                with right:
                    cost = st.number_input("Repair value (₹)", min_value=0, value=50_000, step=5_000,
                                           key=f"cost_{n['id']}",
                                           help="Estimated value of the repair — what the city "
                                                "would otherwise have paid.")
                    if st.button("Mark repaired", key=f"repair_{n['id']}", type="primary",
                                 icon=":material/build:", width="stretch"):
                        try:
                            s.mark_repaired(conn, n["id"], cost, today)
                            flash_and_rerun(f"{n['id']} marked repaired. Sent for engineer verification.")
                        except ValueError as err:
                            st.error(str(err))

# ===========================================================================
# TAB 2 - Engineer / Accounts
# ===========================================================================
with tab_engineer:
    ui.section("Repairs waiting for verification", "Check the site, then approve or send back.")
    pending = conn.execute(
        """SELECT d.id, d.description, d.repaired_on, d.repair_cost_rs, d.liable_party,
                  w.id AS work_id, w.name AS work_name, c.name AS contractor
           FROM defects d JOIN works w ON w.id = d.work_id
           JOIN contractors c ON c.id = w.contractor_id
           WHERE d.status = 'Repaired - Pending Verification'
           ORDER BY d.repaired_on""",
    ).fetchall()

    if not pending:
        st.success("Nothing waiting for verification.", icon=":material/task_alt:")

    for p in pending:
        who = p["contractor"] if p["liable_party"] == "Contractor" else "City team"
        tone = "indigo" if p["liable_party"] == "Contractor" else "amber"
        with st.container(border=True):
            info, approve_col, reject_col = st.columns([4, 1, 1], vertical_alignment="center")
            with info:
                ui.card_header(f"{p['id']} · {p['work_name']}",
                               f"{p['work_id']} · repaired by {who} on {p['repaired_on']} · "
                               f"value {s.format_inr(p['repair_cost_rs'])}",
                               ui.pill(p["liable_party"] + " liable", tone))
                st.text(p["description"])
            if approve_col.button("Approve", key=f"approve_{p['id']}", icon=":material/thumb_up:",
                                  width="stretch"):
                try:
                    s.verify_repair(conn, p["id"], True, today)
                    flash_and_rerun(f"{p['id']} approved and closed.")
                except ValueError:
                    flash_and_rerun(f"{p['id']} was already handled. List refreshed.")
            if reject_col.button("Reject", key=f"reject_{p['id']}", icon=":material/thumb_down:",
                                 width="stretch"):
                try:
                    s.verify_repair(conn, p["id"], False, today)
                    flash_and_rerun(f"{p['id']} rejected. New 7-day notice sent.")
                except ValueError:
                    flash_and_rerun(f"{p['id']} was already handled. List refreshed.")

    ui.section("Security deposit release",
               "A deposit can be released only after the guarantee ends AND every defect is closed.")
    held = conn.execute(
        """SELECT w.id, w.name, w.dlp_end_date, w.security_deposit_rs, c.name AS contractor
           FROM works w JOIN contractors c ON c.id = w.contractor_id
           WHERE w.deposit_status = 'Held' ORDER BY w.dlp_end_date""",
    ).fetchall()
    held_map = {w["id"]: w for w in held}

    with st.container(border=True):
        if not held:
            st.info("No deposits are currently held.")
        else:
            work_id = st.selectbox(
                "Select a work", list(held_map.keys()),
                format_func=lambda wid: f"{wid} · {held_map[wid]['name']} "
                                        f"(guarantee until {held_map[wid]['dlp_end_date']})",
            )
            w = held_map[work_id]
            allowed, reason = s.can_release_deposit(conn, work_id, today)
            ui.facts([
                ("Contractor", w["contractor"], False),
                ("Deposit held", s.format_inr(w["security_deposit_rs"]), False),
            ])
            if allowed:
                st.success(reason, icon=":material/lock_open:")
            else:
                st.warning(reason, icon=":material/lock:")

            if st.button("Release deposit", type="primary", disabled=not allowed,
                         icon=":material/payments:"):
                try:
                    ok, message = s.release_deposit(conn, work_id, today)
                except Exception as err:  # never crash the accounts desk; show the reason instead
                    ok, message = False, f"Could not release deposit: {err}"
                if ok:
                    flash_and_rerun(f"Deposit of {s.format_inr(w['security_deposit_rs'])} for {work_id} released.")
                else:
                    st.error(message)

conn.close()
