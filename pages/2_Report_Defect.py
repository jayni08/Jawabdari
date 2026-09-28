"""Report Defect - citizens (via QR code) and engineers report a problem.

The LIABILITY CHECK runs instantly:
- still under guarantee -> contractor must repair free, notice sent with a 7-day deadline
- guarantee ended       -> added to the city's own maintenance queue
"""

import uuid
from pathlib import Path

import streamlit as st

import db
import seed
import services as s
from i18n import LANGUAGES, t

st.set_page_config(page_title="Report a Problem | Jawabdari", page_icon="📢")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
s.daily_refresh(conn)

UPLOAD_DIR = Path("uploads")
# Problem keys (translated on screen) -> English text stored in the database
PROBLEMS = {"pothole": "Pothole", "crack": "Crack", "waterlogging": "Waterlogging",
            "light": "Light not working", "other": "Other"}


def result_card(text, colour, border):
    """Big, easy-to-read coloured card for the result."""
    st.markdown(
        f"""<div style="background:{colour};border-left:8px solid {border};padding:1.2rem 1.4rem;
        border-radius:10px;font-size:1.25rem;line-height:1.6;color:#1a1a1a;">{s.safe_html(text)}</div>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Language + reporter
# ---------------------------------------------------------------------------
lang = st.radio("Language / भाषा / ભાષા", list(LANGUAGES.keys()),
                format_func=lambda code: LANGUAGES[code], horizontal=True)
st.title(f"📢 {t('title', lang)}")

reporter = st.radio(t("reporter", lang), ["Citizen", "Engineer"],
                    format_func=lambda r: t(r.lower(), lang), horizontal=True)

# ---------------------------------------------------------------------------
# Choose the work (preselected if the QR link has ?work_id=W-0012)
# ---------------------------------------------------------------------------
works = conn.execute("SELECT id, name, ward FROM works ORDER BY id").fetchall()
work_labels = {w["id"]: f"{w['id']} - {w['name']} ({w['ward']})" for w in works}
work_ids = list(work_labels.keys())

url_work = st.query_params.get("work_id")
preselect = work_ids.index(url_work) if url_work in work_labels else None
if url_work and url_work not in work_labels:
    st.warning(f"Work '{url_work}' not found. Please choose from the list.")

work_id = st.selectbox(t("select_work", lang), work_ids, index=preselect,
                       format_func=lambda wid: work_labels[wid],
                       placeholder=t("select_placeholder", lang))

# ---------------------------------------------------------------------------
# Problem details
# ---------------------------------------------------------------------------
problem = st.radio(t("problem_type", lang), list(PROBLEMS.keys()),
                   format_func=lambda key: t(key, lang), horizontal=True)
details = st.text_area(t("describe", lang), max_chars=500)
photo = st.file_uploader(t("photo", lang), type=["jpg", "jpeg", "png"])
reporter_name = st.text_input(t("your_name", lang), max_chars=80)

# ---------------------------------------------------------------------------
# Submit -> liability check
# ---------------------------------------------------------------------------
if st.button(t("submit", lang), type="primary"):
    if work_id is None:
        st.error(t("no_work", lang))
    elif problem == "other" and not details.strip():
        st.error(t("describe_required", lang))
    else:
        description = PROBLEMS[problem] + (f": {details.strip()}" if details.strip() else "")

        photo_path = None
        if photo is not None:
            UPLOAD_DIR.mkdir(exist_ok=True)
            extension = Path(photo.name).suffix.lower() or ".jpg"
            photo_path = str(UPLOAD_DIR / f"{work_id}_{s.local_today()}_{uuid.uuid4().hex[:8]}{extension}")
            Path(photo_path).write_bytes(photo.getbuffer())

        try:
            result = s.report_defect(
                conn, work_id, reporter, reporter_name.strip() or "Anonymous", description,
                language=lang, photo_path=photo_path,
            )
            st.session_state["last_report"] = result
        except ValueError as err:
            st.error(str(err))

# Show the result (kept in session so it stays visible)
result = st.session_state.get("last_report")
if result:
    st.success(t("thank_you", lang))
    if result["under_guarantee"]:
        text = t("under_guarantee", lang, dlp_end=result["dlp_end_date"],
                 contractor=result["contractor_name"], deadline=result["notice_deadline"],
                 defect_id=result["defect_id"])
        result_card("🛡️ " + text, "#e6f4ea", "#1e8e3e")
    else:
        text = t("city_repair", lang, dlp_end=result["dlp_end_date"], defect_id=result["defect_id"])
        result_card("🏛️ " + text, "#fff4e5", "#e8710a")

conn.close()
