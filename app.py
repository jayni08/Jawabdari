"""Jawabdari - Commissioner Dashboard (home page).

Run:  streamlit run app.py

No caching is used on purpose: the data is small (SQLite, a few hundred rows),
queries take milliseconds, and it guarantees the dashboard is always up to date
after actions on the other pages.
"""

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import config
import db
import seed
import services as s

st.set_page_config(page_title="Jawabdari | Dashboard", page_icon="🏗️", layout="wide")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
today = date.today()
s.refresh_overdue(conn, today)
s.refresh_lifecycle(conn, today)

# Colours: validated categorical pair (blue, orange); grey for "ended" (recessive)
CONTRACTOR_BLUE = "#2a78d6"
CITY_ORANGE = "#eb6834"
ENDED_GREY = "#8a8a85"

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("What is Jawabdari?")
    st.write(
        "When a contractor builds a road, bridge or drain, they must repair defects **free** "
        "during the Defect Liability Period (DLP). Nobody tracks this, so cities pay twice.\n\n"
        "Jawabdari tracks **who is responsible** for every public work at every stage — and "
        "makes sure the city never pays twice."
    )
    st.caption(f"AMC rule: ≤ ₹1 crore → {config.DLP_MONTHS_SMALL} months, "
               f"> ₹1 crore → {config.DLP_MONTHS_LARGE} months.")
    st.divider()
    st.write(f"📅 Today: **{today.strftime('%d %b %Y')}**")

st.title("🏗️ Jawabdari — Commissioner Dashboard")
st.caption("Ahmedabad Municipal Corporation · public works, guarantees and contractor accountability")

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
under_guarantee = conn.execute(
    "SELECT COUNT(*) FROM works WHERE dlp_end_date >= ? AND lifecycle_stage != 'Decommissioned'",
    (today.isoformat(),),
).fetchone()[0]
expiring = s.expiring_soon(conn, today, config.EXPIRY_ALERT_DAYS)
open_notices = conn.execute(
    "SELECT COUNT(*) FROM defects WHERE status IN ('Notice Sent', 'Overdue')").fetchone()[0]
overdue = conn.execute("SELECT COUNT(*) FROM defects WHERE status = 'Overdue'").fetchone()[0]
deposits_held = conn.execute(
    "SELECT COALESCE(SUM(security_deposit_rs), 0) FROM works WHERE deposit_status = 'Held'").fetchone()[0]

def short_inr(amount):
    """Compact money text for KPI tiles: Rs 4.95 lakh -> ₹4.95 L, Rs 4.46 crore -> ₹4.46 Cr."""
    return (s.format_inr(amount).replace("Rs ", "₹")
            .replace(" lakh", " L").replace(" crore", " Cr"))


k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("💰 Money saved", short_inr(s.money_saved(conn)),
          help="Repairs the contractor had to do free (closed defects under guarantee). "
               "The city would otherwise have paid this.")
k2.metric("🛡️ Works under guarantee", under_guarantee)
k3.metric(f"⏳ Expiring in {config.EXPIRY_ALERT_DAYS} days", len(expiring))
k4.metric("📨 Open notices", open_notices, delta=f"{overdue} overdue" if overdue else None,
          delta_color="inverse")
k5.metric("🏦 Deposits held", short_inr(deposits_held))

# ---------------------------------------------------------------------------
# Inspect before guarantee expires
# ---------------------------------------------------------------------------
st.subheader("🔍 Inspect before the guarantee expires")
st.caption("Any defect found **after** the guarantee ends becomes the city's cost — "
           "so inspect these works now, while the contractor must still repair free.")
if expiring.empty:
    st.success(f"No guarantees end in the next {config.EXPIRY_ALERT_DAYS} days.")
else:
    table = expiring.sort_values("days_left").rename(columns={
        "id": "ID", "name": "Work", "asset_type": "Type", "ward": "Ward", "contractor": "Contractor",
        "dlp_end_date": "Guarantee ends", "days_left": "Days left", "security_deposit_rs": "Deposit held",
    })
    table["Deposit held"] = table["Deposit held"].map(s.format_inr)
    st.dataframe(
        table[["ID", "Work", "Type", "Ward", "Contractor", "Guarantee ends", "Days left", "Deposit held"]],
        hide_index=True, width="stretch",
    )

