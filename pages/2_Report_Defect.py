"""Report a problem - citizens (via QR code) and engineers report a defect.

The LIABILITY CHECK runs instantly:
- still under guarantee -> contractor must repair free, notice sent with a 7-day deadline
- guarantee ended       -> added to the city's own maintenance queue
Mobile-first: one column, big tap targets, three languages.
"""

import uuid
from pathlib import Path

import streamlit as st

import db
import seed
import services as s
import ui
from i18n import LANGUAGES, t

ui.setup("Report a problem", "📢", layout="centered")

db.init_db()
seed.ensure_seeded()
conn = db.get_conn()
s.daily_refresh(conn)

UPLOAD_DIR = Path("uploads")
MAX_PHOTO_MB = 5
# Problem keys (translated on screen) -> English text stored in the database
PROBLEMS = {"pothole": "Pothole", "crack": "Crack", "waterlogging": "Waterlogging",
            "light": "Light not working", "other": "Other"}
PROBLEM_ICONS = {"pothole": "🕳️", "crack": "⚡", "waterlogging": "🌊", "light": "💡", "other": "✏️"}

# ---------------------------------------------------------------------------
# Language first (everything below is translated)
# ---------------------------------------------------------------------------
lang = st.segmented_control("Language / भाषा / ભાષા", list(LANGUAGES.keys()), default="en",
                            format_func=lambda code: LANGUAGES[code], required=True)
ui.hero(t("title", lang), t("hero_sub", lang), eyebrow="Jawabdari · जवाबदारी · જવાબદારી",
        show_brand=False)

# ---------------------------------------------------------------------------
# Which work? (preselected if the QR link has ?work_id=W-0012)
# ---------------------------------------------------------------------------
works = conn.execute("SELECT id, name, ward FROM works ORDER BY id").fetchall()
work_labels = {w["id"]: f"{w['id']} · {w['name']} ({w['ward']})" for w in works}
work_ids = list(work_labels.keys())

url_work = st.query_params.get("work_id")
preselect = work_ids.index(url_work) if url_work in work_labels else None
if url_work and url_work not in work_labels:
    st.warning(f"Work '{url_work}' not found. Please choose from the list.")

with st.container(border=True):
    work_id = st.selectbox(t("select_work", lang), work_ids, index=preselect,
                           format_func=lambda wid: work_labels[wid],
                           placeholder=t("select_placeholder", lang))

    problem = st.pills(t("problem_type", lang), list(PROBLEMS.keys()), default="pothole",
                       format_func=lambda key: f"{PROBLEM_ICONS[key]} {t(key, lang)}", required=True)
    details = st.text_area(t("describe", lang), max_chars=500, height=90)
    photo = st.file_uploader(t("photo", lang), type=["jpg", "jpeg", "png"])

    c1, c2 = st.columns(2)
    reporter = c1.segmented_control(t("reporter", lang), ["Citizen", "Engineer"], default="Citizen",
                                    format_func=lambda r: t(r.lower(), lang), required=True)
    reporter_name = c2.text_input(t("your_name", lang), max_chars=80)

    submitted = st.button(t("submit", lang), type="primary", icon=":material/send:", width="stretch")

# ---------------------------------------------------------------------------
# Submit -> liability check
# ---------------------------------------------------------------------------
if submitted:
    if work_id is None:
        st.error(t("no_work", lang))
    elif problem == "other" and not details.strip():
        st.error(t("describe_required", lang))
    elif photo is not None and photo.size > MAX_PHOTO_MB * 1024 * 1024:
        st.error(t("photo_too_big", lang))
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

# Show the result only for the work it belongs to (not after switching to another work)
result = st.session_state.get("last_report")
if result and result["work_id"] == work_id:
    st.success(t("thank_you", lang), icon=":material/check_circle:")
    if result["under_guarantee"]:
        ui.status_banner(
            "🛡️ " + t("result_contractor_h", lang),
            t("under_guarantee", lang, dlp_end=result["dlp_end_date"], contractor=result["contractor_name"],
              deadline=result["notice_deadline"], defect_id=result["defect_id"]),
            tone="green",
        )
    else:
        ui.status_banner(
            "🏛️ " + t("result_city_h", lang),
            t("city_repair", lang, dlp_end=result["dlp_end_date"], defect_id=result["defect_id"]),
            tone="amber",
        )

conn.close()
