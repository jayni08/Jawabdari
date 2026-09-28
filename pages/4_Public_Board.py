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
from i18n import LANGUAGES, t

st.set_page_config(page_title="Public Board | Jawabdari", page_icon="🪧", layout="centered")

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


def stars(score):
    """Score 0-100 -> 1 to 5 stars."""
    filled = max(1, min(5, round(score / 20)))
    return "★" * filled + "☆" * (5 - filled)


# ---------------------------------------------------------------------------
# Language + which work
# ---------------------------------------------------------------------------
lang = st.radio("Language / भाषा / ભાષા", list(LANGUAGES.keys()),
                format_func=lambda code: LANGUAGES[code], horizontal=True)
st.title(f"🪧 {t('board_title', lang)}")

works = conn.execute("SELECT id, name, ward FROM works ORDER BY id").fetchall()
labels = {w["id"]: f"{w['id']} - {w['name']} ({w['ward']})" for w in works}

work_id = st.query_params.get("work_id")
if work_id not in labels:
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
# Big status card
# ---------------------------------------------------------------------------
if s.is_under_guarantee(work["dlp_end_date"], today) and work["lifecycle_stage"] != "Decommissioned":
    badge = t("guarantee_until", lang, date=work["dlp_end_date"])
    note, bg, fg = t("guarantee_note", lang), "#1e8e3e", "#ffffff"
else:
    badge = t("guarantee_ended", lang, date=work["dlp_end_date"])
    note, bg, fg = t("ended_note", lang), "#5f6368", "#ffffff"

st.markdown(
    f"""
    <div style="border:1px solid #ddd;border-radius:14px;padding:1.2rem;margin-bottom:1rem;">
      <div style="font-size:1.5rem;font-weight:700;line-height:1.3;">{work['name']}</div>
      <div style="color:#666;margin-bottom:0.8rem;">{work['id']}</div>
      <div style="background:{bg};color:{fg};border-radius:10px;padding:0.9rem;text-align:center;
                  font-size:1.35rem;font-weight:800;letter-spacing:0.5px;">🛡️ {badge}</div>
      <div style="text-align:center;margin-top:0.5rem;font-size:1.05rem;">{note}</div>
    </div>
    """,
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

st.markdown(
    f"""
- **{t('ward', lang)}:** {work['ward'] or '-'}
- **{t('asset_type', lang)}:** {t(work['asset_type'], lang)}
- **{t('built_by', lang)}:** {work['contractor_name']}
- **{t('cost', lang)}:** {s.format_inr(work['cost_rs'])}
- **{t('completed_on', lang)}:** {work['completion_date']}
- **{t('rating', lang)}:** <span style="color:#f5a623;font-size:1.3rem;">{stars(score)}</span> ({score}/100)
- **{t('open_defects', lang)}:** {open_count}
- **{t('last_repair', lang)}:** {last_repair or t('none', lang)}
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Big "Report a problem" button -> Report page with this work preselected
# ---------------------------------------------------------------------------
try:
    st.page_link("pages/2_Report_Defect.py", label=f"📢 {t('report_button', lang)}",
                 query_params={"work_id": work_id}, width="stretch")
except StreamlitPageNotFoundError:
    # Happens only when this page is run on its own (e.g. in tests): use a plain link instead
    st.markdown(
        f'<a href="Report_Defect?work_id={work_id}" target="_self" style="display:block;'
        f'text-align:center;background:#1a73e8;color:white;padding:0.9rem;border-radius:10px;'
        f'font-size:1.2rem;font-weight:700;text-decoration:none;">📢 {t("report_button", lang)}</a>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Lifecycle timeline
# ---------------------------------------------------------------------------
with st.expander(f"🕒 {t('timeline', lang)}"):
    for event in s.get_work_timeline(conn, work_id):
        icon = EVENT_ICONS.get(event["event_type"], "•")
        st.markdown(f"{icon} **{event['created_at'][:10]}** — {event['details']}")

conn.close()
