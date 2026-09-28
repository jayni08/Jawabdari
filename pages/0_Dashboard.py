"""Commissioner Dashboard - the home page.

No caching on purpose: the data is small (SQLite) and queries take milliseconds,
so the dashboard is always up to date after actions on other pages.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

import config
import db
import seed
import services as s
import ui

ui.setup("Dashboard", "📊")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
today = s.local_today()
s.refresh_overdue(conn, today)
s.refresh_lifecycle(conn, today)

ui.hero(
    "Commissioner dashboard",
    "Every public work, who is responsible for it today, and how much the city saved by "
    f"making contractors repair defects free during the guarantee. As of {today.strftime('%d %b %Y')}.",
)


def short_inr(amount):
    """Compact money for KPI tiles: Rs 4.95 lakh -> ₹4.95 L, Rs 4.46 crore -> ₹4.46 Cr."""
    return s.format_inr(amount).replace("Rs ", "₹").replace(" lakh", " L").replace(" crore", " Cr")


# ---------------------------------------------------------------------------
# KPI tiles (two rows so they stay readable on phones)
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

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Money saved", short_inr(s.money_saved(conn)),
          help="Repairs contractors had to do free during the guarantee. "
               "Without Jawabdari the city would have paid for these.")
k2.metric("Under guarantee", under_guarantee, help="Works where the contractor must still repair free.")
k3.metric(f"Expiring ≤ {config.EXPIRY_ALERT_DAYS} days", len(expiring),
          help="Inspect these now - after expiry, repairs become the city's cost.")
k4.metric("Open notices", f"{open_notices} · {overdue} late",
          help="Repair notices sent to contractors that are not yet repaired.")
k5.metric("Deposits held", short_inr(deposits_held),
          help="Contractor security deposits the city is holding until guarantees end.")

# ---------------------------------------------------------------------------
# Inspect before guarantee expires
# ---------------------------------------------------------------------------
ui.section("Inspect before the guarantee expires",
           "Any defect found after expiry becomes the city's cost - inspect these works now, "
           "while the contractor must still repair free.")
with st.container(border=True):
    if expiring.empty:
        st.success(f"No guarantees end in the next {config.EXPIRY_ALERT_DAYS} days.")
    else:
        table = expiring.sort_values("days_left").rename(columns={
            "id": "ID", "name": "Work", "asset_type": "Type", "ward": "Ward",
            "contractor": "Contractor", "dlp_end_date": "Guarantee ends",
            "days_left": "Days left", "security_deposit_rs": "Deposit held",
        })
        table["Deposit held"] = table["Deposit held"].map(s.format_inr)
        st.dataframe(
            table[["ID", "Work", "Type", "Ward", "Contractor", "Guarantee ends", "Days left", "Deposit held"]],
            hide_index=True, width="stretch",
            column_config={
                "Days left": st.column_config.ProgressColumn(
                    "Days left", format="%d days", min_value=0, max_value=config.EXPIRY_ALERT_DAYS),
            },
        )

# ---------------------------------------------------------------------------
# Chart + leaderboard
# ---------------------------------------------------------------------------
chart_col, board_col = st.columns(2, gap="medium")

with chart_col:
    ui.section("Who paid for repairs?", "Defects reported per month, last 12 months")
    with st.container(border=True):
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
        counts["Month"] = counts["month"].dt.strftime("%b")
        counts["Liable"] = counts["liable_party"].map({"Contractor": "Contractor (free repair)",
                                                       "City": "City (paid by city)"})
        fig = px.bar(
            counts, x="Month", y="defects", color="Liable", barmode="group",
            color_discrete_map={"Contractor (free repair)": ui.CONTRACTOR_BLUE,
                                "City (paid by city)": ui.CITY_ORANGE},
            labels={"defects": "Defects", "Month": ""},
        )
        fig.update_traces(marker_line_width=0, marker_cornerradius=4,
                          hovertemplate="%{x}<br>%{y} defect(s)<extra>%{fullData.name}</extra>")
        fig.update_layout(
            bargap=0.35, bargroupgap=0.1, height=340, margin=dict(l=8, r=8, t=8, b=8),
            font=dict(family="Inter, sans-serif", color="#3c4043"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
            yaxis=dict(gridcolor="rgba(28,29,43,0.08)", dtick=1, rangemode="tozero", zeroline=False),
            xaxis=dict(tickangle=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with board_col:
    ui.section("Contractor reliability", "Worst first - use this when awarding future tenders")
    with st.container(border=True):
        scores = s.contractor_scores(conn).sort_values(["score", "overdue"], ascending=[True, False])
        if scores.empty:
            st.info("No contractors yet - add one on Register work.")
        else:
            board = pd.DataFrame({
                "Contractor": scores["contractor"],
                "Score": scores["score"].astype(int),
                "Defects": scores["defects"],
                "Overdue": scores["overdue"],
            })
            st.dataframe(
                board, hide_index=True, width="stretch", height=330,
                column_config={
                    "Contractor": st.column_config.TextColumn(width="medium"),
                    "Score": st.column_config.ProgressColumn("Score", format="%d", min_value=0,
                                                             max_value=100, width="small"),
                    "Defects": st.column_config.NumberColumn(width="small"),
                    "Overdue": st.column_config.NumberColumn(width="small"),
                },
            )
        st.caption("Score = 100 − 5 per defect − 15 per overdue notice + 2 per on-time repair.")

# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
ui.section("Works on the map", "Blue = contractor still responsible · Grey = guarantee ended")
with st.container(border=True):
    works = pd.read_sql_query(
        """SELECT w.id, w.name, w.asset_type, w.ward, w.latitude, w.longitude, w.dlp_end_date,
                  c.name AS contractor
           FROM works w JOIN contractors c ON c.id = w.contractor_id
           WHERE w.latitude IS NOT NULL AND w.longitude IS NOT NULL""",
        conn,
    )
    if works.empty:
        st.info("No works with a location yet.")
    else:
        works["Status"] = ["Under guarantee" if s.is_under_guarantee(d, today) else "Guarantee ended"
                           for d in works["dlp_end_date"]]
        map_fig = px.scatter_map(
            works, lat="latitude", lon="longitude", color="Status",
            color_discrete_map={"Under guarantee": ui.CONTRACTOR_BLUE, "Guarantee ended": "#8a8a85"},
            hover_name="name",
            hover_data={"id": True, "ward": True, "contractor": True, "dlp_end_date": True,
                        "latitude": False, "longitude": False, "Status": False},
            zoom=10.6, height=460, map_style="open-street-map",
        )
        map_fig.update_traces(marker=dict(size=13, opacity=0.9))
        map_fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), font=dict(family="Inter, sans-serif"),
            legend=dict(orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0.02,
                        bgcolor="rgba(255,255,255,0.9)", title=None),
        )
        st.plotly_chart(map_fig, width="stretch", config={"displayModeBar": False})

with st.expander("What is Jawabdari?"):
    st.markdown(
        "When a contractor builds a road, bridge or drain, they must repair defects **free** during "
        "the Defect Liability Period. Nobody tracks this, so cities pay twice. Jawabdari tracks "
        "**who is responsible** for every public work at every stage.\n\n"
        f"AMC rule (Aug 2026): up to ₹1 crore → {config.DLP_MONTHS_SMALL} months, "
        f"above ₹1 crore → {config.DLP_MONTHS_LARGE} months."
    )

conn.close()
