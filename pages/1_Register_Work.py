"""Register Work - ward engineer registers a completed public work.

The guarantee (DLP) is calculated automatically, the deposit is marked Held,
and a QR code is generated to fix on site so citizens can see who is responsible.
"""

from io import BytesIO
from urllib.parse import urlsplit

import pandas as pd
import qrcode
import streamlit as st

import config
import db
import seed
import services as s
import ui

ui.setup("Register work", "🏗️")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
today = s.local_today()


def app_base_url():
    """The address people are using right now (localhost, Wi-Fi IP or the live site),
    so QR links always open the same app. Falls back to config.BASE_URL."""
    try:
        parts = urlsplit(st.context.url or "")
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}"
    except Exception:
        pass
    return config.BASE_URL.rstrip("/")


def make_qr_png(text):
    """Return a QR code for `text` as PNG bytes."""
    img = qrcode.make(text, border=2)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


ui.hero("Register a completed public work",
        "The guarantee period is calculated automatically (AMC rule: up to ₹1 crore → 12 months, "
        "above → 36 months). Print the QR code and fix it on site.",
        eyebrow="City teams · Ward engineer")

contractors = conn.execute("SELECT id, name FROM contractors ORDER BY name").fetchall()
contractor_labels = {f"{c['name']} ({c['id']})": c["id"] for c in contractors}

form_col, side_col = st.columns([3, 2], gap="large")

# ---------------------------------------------------------------------------
# Form (plain widgets, not st.form, so the preview updates live)
# ---------------------------------------------------------------------------
with form_col:
    with st.container(border=True):
        st.markdown("**Work details**")
        name = st.text_input("Work name *", placeholder="e.g. SG Highway service road resurfacing")
        c1, c2 = st.columns(2)
        asset_type = c1.selectbox("Asset type *", s.ASSET_TYPES)
        ward = c2.selectbox("Ward *", list(seed.WARDS.keys()))
        ward_lat, ward_lon, ward_zone = seed.WARDS[ward]
        c3, c4, c5 = st.columns(3)
        zone = c3.text_input("Zone", value=ward_zone, key=f"zone_{ward}")
        latitude = c4.number_input("Latitude", value=ward_lat, format="%.6f", key=f"lat_{ward}")
        longitude = c5.number_input("Longitude", value=ward_lon, format="%.6f", key=f"lon_{ward}")

    with st.container(border=True):
        st.markdown("**Contract**")
        contractor_label = st.selectbox("Contractor *", list(contractor_labels.keys()),
                                        placeholder="Add a contractor first")
        c6, c7 = st.columns(2)
        cost_rs = c6.number_input("Cost (₹) *", min_value=0, value=50_00_000, step=1_00_000)
        completion = c7.date_input("Completion date *", value=today, max_value=today, format="DD/MM/YYYY")
        deposit_rs = st.number_input("Security deposit (₹) — leave 0 to use 5% of cost",
                                     min_value=0, value=0, step=10_000)

    register_clicked = st.button("Register work", type="primary", icon=":material/add_task:",
                                 width="stretch")