# ---------------------------------------------------------------------------
# Defects by liability per month (last 12 months)
# ---------------------------------------------------------------------------
chart_col, board_col = st.columns(2)

with chart_col:
    st.subheader("📊 Who paid for repairs?")
    st.caption("Defects reported per month, last 12 months")
    months = pd.period_range(end=pd.Period(today, freq="M"), periods=12, freq="M")
    defects = pd.read_sql_query(
        "SELECT reported_on, liable_party FROM defects WHERE reported_on >= ?",
        conn, params=(months[0].start_time.date().isoformat(),),
    )
    defects["month"] = pd.to_datetime(defects["reported_on"]).dt.to_period("M")
    counts = (defects.groupby(["month", "liable_party"]).size()
              .reindex(pd.MultiIndex.from_product([months, ["Contractor", "City"]],
                                                  names=["month", "liable_party"]), fill_value=0)
              .reset_index(name="defects"))
    counts["Month"] = counts["month"].dt.strftime("%b %Y")
    counts["Liable"] = counts["liable_party"].map({"Contractor": "Contractor (free repair)",
                                                   "City": "City (paid by city)"})
    fig = px.bar(
        counts, x="Month", y="defects", color="Liable", barmode="group",
        color_discrete_map={"Contractor (free repair)": CONTRACTOR_BLUE, "City (paid by city)": CITY_ORANGE},
        labels={"defects": "Defects reported", "Month": ""},
    )
    fig.update_traces(marker_line_width=0, hovertemplate="%{x}<br>%{y} defect(s)<extra>%{fullData.name}</extra>")
    fig.update_layout(
        bargap=0.35, bargroupgap=0.08, height=360, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        yaxis=dict(gridcolor="rgba(128,128,128,0.2)", dtick=1, rangemode="tozero"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Contractor leaderboard (worst first)
# ---------------------------------------------------------------------------
with board_col:
    st.subheader("🏅 Contractor reliability")
    scores = s.contractor_scores(conn).sort_values(["score", "overdue"], ascending=[True, False])

    def rating(score):
        return "🔴 Poor" if score < 60 else ("🟠 Watch" if score < 85 else "🟢 Good")

    board = pd.DataFrame({
        "Contractor": scores["contractor"],
        "Score": scores["score"].astype(int),
        "Rating": scores["score"].map(rating),
        "Defects": scores["defects"],
        "Overdue": scores["overdue"],
    })

    def colour_score(value):
        if value < 60:
            return "background-color: #fde2e1; color: #8a1c14; font-weight: 700"
        if value < 85:
            return "background-color: #fff1d6; color: #7a4b00; font-weight: 700"
        return "background-color: #e3f4e6; color: #145c2a; font-weight: 700"

    st.dataframe(board.style.map(colour_score, subset=["Score"]), hide_index=True, width="stretch")
    st.caption("Score = 100 − 5 per defect − 15 per overdue notice + 2 per on-time repair (0–100). "
               "Use it when awarding future tenders.")

# ---------------------------------------------------------------------------
# Map of works
# ---------------------------------------------------------------------------
st.subheader("🗺️ Works on the map")
works = pd.read_sql_query(
    """SELECT w.id, w.name, w.asset_type, w.ward, w.latitude, w.longitude, w.dlp_end_date,
              c.name AS contractor
       FROM works w JOIN contractors c ON c.id = w.contractor_id
       WHERE w.latitude IS NOT NULL AND w.longitude IS NOT NULL""",
    conn,
)
works["Status"] = ["Under guarantee" if s.is_under_guarantee(d, today) else "Guarantee ended"
                   for d in works["dlp_end_date"]]
map_fig = px.scatter_map(
    works, lat="latitude", lon="longitude", color="Status",
    color_discrete_map={"Under guarantee": CONTRACTOR_BLUE, "Guarantee ended": ENDED_GREY},
    hover_name="name",
    hover_data={"id": True, "ward": True, "contractor": True, "dlp_end_date": True,
                "latitude": False, "longitude": False, "Status": False},
    zoom=10.5, height=480, map_style="open-street-map",
)
map_fig.update_traces(marker=dict(size=12))
map_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01,
                                  bgcolor="rgba(255,255,255,0.85)", title=None))
st.plotly_chart(map_fig, width="stretch")

conn.close()
