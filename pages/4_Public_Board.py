"""Public Board - the page a citizen sees after scanning the QR code on site.

Mobile-first: one column, big text, no login.
Shows who built the work, what it cost, whether it is still under guarantee,
the contractor's rating, and a big button to report a problem.
"""

import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError

import db
import seed
import services as s
import ui
from i18n import LANGUAGES, t

ui.setup("Public board", "🪧", layout="centered")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
today = s.local_today()
s.daily_refresh(conn, today)

EVENT_ICONS = {
    "WORK_REGISTERED": "🏗️", "NOTICE_SENT": "📨", "CITY_MAINTENANCE": "🏛️", "REPAIR_DONE": "🔧",
    "REPAIR_VERIFIED": "✅", "REPAIR_REJECTED": "↩️", "NOTICE_OVERDUE": "⏰",
    "GUARANTEE_ENDED": "📅", "DEPOSIT_RELEASED": "💰",
}

# ---------------------------------------------------------------------------
# Language + which work
# ---------------------------------------------------------------------------
lang = st.segmented_control("Language / भाषा / ભાષા", list(LANGUAGES.keys()), default="en",
                            format_func=lambda code: LANGUAGES[code], required=True)

works = conn.execute("SELECT id, name, ward FROM works ORDER BY id").fetchall()
labels = {w["id"]: f"{w['id']} · {w['name']} ({w['ward']})" for w in works}

work_id = st.query_params.get("work_id")
if work_id not in labels:
    ui.hero(t("board_title", lang), t("board_sub", lang), eyebrow="Jawabdari · जवाबदारी · જવાબદારી",
            show_brand=False)
    if work_id:
        st.warning(t("not_found", lang))
    work_id = st.selectbox(t("select_work", lang), list(labels.keys()), index=None,
                           format_func=lambda wid: labels[wid],
                           placeholder=t("select_placeholder", lang))

if not work_id:
    conn.close()
    st.stop()

work = s.get_work(conn, work_id)

# ---------------------------------------------------------------------------
# Header + big guarantee status
# ---------------------------------------------------------------------------
ui.hero(work["name"], f"{work['id']} · {work['ward'] or ''} · {t(work['asset_type'], lang)}",
        eyebrow=t("board_title", lang), show_brand=False)

if s.is_under_guarantee(work["dlp_end_date"], today) and work["lifecycle_stage"] != "Decommissioned":
    ui.status_banner("🛡️ " + t("guarantee_until", lang, date=work["dlp_end_date"]),
                     t("guarantee_note", lang), tone="green")
else:
    ui.status_banner("📅 " + t("guarantee_ended", lang, date=work["dlp_end_date"]),
                     t("ended_note", lang), tone="grey")

# ---------------------------------------------------------------------------
# Big "Report a problem" button -> Report page with this work preselected
# ---------------------------------------------------------------------------
try:
    st.page_link("pages/2_Report_Defect.py", label=t("report_button", lang), icon=":material/campaign:",
                 query_params={"work_id": work_id}, width="stretch")
except StreamlitPageNotFoundError:
    # Only when this page runs on its own (e.g. in tests): fall back to a plain link
    st.markdown(
        f'<a href="Report_Defect?work_id={ui.esc(work_id)}" target="_self" style="display:block;'
        f'text-align:center;background:#4338ca;color:white;padding:0.85rem;border-radius:12px;'
        f'font-size:1.1rem;font-weight:700;text-decoration:none;">📢 {ui.esc(t("report_button", lang))}</a>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Key facts
# ---------------------------------------------------------------------------
scores = s.contractor_scores(conn).set_index("contractor_id")
score = int(scores.loc[work["contractor_id"], "score"]) if work["contractor_id"] in scores.index else 100

open_count = conn.execute(
    f"SELECT COUNT(*) FROM defects WHERE work_id = ? AND status IN ({','.join('?' * len(s.UNRESOLVED_STATUSES))})",
    (work_id, *s.UNRESOLVED_STATUSES),
).fetchone()[0]
last_repair = conn.execute(
    "SELECT MAX(repaired_on) FROM defects WHERE work_id = ? AND status = 'Closed'", (work_id,)
).fetchone()[0]

ui.facts([
    (t("built_by", lang), work["contractor_name"], False),
    (t("rating", lang), f'<span class="jw-stars">{ui.stars(score)}</span> {score}/100', True),
    (t("cost", lang), s.format_inr(work["cost_rs"]), False),
    (t("completed_on", lang), work["completion_date"], False),
    (t("open_defects", lang), open_count, False),
    (t("last_repair", lang), last_repair or t("none", lang), False),
    (t("ward", lang), work["ward"] or "-", False),
    (t("asset_type", lang), t(work["asset_type"], lang), False),
])

# ---------------------------------------------------------------------------
# Lifecycle timeline
# ---------------------------------------------------------------------------
with st.expander(t("timeline", lang), icon=":material/history:"):
    ui.timeline(s.get_work_timeline(conn, work_id), EVENT_ICONS)

st.caption("Jawabdari · Ahmedabad Municipal Corporation · data shown is public information")
conn.close()