# ---------------------------------------------------------------------------
# Live guarantee preview + add contractor
# ---------------------------------------------------------------------------
with side_col:
    ui.section("Guarantee preview")
    if cost_rs > 0:
        months, end_date = s.calc_dlp(cost_rs, completion)
        deposit_preview = deposit_rs or round(cost_rs * 0.05)
        active = s.is_under_guarantee(end_date, today)
        ui.status_banner(
            f"{months}-month guarantee",
            f"Contractor must repair defects free until {end_date}. "
            f"Deposit held: {s.format_inr(deposit_preview)}.",
            tone="green" if active else "grey",
        )
        if not active:
            st.caption("This guarantee has already ended — defects will go to the city queue.")
    else:
        ui.status_banner("No guarantee yet", "Enter a cost greater than 0.", tone="amber")

    with st.expander("Add a new contractor", icon=":material/person_add:"):
        with st.form("add_contractor", clear_on_submit=True, border=False):
            c_name = st.text_input("Firm name")
            c_phone = st.text_input("Phone")
            c_gst = st.text_input("GST number")
            if st.form_submit_button("Add contractor"):
                try:
                    new_cid = s.add_contractor(conn, c_name, c_phone or None, c_gst or None)
                    st.session_state["flash"] = f"Contractor {new_cid} added."
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------
if register_clicked:
    errors = []
    if not name.strip():
        errors.append("Work name is required.")
    if cost_rs <= 0:
        errors.append("Cost must be greater than 0.")
    if deposit_rs > cost_rs:
        errors.append("Security deposit cannot be more than the cost.")
    if completion > today:
        errors.append("Completion date cannot be in the future.")
    if not (6 <= latitude <= 38 and 68 <= longitude <= 98):
        errors.append("Location must be inside India (check latitude / longitude).")
    if not contractor_labels or contractor_label is None:
        errors.append("Add a contractor first.")

    if not errors:
        duplicate = conn.execute(
            "SELECT id FROM works WHERE name = ? AND contractor_id = ? AND completion_date = ?",
            (name.strip(), contractor_labels[contractor_label], completion.isoformat()),
        ).fetchone()
        if duplicate:
            errors.append(f"This work is already registered as {duplicate['id']}.")

    if errors:
        for e in errors:
            st.error(e, icon=":material/error:")
    else:
        try:
            new_id = s.add_work(
                conn, name, asset_type, contractor_labels[contractor_label], cost_rs, completion,
                ward=ward, zone=zone, latitude=latitude, longitude=longitude,
                security_deposit_rs=deposit_rs or None, today=today,
            )
            st.session_state["last_work_id"] = new_id   # keep QR visible after reruns
        except ValueError as err:
            st.error(str(err))

# ---------------------------------------------------------------------------
# Result: success + QR code
# ---------------------------------------------------------------------------
last_id = st.session_state.get("last_work_id")
if last_id:
    work = s.get_work(conn, last_id)
    if work:
        st.success(f"Registered **{work['id']} — {s.safe_md(work['name'])}**. Guarantee until "
                   f"{work['dlp_end_date']}; deposit {s.format_inr(work['security_deposit_rs'])} held.",
                   icon=":material/check_circle:")
        base_url = app_base_url()
        qr_url = f"{base_url}/Public_Board?work_id={work['id']}"
        png = make_qr_png(qr_url)
        with st.container(border=True):
            qr_col, info_col = st.columns([1, 2], vertical_alignment="center")
            qr_col.image(png, width=200)
            with info_col:
                ui.card_header(f"QR code for {work['id']}", "Print it and fix it on site. "
                               "Citizens scan it to see who built this and to report problems.")
                st.code(qr_url, language=None)
                st.download_button("Download QR (PNG)", data=png, icon=":material/download:",
                                   file_name=f"{work['id']}_qr.png", mime="image/png")
            host = urlsplit(base_url).hostname or ""
            if host in ("localhost", "127.0.0.1"):
                st.info("This QR uses **localhost**, which only opens on this laptop. To test with your "
                        "phone, open the app using the **Network URL** shown in Terminal "
                        "(http://192.168.x.x:8501) on the same Wi-Fi, or use the deployed app, then "
                        "register again.", icon=":material/smartphone:")

# ---------------------------------------------------------------------------
# Recent works
# ---------------------------------------------------------------------------
ui.section("Recently registered works")
recent = pd.read_sql_query(
    """SELECT w.id AS "ID", w.name AS "Work", w.asset_type AS "Type", w.ward AS "Ward",
              c.name AS "Contractor", w.cost_rs AS cost, w.completion_date AS "Completed",
              w.dlp_end_date AS "Guarantee until", w.deposit_status AS "Deposit"
       FROM works w JOIN contractors c ON c.id = w.contractor_id
       ORDER BY w.created_at DESC, w.id DESC LIMIT 10""",
    conn,
)
recent.insert(5, "Cost", recent.pop("cost").map(s.format_inr))
with st.container(border=True):
    if recent.empty:
        st.info("No works registered yet.")
    else:
        st.dataframe(recent, hide_index=True, width="stretch")

conn.close()
