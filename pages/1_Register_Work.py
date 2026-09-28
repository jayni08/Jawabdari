"""Register Work - ward engineer registers a completed public work.

The guarantee (DLP) is calculated automatically, the deposit is marked Held,
and a QR code is generated to fix on site so citizens can see who is responsible.
"""

from datetime import date
from io import BytesIO

import pandas as pd
import qrcode
import streamlit as st

import config
import db
import seed
import services as s

st.set_page_config(page_title="Register Work | Jawabdari", page_icon="🏗️", layout="wide")

# Make sure tables exist and demo data is present
db.init_db()
seed.ensure_seeded()
conn = db.get_conn()


def make_qr_png(text):
    """Return a QR code for `text` as PNG bytes."""
    img = qrcode.make(text)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


st.title("🏗️ Register a completed public work")
st.caption("The guarantee period is calculated automatically using the AMC rule: "
           "up to ₹1 crore → 12 months, above ₹1 crore → 36 months.")

# ---------------------------------------------------------------------------
# Add contractor (small expander)
# ---------------------------------------------------------------------------
with st.expander("➕ Add a new contractor"):
    with st.form("add_contractor", clear_on_submit=True):
        c_name = st.text_input("Firm name")
        c_phone = st.text_input("Phone")
        c_gst = st.text_input("GST number")
        if st.form_submit_button("Add contractor"):
            try:
                new_cid = s.add_contractor(conn, c_name, c_phone or None, c_gst or None)
                st.success(f"Contractor {new_cid} added.")
                st.rerun()
            except ValueError as err:
                st.error(str(err))

# ---------------------------------------------------------------------------
# Work form (plain widgets, not st.form, so the preview updates live)
# ---------------------------------------------------------------------------
contractors = conn.execute("SELECT id, name FROM contractors ORDER BY name").fetchall()
contractor_labels = {f"{c['name']} ({c['id']})": c["id"] for c in contractors}

left, right = st.columns(2)
with left:
    name = st.text_input("Work name *", placeholder="e.g. SG Highway service road resurfacing")
    asset_type = st.selectbox("Asset type *", s.ASSET_TYPES)
    ward = st.selectbox("Ward *", list(seed.WARDS.keys()))
    ward_lat, ward_lon, ward_zone = seed.WARDS[ward]
    # key includes the ward, so the defaults change when the ward changes
    zone = st.text_input("Zone", value=ward_zone, key=f"zone_{ward}")
    lat_col, lon_col = st.columns(2)
    latitude = lat_col.number_input("Latitude", value=ward_lat, format="%.6f", key=f"lat_{ward}")
    longitude = lon_col.number_input("Longitude", value=ward_lon, format="%.6f", key=f"lon_{ward}")

with right:
    contractor_label = st.selectbox("Contractor *", list(contractor_labels.keys()))
    cost_rs = st.number_input("Cost (₹) *", min_value=0, value=50_00_000, step=1_00_000)
    completion = st.date_input("Completion date *", value=date.today(), max_value=date.today())
    deposit_rs = st.number_input("Security deposit (₹) — leave 0 to use 5% of cost",
                                 min_value=0, value=0, step=10_000)

    # Live preview of the guarantee
    if cost_rs > 0:
        months, end_date = s.calc_dlp(cost_rs, completion)
        deposit_preview = deposit_rs or round(cost_rs * 0.05)
        status = "🟢 active" if s.is_under_guarantee(end_date, date.today()) else "⚪ already ended"
        st.info(f"**DLP: {months} months, guarantee until {end_date}** ({status})  \n"
                f"Deposit held: ₹{deposit_preview:,}")
    else:
        st.warning("Enter a cost greater than 0 to see the guarantee.")

if st.button("Register work", type="primary"):
    errors = []
    if not name.strip():
        errors.append("Work name is required.")
    if cost_rs <= 0:
        errors.append("Cost must be greater than 0.")
    if completion > date.today():
        errors.append("Completion date cannot be in the future.")
    if not contractor_labels:
        errors.append("Add a contractor first.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        try:
            new_id = s.add_work(
                conn, name, asset_type, contractor_labels[contractor_label], cost_rs, completion,
                ward=ward, zone=zone, latitude=latitude, longitude=longitude,
                security_deposit_rs=deposit_rs or None,
            )
            # Remember it so the QR code stays visible after the page reruns
            st.session_state["last_work_id"] = new_id
        except ValueError as err:
            st.error(str(err))

# ---------------------------------------------------------------------------
# Result: success message + QR code
# ---------------------------------------------------------------------------
last_id = st.session_state.get("last_work_id")
if last_id:
    work = s.get_work(conn, last_id)
    if work:
        st.success(f"✅ Registered **{work['id']} — {work['name']}**. Guarantee until "
                   f"{work['dlp_end_date']}; deposit ₹{work['security_deposit_rs']:,} held.")
        qr_url = f"{config.BASE_URL}/Public_Board?work_id={work['id']}"
        png = make_qr_png(qr_url)
        qr_col, info_col = st.columns([1, 2])
        qr_col.image(png, caption=work["id"], width=220)
        info_col.markdown(f"**Print and fix this QR code on site.**  \nIt opens: `{qr_url}`")
        info_col.download_button("⬇️ Download QR (PNG)", data=png,
                                 file_name=f"{work['id']}_qr.png", mime="image/png")

# ---------------------------------------------------------------------------
# Recent works
# ---------------------------------------------------------------------------
st.subheader("10 most recently registered works")
recent = pd.read_sql_query(
    """SELECT w.id AS "ID", w.name AS "Work", w.asset_type AS "Type", w.ward AS "Ward",
              c.name AS "Contractor", w.cost_rs AS "Cost (₹)", w.completion_date AS "Completed",
              w.dlp_end_date AS "Guarantee until", w.deposit_status AS "Deposit"
       FROM works w JOIN contractors c ON c.id = w.contractor_id
       ORDER BY w.created_at DESC, w.id DESC LIMIT 10""",
    conn,
)
st.dataframe(recent, hide_index=True, width="stretch")

conn.close()
